import hashlib
import pymysql
from server.config import settings
from contextlib import contextmanager
from langchain_milvus import BM25BuiltInFunction, Milvus
from langchain_openai import OpenAIEmbeddings
from server.models.milvus import (
    JobHit,
    JobProfileInput,
    QuestionHit,
    QuestionInput,
    RagHit,
)

class Database:
    """数据库连接管理"""

    def __init__(self):
        self.config = {
            "host": settings.db_host,
            "port": settings.db_port,
            "user": settings.db_user,
            "password": settings.db_password,
            "database": settings.db_name,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": False,  # 手动提交，service层控制事务
        }

    def get_conn(self):
        """获取新连接"""
        return pymysql.connect(**self.config)

    def execute(self, sql: str, params=None):
        """执行增删改，返回影响行数"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                rows = cursor.execute(sql, params)
            conn.commit()
            return rows
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def query(self, sql: str, params=None, one: bool = False):
        """执行查询，one=True返回单条"""
        conn = self.get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone() if one else cursor.fetchall()
        finally:
            conn.close()
    @contextmanager
    def transaction(self):
        conn = self.get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

class MilvusDataBase:
   
    def __init__(self, _collection_name: str):
        """初始化一个 Milvus Collection 的向量存储连接"""
        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            check_embedding_ctx_length=False,
        )
        self._vectorstore = Milvus(
            embedding_function=embeddings,
            connection_args={
                "uri": f"http://{settings.milvus_host}:{settings.milvus_port}",
                "user": settings.milvus_username,
                "password": settings.milvus_password,
                "db_name": settings.milvus_db_name,
            },
            builtin_function=BM25BuiltInFunction(),
            vector_field=["vector", "sparse"], # 指定向量字段名称
                index_params=[
                {
                    "index_type": "FLAT", # 指定索引类型为 FLAT，暴力搜索
                    "metric_type": "COSINE", # 指定度量类型为 COSINE
                },
                {
                    "index_type": "SPARSE_INVERTED_INDEX", # 指定索引类型为 SPARSE_INVERTED_INDEX
                    "metric_type": "BM25", # 指定度量类型为 BM25
                },
            ],
            collection_name=_collection_name,
            consistency_level="Strong",
            drop_old=False,
        )
        self._collection_name = _collection_name

    def _store(self) -> Milvus:
        """获取底层 LangChain Milvus 向量存储实例"""
        return self._vectorstore

    def _rrf_search(
        self, query: str, top_k: int = 5, expr: str | None = None
    ) -> list:
        """统一双路检索：COSINE + BM25 → RRF 排名融合"""
        kwargs: dict = {
            "search_type": "similarity",
            "k": top_k,
            "ranker_type": "rrf",
            "ranker_params": {"k": 60},
        }
        if expr:
            kwargs["expr"] = expr
        return self._store().search(query, **kwargs)

    """
    静态方法，获取
    """
    @staticmethod
    def build_question_pk(company_id: int, job_id: int, question_md5: str) -> int:
        """构建题库主键: MD5({company_id}_{job_id}_{question_md5}) → INT64

        拼接三要素 → MD5 哈希 → 取前 8 字节 → 无符号 INT64。
        同一公司、同一岗位、同一题目 → 相同主键（天然去重）。
        """
        raw = f"{company_id}_{job_id}_{question_md5}"
        md5_bytes = hashlib.md5(raw.encode()).digest()
        return int.from_bytes(md5_bytes[:8], "big", signed=False)
    
    """
    题库操作，增删改查
    """
    def insert_questions(self, questions: list[QuestionInput]) -> list[str]:
        """批量插入面试题目，自动 Embedding + 混合索引"""
        texts = []
        metadatas = []
        ids = []
        for q in questions:
            texts.append(q.question)
            pk = self.build_question_pk(q.company_id, q.job_id, q.question_md5)
            ids.append(str(pk))
            metadatas.append({
                "pk": pk,
                "company_id": q.company_id,
                "job_id": q.job_id,
                "question": q.question,
                "answer": q.answer,
                "difficulty": q.difficulty,
            })
        return self._store().add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def search_questions(
        self,
        query: str,        # 检索文本
        top_k: int = 5,    # 搜索数量
        expr: str | None = None,
    ) -> list[QuestionHit]:
        """混合检索题目：BM25 + COSINE → RRF 融合

        expr: Milvus 标量过滤表达式，如 "difficulty >= 2"
        """
        docs = self._rrf_search(query, top_k, expr)
        return [
            QuestionHit(
                pk=doc.metadata.get("pk", 0),
                question=doc.metadata.get("question", doc.page_content),
                answer=doc.metadata.get("answer", ""),
                difficulty=doc.metadata.get("difficulty", 0),
                job_id=doc.metadata.get("job_id", 0),
                company_id=doc.metadata.get("company_id", 0),
                score=doc.metadata.get("score", 0.0),
            )
            for doc in docs
        ]

    def delete_questions(self, ids: list[str]) -> bool:
        """按 ID 删除题目"""
        return self._store().delete(ids=ids)

    """
    岗位画像操作
    """

    def insert_job(self, job: JobProfileInput) -> list[str]:
        """插入岗位画像到 Milvus（自动 Embedding）"""
        job_id = str(job.job_id)
        return self._store().add_texts(
            texts=[job.text],
            metadatas=[{         # 元数据，留给业务层使用
                "job_id": job.job_id,
                "company_id": job.company_id,
            }],
            ids=[job_id],
        )

    def upsert_job(self, job: JobProfileInput) -> list[str]:
        """
        插入或更新岗位画像（按 job_id 去重）
        """
        job_id = str(job.job_id)
        # 先删后插，确保幂等
        try:
            self._store().delete(ids=[job_id])
        except Exception:
            pass
        return self.insert_job(job)

    def search_jobs(
        self, query: str, top_k: int = 5, expr: str | None = None
    ) -> list[JobHit]:
        """混合检索岗位：BM25 + COSINE → RRF 融合"""
        docs = self._rrf_search(query, top_k, expr)
        return [
            JobHit(
                job_id=doc.metadata.get("job_id"),
                company_id=doc.metadata.get("company_id", 0),
                text=doc.page_content,
                score=doc.metadata.get("score", 0.0),
            )
            for doc in docs
        ]


# 全局单例
db = Database()
