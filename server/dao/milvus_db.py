import logging
import threading
import time

from pymilvus import  DataType, Function, FunctionType, AnnSearchRequest, RRFRanker

from server.config import settings, embedding,milvus_client
from server.models.milvus import JobProfileInput, QuestionInput, QuestionHit

_log = logging.getLogger(__name__)

# ── 模块级常量 ──────────────────────────────────────────
_ANALYZER_PARAMS = {"type": "chinese"}

# ── 模块级 embedding 缓存（TTL + 容量上限，防止内存无限增长）──

class _EmbeddingCache:
    """线程安全的 embedding 缓存，支持 TTL 过期和容量上限。

    相比 @lru_cache：
    - 按时间过期（TTL），而非仅按访问频率淘汰
    - 更大容量（默认 2048）
    - 惰性淘汰：获取时跳过过期项，写满时触发批量清理
    """

    def __init__(self, maxsize: int = 2048, ttl: int = 3600):
        """
        Args:
            maxsize: 最大缓存条目数
            ttl: 有效期（秒），默认 1 小时
        """
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: dict[str, tuple[float, tuple[float, ...]]] = {}  # text → (ts, embedding)
        self._lock = threading.Lock()

    def get(self, text: str) -> list[float] | None:
        """获取缓存的 embedding，过期返回 None"""
        with self._lock:
            entry = self._store.get(text)
            if entry is None:
                return None
            ts, emb = entry
            if time.time() - ts > self._ttl:
                del self._store[text]
                return None
            return list(emb)

    def put(self, text: str, embedding: tuple[float, ...]):
        """写入缓存；满了先淘汰过期项再按 LRU 驱逐"""
        with self._lock:
            if len(self._store) >= self._maxsize:
                self._evict()
            self._store[text] = (time.time(), embedding)

    def _evict(self):
        """淘汰策略：先删过期项，仍满则删最早插入的 25%"""
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]
        if len(self._store) >= self._maxsize:
            # 按插入时间排序，删最早 25%
            sorted_keys = sorted(self._store.items(), key=lambda x: x[1][0])
            remove_count = max(len(sorted_keys) // 4, 1)
            for k, _ in sorted_keys[:remove_count]:
                del self._store[k]

    def clear(self):
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# 全局 embedding 缓存实例
_embedding_cache = _EmbeddingCache(maxsize=2048, ttl=3600)


def _cached_embedding(text: str) -> list[float]:
    """对 text 做 embedding，优先命中 TTL 缓存。

    Returns:
        list[float] — 可直接使用的向量
    """
    # 1. 查缓存
    cached = _embedding_cache.get(text)
    if cached is not None:
        return cached

    # 2. 调 API
    client = embedding
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=1024,
    )
    result = response.data[0].embedding  # list[float]

    # 3. 写缓存
    _embedding_cache.put(text, tuple(result))
    return result


# ── 常用集合单例（避免每次新建实例 -> has_collection 网络调用）──

_job_profile_mdb: "MilvusDataBase | None" = None


def get_job_profile_mdb() -> "MilvusDataBase":
    """获取岗位画像集合的 MilvusDataBase 单例"""
    global _job_profile_mdb
    if _job_profile_mdb is None:
        from server.config import settings
        _job_profile_mdb = MilvusDataBase(settings.collection_name)
    return _job_profile_mdb

class MilvusDataBase:

    def __init__(self, collection_name: str="offical_job_question_bank"):
        """初始化Milvus数据库连接"""
        self._milvus = milvus_client
        self._collection_name = collection_name
        self._collection_exists = False  # 实例级缓存，运行时 collection 不常变

    def _ensure_collection(self, create_fn=None):
        """缓存式 collection 存在检查，避免每次操作都 ping Milvus"""
        if self._collection_exists:
            return
        if self._milvus.has_collection(self._collection_name):
            self._collection_exists = True
        elif create_fn:
            create_fn()
            self._collection_exists = True

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本向量（优先命中模块级 TTL 缓存）"""
        return _cached_embedding(text)

    def _get_index_params(self):
        """直接返回双路索引：密集 + 稀疏"""
        try:
            index_params = self._milvus.prepare_index_params()
            index_params.add_index(
                field_name="vector", index_type="FLAT", metric_type="COSINE"
            )
            index_params.add_index(
                field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25"
            )
            return index_params
        except Exception as e:
            raise Exception("Milvus 索引参数获取失败")

    def _create_questions_collection(self, collection_name: str = "offical_job_question_bank"):
        """
        创建公司题库: PK((chunk+岗位id):做md5)-岗位id-(题目-参考答案)-向量化-评分标准,有分区(不同岗位不同分区)  
        {双路检索:BM25(稀疏) + COSINE(密集) → RRF 融合}
        """
        try:
            if self._milvus.has_collection(collection_name):
                return

            schema = self._milvus.create_schema(auto_id=False, enable_dynamic_field=True)

            # 主键：MD5(chunk + job_id) 的十六进制字符串
            schema.add_field(
                field_name="pk", datatype=DataType.VARCHAR, max_length=64, is_primary=True
            )
            # 分区键
            schema.add_field(
                field_name="question_bank_partition", datatype=DataType.VARCHAR, max_length=100, is_partition_key=True
            )
            # 业务字段
            schema.add_field(
                field_name="job_id", datatype=DataType.INT64,
            )
            analyzer_params = _ANALYZER_PARAMS
            schema.add_field(
                field_name="question", datatype=DataType.VARCHAR, max_length=65535,enable_analyzer=True,analyzer_params=analyzer_params
            )
            schema.add_field(
                field_name="answer", datatype=DataType.VARCHAR, max_length=65535,enable_analyzer=True
            )
            schema.add_field(
                field_name="scoring_criteria", datatype=DataType.VARCHAR, max_length=65535
            )
            schema.add_field(
                field_name="difficulty", datatype=DataType.INT64,
            )
            # 密集向量（COSINE）
            schema.add_field(
                field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=1024
            )
            # 稀疏向量（BM25 输出）
            schema.add_field(
                field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR
            )

            # BM25 Function：对 question 字段自动生成稀疏向量
            bm25_fn = Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["question"],
                output_field_names=["sparse"],
            )
            schema.add_function(bm25_fn)

            self._milvus.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=self._get_index_params(),
            )
        except Exception as e:
            raise Exception(f"Milvus 题库创建失败,原因:{e}")

    def _create_job_profile_collection(self, collection_name: str = "job_profile"):
        """
        创建岗位画像: PK(岗位id)-(岗位画像TEXT)-向量化  
        {双路检索:BM25(稀疏) + COSINE(密集) → RRF 融合}
        """
        try:
            if self._milvus.has_collection(collection_name):
                return

            schema = self._milvus.create_schema(auto_id=False, enable_dynamic_field=True)

            # 主键：岗位id
            schema.add_field(
                field_name="job_id", datatype=DataType.INT64, is_primary=True
            )
            # 业务字段
            analyzer_params = _ANALYZER_PARAMS
            schema.add_field(
                field_name="profile_text", datatype=DataType.VARCHAR, max_length=65535,enable_analyzer=True,analyzer_params=analyzer_params
            )
            # 密集向量（COSINE）
            schema.add_field(
                field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=1024
            )
            # 稀疏向量（BM25 输出）
            schema.add_field(
                field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR
            )
            # BM25 Function：对 profile_text 字段自动生成稀疏向量
            bm25_fn = Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["profile_text"],
                output_field_names=["sparse"],
            )
            schema.add_function(bm25_fn)
            self._milvus.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=self._get_index_params(),
            )
        except Exception as e:
            raise Exception(f"Milvus 岗位画像表创建失败,原因:{e}")

    def _insert_job_question(self, job_question: QuestionInput)->bool:
        """
        插入公司题库->判断表是否存在->（不存在创建表）->插入数据    
        question_md5:pk主键  
        question_bank_partition:分区键
        job_id:岗位id  
        question:问题  
        answer:答案  
        scoring_criteria:评分标准  
        difficulty:难度  
        vector:向量:问题答案    
        """
        try:
            self._ensure_collection(lambda: self._create_questions_collection(self._collection_name))
            # 通过question_md5判断是否重复（pk即question_md5）
            existing = self._milvus.get(
                collection_name=self._collection_name,
                ids=[job_question.question_md5],
            )
            if existing:
                _log.debug("已存在question_md5:%s", job_question.question_md5)
                return False
            # 核心：拼接题目+答案一起向量化
            combined_text = f"题目：{job_question.question}\n答案：{job_question.answer}"
            vector = self._get_embedding(combined_text)
            self._milvus.insert(
                collection_name=self._collection_name,
                data=[{
                    "pk": job_question.question_md5,
                    "question_bank_partition": job_question.question_bank_partition,
                    "job_id": job_question.job_id,
                    "question": job_question.question,
                    "answer": job_question.answer,
                    "scoring_criteria": job_question.scoring_criteria or "",
                    "difficulty": job_question.difficulty or 3,
                    "vector": vector,
                }]
            )
            return True
        except Exception as e:
            raise Exception(f"Milvus 题库插入失败,原因:{e}")

    def _insert_job_profile(self,job: JobProfileInput):
        """
        插入用户画像->判断表是否存在->（不存在创建表）->插入数据  
        job_id:pk主键  
        vector:向量  
        profile_text:文本  
        """
        try:
            self._ensure_collection(lambda: self._create_job_profile_collection())
            vector = self._get_embedding(job.profile_text)
            self._milvus.insert(
                collection_name=self._collection_name,
                data=[{
                    "job_id": job.job_id,
                    "profile_text": job.profile_text,
                    "vector": vector,
                }]
            )
        except Exception as e:
            raise Exception(f"Milvus 岗位画像插入失败,原因:{e}")
        
    def _rrf_search(self, query: str, top_k: int = 10, filter_expr: str | None = None,
                    output_fields: list[str] = None, score_threshold: float = 0.0,
                    vector: list[float] | None = None) -> list[dict]:
        """
        双路检索：BM25(稀疏) + COSINE(密集) → RRF 排名融合
        filter_expr: Milvus 过滤表达式，如 'question_bank_partition == "xxx"'
        score_threshold: COSINE 相似度阈值（0~1），仅 job 画像搜索使用，题库搜索传 0
        vector: 预计算的密集向量，传入则跳过 embedding API 调用
        """
        try:
            self._ensure_collection()
            if not self._collection_exists:
                raise Exception(f"Milvus 集合不存在: {self._collection_name}")
            if vector is None:
                vector = self._get_embedding(query)
            cos_param = {"metric_type": "COSINE"}
            if score_threshold > 0:
                # radius 是下界（保留距离 >= score_threshold 的结果）
                # range_filter 是上界，COSINE 最大为 1.0
                cos_param["radius"] = score_threshold
                cos_param["range_filter"] = 1.0
            text_search = AnnSearchRequest(
                data=[vector],
                anns_field="vector",
                param=cos_param,
                limit=top_k
            )
            sparse_search = AnnSearchRequest(
                data=[query],
                anns_field="sparse",
                param={"metric_type": "BM25"},
                limit=top_k
            )
            reqs = [text_search, sparse_search]
            ranker = RRFRanker(k=100)
            kwargs = dict(
                collection_name=self._collection_name,
                reqs=reqs,
                ranker=ranker,
                limit=top_k,
                output_fields=output_fields,
            )
            if filter_expr:
                kwargs["filter"] = filter_expr
            result = self._milvus.hybrid_search(**kwargs)
            return result[0] if result else []
        except Exception as e:
            raise Exception(f"Milvus RRF 搜索失败,原因:{e}")

    def search_jobs(self, query: str, top_k: int = 10, score_threshold: float = 0.95,
                    vector: list[float] | None = None) -> list[int]:
        """
        混合检索岗位画像 → 返回匹配的 job_id 列表
        COSINE 相似度 ≥ score_threshold 由 Milvus 在向量检索层过滤
        vector: 预计算的密集向量，传入则跳过 embedding API 调用
        """
        hits = self._rrf_search(query, top_k=top_k, output_fields=["job_id"],
                                score_threshold=score_threshold, vector=vector)
        job_ids: list[int] = []
        for h in hits:
            jid = h.get("entity", {}).get("job_id") or h.get("job_id")
            if jid and jid not in job_ids:
                job_ids.append(jid)
        return job_ids

    def _delete_job_profiles(self, job_ids: list[int]):
        try:
            self._ensure_collection()
            if not self._collection_exists:
                raise Exception(f"Milvus 岗位画像表不存在")
            self._milvus.delete(
                collection_name=self._collection_name,
                ids=job_ids,
            )
        except Exception as e:
            raise Exception(f"Milvus 岗位画像删除失败,原因:{e}")

    def _delete_job_questions(self, job_ids: list[int]):
        try:
            self._ensure_collection()
            if not self._collection_exists:
                raise Exception(f"Milvus 题库表不存在")
            self._milvus.delete(
                collection_name=self._collection_name,
                filter=f"job_id in {job_ids}",
            )
        except Exception as e:
            raise Exception(f"Milvus 题库删除失败,原因:{e}")

    def _delete_question(self, pk: str) -> bool:
        """按主键删除单条题目"""
        try:
            self._ensure_collection()
            if not self._collection_exists:
                return False
            self._milvus.delete(
                collection_name=self._collection_name,
                ids=[pk],
            )
            return True
        except Exception as e:
            raise Exception(f"题目删除失败,原因:{e}")

    def _update_question(self, pk: str, partition: str, job_id: int,
                         question: str, answer: str,
                         scoring_criteria: str, difficulty: int) -> bool:
        """更新题目：重新向量化 → upsert（避免先删后插的数据丢失窗口）"""
        try:
            self._ensure_collection(lambda: self._create_questions_collection(self._collection_name))

            # 1. 重新向量化（题目+答案合并 embedding）
            combined_text = f"题目：{question}\n答案：{answer}"
            vector = self._get_embedding(combined_text)

            # 2. upsert：按 pk 存在则更新，不存在则插入（无数据丢失窗口）
            self._milvus.upsert(
                collection_name=self._collection_name,
                data=[{
                    "pk": pk,
                    "question_bank_partition": partition,
                    "job_id": job_id,
                    "question": question,
                    "answer": answer,
                    "scoring_criteria": scoring_criteria or "",
                    "difficulty": difficulty or 3,
                    "vector": vector,
                }]
            )
            return True
        except Exception as e:
            raise Exception(f"题目更新失败,原因:{e}")

    def _get_question_by_pk(self, pk: str) -> dict | None:
        """按主键查询单条题目"""
        try:
            self._ensure_collection()
            if not self._collection_exists:
                _log.warning("Milvus 题库表不存在")
                return None
            results = self._milvus.get(
                collection_name=self._collection_name,
                ids=[pk],
                output_fields=["pk", "question", "answer", "scoring_criteria",
                               "difficulty", "job_id", "question_bank_partition"],
            )
            return results[0] if results else None
        except Exception as e:
            raise Exception(f"题目查询失败,原因:{e}")

    def _delete_question_collection(self):
        try:
            self._ensure_collection()
            if self._collection_exists:
                self._milvus.drop_collection(self._collection_name)
                self._collection_exists = False
        except Exception as e:
            raise Exception(f"Milvus 题库表删除失败,原因:{e}")
    
