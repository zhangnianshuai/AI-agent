import hashlib
import logging
from pathlib import Path

from server.config import settings,llm

_log = logging.getLogger(__name__)
from server.dao.database import db
from server.dao.job_dao import JobDAO
from server.dao.company_dao import CompanyDao
from server.dao.user_dao import UserDao
from server.dao.resume_dao import ResumeDao
from server.dao.interview_dao import InterviewDao
from server.dao.agent_dao import AgentConfigDao
from server.models.job import Job
from server.models.result import Result
from server.models.request import JobSearchRequest
from server.utils.content_checker import check_job_content
from server.utils.permission import AccessControl
from server.utils.sql_builder import build_set
from server.utils.snowflake import snowflake
from server.utils.word_split import split_word

from server.service.ai_server import LLMService
from server.dao.milvus_db import MilvusDataBase, get_job_profile_mdb, _cached_embedding
from server.models.milvus import JobProfileInput,QuestionInput


class JobService:
    """岗位业务逻辑"""

    def __init__(self):
        self.job_dao = JobDAO()
        self.company_dao = CompanyDao()
        self.user_dao = UserDao()
        self.resume_dao = ResumeDao()
        self.interview_dao = InterviewDao()
        self.agent_dao = AgentConfigDao()
        self.access = AccessControl(self.company_dao)

    def _store_job_profile(
        self, company: dict, job_id: int, title: str,
        description: str = None, location: str = None,
        category: str = None, education_requirement: str = None,
        experience_requirement: str = None,
    ) -> bool:
        """拼接岗位信息 → LLM 生成画像 → 存入 Milvus 向量数据库"""
        try:
            # 1. 拼接岗位信息为一段文本
            parts: list[str] = [f"job_id: {job_id}"]
            if title:
                parts.append(f"岗位名称: {title}")
            if description:
                parts.append(f"岗位描述和要求: {description}")
            if location:
                parts.append(f"工作地点: {location}")
            if category:
                parts.append(f"岗位类型: {category}")
            if education_requirement:
                parts.append(f"学历要求: {education_requirement}")
            if experience_requirement:
                parts.append(f"工作经验要求: {experience_requirement}")
            text = ", ".join(parts)

            # 2. LLM 生成岗位画像摘要
            client = llm
            ai_server = LLMService(client)
            profile_text = ai_server.get_job_profile(text)
            if not profile_text:
                return False

            # 3. 存入 Milvus
            milvus = MilvusDataBase(settings.collection_name)
            profile = JobProfileInput(
                job_id=job_id,
                profile_text=profile_text,
                company_id=company["id"],
            )
            milvus._insert_job_profile(profile)
            return True
        except Exception as e:
            _log.warning(f"岗位画像向量存入失败：job_id={job_id}, 原因={e}")
            return False

    def create_job(self, user_id: int, company_id: int, title: str,
                   agent_config_id: int = None, description: str = None,
                   salary_min: int = None, salary_max: int = None,
                   location: str = None, category: str = None,
                   education_requirement: str = None,
                   experience_requirement: str = None,
                   headcount: int = 1, role: str = None) -> Result:
        """创建岗位，仅公司HR或管理员可操作"""
        try:

            # 1. 校验公司存在(user_id, company_id)
            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")
            if err := self.access.can_operate_job(user_id, role, company_id):
                return err

            # 2. 内容违规检测
            job = Job(
                title=title,
                company_id=company_id,
                description=description,
                location=location,
                category=category,
                education_requirement=education_requirement,
                experience_requirement=experience_requirement,
            )
            if not check_job_content(job):
                return Result.fail(code=400, message="内容违规，请修改后重新提交")

            # 3. 生成分区名
            job_id=job.id
            partition_name = f"part_{job_id}"

            # 4. 写入
            self.job_dao.insert_job(
                job_id=job_id,
                company_id=company_id,
                question_bank_partition=partition_name,   # 题库分区名
                agent_config_id=agent_config_id,
                title=title,
                description=description,
                salary_min=salary_min,
                salary_max=salary_max,
                location=location,
                category=category,
                education_requirement=education_requirement,
                experience_requirement=experience_requirement,
                headcount=headcount,
            )
            try:
                # 5. 岗位画像存入向量数据库
                vector_stored = self._store_job_profile(
                    company=company, job_id=job_id, title=title,
                    description=description, location=location,
                    category=category, education_requirement=education_requirement,
                    experience_requirement=experience_requirement,
                )
            except Exception as e:
                self.job_dao.delete_job(job_id)
                return Result.fail(code=500, message=str(e))


            return Result.success(data={
                "job_id": job_id,
                "company_id": company_id,
                "title": title,
                "question_bank_partition": partition_name,
                "vector_stored": vector_stored,
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))
    
    def search_jobs(self, req: JobSearchRequest, role: str = None) -> Result:
        """分页条件搜索岗位。普通用户只看上架(status=1)，HR/管理员看全部"""
        try:
            filters = {
                "keyword": req.keyword,
                "location": req.location,
                "category": req.category,
                "education_requirement": req.education_requirement,
                "experience_requirement": req.experience_requirement,
                "company_id": req.company_id,
            }
            filters = {k: v for k, v in filters.items() if v is not None}

            is_staff = role in ("hr", "admin")
            rows = self.job_dao.search_jobs(
                page=req.page, page_size=req.page_size,
                show_all=is_staff, **filters,
            )
            total = self.job_dao.count_jobs(show_all=is_staff, **filters)
            items = [
                {
                    "job_id": r["job_id"],
                    "title": r.get("title", ""),
                    "company_id": r.get("company_id"),
                    "company_name": r.get("company_name", ""),
                    "company_logo": r.get("company_logo", ""),
                    "salary_min": r.get("salary_min"),
                    "salary_max": r.get("salary_max"),
                    "location": r.get("location"),
                    "category": r.get("category", ""),
                    "education_requirement": r.get("education_requirement"),
                    "experience_requirement": r.get("experience_requirement"),
                    "headcount": r.get("headcount", 0),
                    "status": r.get("status", 1),
                }
                for r in rows
            ]

            return Result.success(data={
                "items": items,
                "total": total,
                "page": req.page,
                "page_size": req.page_size,
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))
        
    def ai_search_jobs(self, user_id: int) -> Result:
        """AI智能搜索岗位：基于用户简历内容向量匹配岗位"""
        try:
            # 1. 获取用户简历解析文本
            parsed = self.resume_dao.get_parsed_content(user_id)
            if not parsed or not parsed.get("parsed_content"):
                return Result.fail(code=404, message="未找到简历信息，请先上传简历")

            # 2. 向量检索匹配岗位
            #    使用模块级单例避免每次 has_collection 网络调用
            #    预计算 embedding（命中 TTL 缓存则跳过 API 调用）
            query_text = parsed["parsed_content"]
            vector = _cached_embedding(query_text)
            milvus = get_job_profile_mdb()
            job_ids = milvus.search_jobs(query=query_text, vector=vector)

            if not job_ids:
                return Result.success(data={"items": [], "total": 0})

            # 3. 根据 job_id 列表获取岗位详情
            jobs = self.job_dao.get_job_list_by_ids(job_ids)

            # 4. 按 Milvus 返回的排序组装结果（保持相关性顺序）
            job_map = {j["job_id"]: j for j in jobs}
            items = []
            for jid in job_ids:
                job = job_map.get(jid)
                if job:
                    items.append({
                        "job_id": job["job_id"],
                        "title": job.get("title", ""),
                        "company_name": job.get("company_name", ""),
                        "company_logo": job.get("company_logo", ""),
                        "salary_min": job.get("salary_min"),
                        "salary_max": job.get("salary_max"),
                        "education_requirement": job.get("education_requirement"),
                        "experience_requirement": job.get("experience_requirement"),
                    })

            return Result.success(data={
                "items": items,
                "total": len(items),
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))
        
    def get_job_detail(self, job_id: int, role: str = None) -> Result:
        """获取岗位详情。普通用户只能看已上架，HR/admin可看全部"""
        try:
            job = self.job_dao.get_job_by_id(job_id)
            if not job:
                return Result.fail(code=404, message="未找到岗位信息")
            is_staff = role in ("hr", "admin")
            if not is_staff and job.get("status") != 1:
                return Result.fail(code=404, message="岗位已下线")

            return Result.success(data=job)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def insert_question(self,company_id: int, job_id: int,user_id:int, role: str = None) -> Result:
        """插入问题"""
        try:
            # 检测公司是否有题库集合，没有则自动创建
            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")
            if not company.get("question_bank_collection"):
                import uuid
                collection_name = f"col_{uuid.uuid4().hex}"
                milvus = MilvusDataBase()
                milvus._create_questions_collection(collection_name)
                db.execute("UPDATE company SET question_bank_collection = %s WHERE id = %s",
                          (collection_name, company_id))
                company["question_bank_collection"] = collection_name

            # 获取公司题库表和岗位题库分区，顺便判断用户是否有该公司
            question_bank_collection, question_bank_partition = self.job_dao.get_question_bank_collection_and_partition(company_id, job_id)
            if not question_bank_collection or not question_bank_partition:
                return Result.fail(code=404, message="未找到公司或岗位信息")

            # 读取前缀是（公司id_岗位id）的文件的地址
            rag_dir = Path(__file__).resolve().parent.parent / "store" / "job_rag"
            prefix = f"{company_id}_{job_id}_"
            files = list(rag_dir.glob(f"{prefix}*"))
            if not files:
                 return Result.fail(code=404, message=f"未找到题库文件，请先上传")
            milvus = MilvusDataBase(question_bank_collection)

            inserted=0
            all_chunks=0
            for file in files:
                """
                读取分割文本块split_words(文件地址)
                输出list[dict{"question": "问题", "answer": "答案","scoring_criteria": "评分标准","difficulty": "难度"}]
                """
                chunks = split_word(str(file))
                for item in chunks:
                    """
                    插入向量数据库题库
                    """
                    it=QuestionInput(
                        question=item["question"],
                        answer=item["answer"],
                        scoring_criteria=item["scoring_criteria"],
                        difficulty=item["difficulty"],
                        company_id=company_id,
                        job_id=job_id,
                        question_md5=hashlib.md5(f"{item['question']}_{job_id}".encode()).hexdigest(),
                        question_bank_partition=question_bank_partition,
                    )
                    is_insert = milvus._insert_job_question(it)
                    if is_insert:
                        inserted+=1
                    all_chunks+=1
            #删除文件
            for file in files:
                file.unlink()
            return Result.success(data={
                "insert": all_chunks, #插入总数
                "inserted": inserted,   #实际插入数
                "file_count": len(files),  #处理的文件数
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))
        
    def get_question(self, company_id: int, job_id: int, user_id: int,
                     page: int = 1, page_size: int = 20, role: str = None) -> Result:
        """分页获取某个岗位的题库问题"""
        try:
            question_bank_collection, question_bank_partition = (
                self.job_dao.get_question_bank_collection_and_partition(
                    company_id, job_id
                )
            )
            if not question_bank_collection or not question_bank_partition:
                return Result.fail(code=404, message="未找到公司或岗位信息")
            filter_expr = f'job_id == {job_id} and question_bank_partition == "{question_bank_partition}"'
            milvus_db = MilvusDataBase(question_bank_collection)

            # 查询总数
            total_hits = milvus_db._milvus.query(
                collection_name=question_bank_collection,
                filter=filter_expr,
                output_fields=["pk"],
            )
            total = len(total_hits)

            # 分页查询
            offset = (page - 1) * page_size
            hits = milvus_db._milvus.query(
                collection_name=question_bank_collection,
                filter=filter_expr,
                output_fields=["pk", "question", "answer", "scoring_criteria", "difficulty"],
                offset=offset,
                limit=page_size + 1,
                order_by="pk ASC",
            )
            has_more = len(hits) > page_size
            if has_more:
                hits = hits[:page_size]

            items = [
                {
                    "pk": h.get("pk"),
                    "question": h.get("question"),
                    "answer": h.get("answer"),
                    "scoring_criteria": h.get("scoring_criteria"),
                    "difficulty": h.get("difficulty"),
                }
                for h in hits
            ]

            return Result.success(data={
                "items": items,
                "total": total,
                "has_more": has_more,
                "page": page,
                "page_size": page_size,
                "question_bank_collection": question_bank_collection,
                "company_id": company_id,
            })
        except PermissionError as e:
            return Result.fail(code=403, message=str(e))
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def _get_question_collection(self, company_id: int, user_id: int,
                                  role: str) -> str | Result:
        """校验权限 + 获取公司题库集合名。失败返回 Result，成功返回 collection_name"""
        if err := self.access.can_operate_question(user_id, role, company_id):
            return err
        company = self.company_dao.get_company_by_id(company_id)
        if not company:
            return Result.fail(code=404, message="公司不存在")
        collection_name = company.get("question_bank_collection")
        if not collection_name:
            return Result.fail(code=404, message="该公司未创建题库")
        return collection_name

    def delete_question(self, company_id: int, pk: str, user_id: int, role: str = None) -> Result:
        """删除单道题目（通过主键 pk）"""
        try:
            collection_name = self._get_question_collection(company_id, user_id, role)
            if isinstance(collection_name, Result):
                return collection_name

            db = MilvusDataBase(collection_name)
            db._delete_question(pk)
            return Result.success(message="题目已删除")
        except PermissionError as e:
            return Result.fail(code=403, message=str(e))
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def update_question(self, company_id: int, pk: str, user_id: int,
                        question: str | None = None,
                        answer: str | None = None,
                        scoring_criteria: str | None = None,
                        difficulty: int | None = None, role: str = None) -> Result:
        """更新单道题目：先查出现有数据，合并更新字段，删旧插新"""
        try:
            collection_name = self._get_question_collection(company_id, user_id, role)
            if isinstance(collection_name, Result):
                return collection_name

            # 查出现有题目
            db = MilvusDataBase(collection_name)
            existing = db._get_question_by_pk(pk)
            if not existing:
                return Result.fail(code=404, message="题目不存在")

            # 3. 合并更新（传了就用新的，没传用旧的）
            merged_question = question if question is not None else existing.get("question", "")
            merged_answer = answer if answer is not None else existing.get("answer", "")
            merged_criteria = scoring_criteria if scoring_criteria is not None else existing.get("scoring_criteria", "")
            merged_difficulty = difficulty if difficulty is not None else existing.get("difficulty", 3)

            # 4. 删旧 + 重新向量化 + 插入
            db._update_question(
                pk=pk,
                partition=existing.get("question_bank_partition", ""),
                job_id=existing.get("job_id", 0),
                question=merged_question,
                answer=merged_answer,
                scoring_criteria=merged_criteria,
                difficulty=merged_difficulty,
            )
            return Result.success(message="题目已更新")
        except PermissionError as e:
            return Result.fail(code=403, message=str(e))
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def update_job(self, job_id: int, user_id: int,
                   title: str, description: str = None,
                   salary_min: int = None, salary_max: int = None,
                   location: str = None, category: str = None,
                   education_requirement: str = None,
                   experience_requirement: str = None,
                   headcount: int = 1, role: str = None) -> Result:
        """更新岗位信息"""
        try:
            job = self.job_dao.get_job_by_id(job_id)
            if not job:
                return Result.fail(code=404, message="岗位不存在")
            if err := self.access.can_operate_job(user_id, role, job.get("company_id", 0)):
                return err
            sets, params = build_set(
                title=title, description=description,
                salary_min=salary_min, salary_max=salary_max,
                location=location, category=category,
                education_requirement=education_requirement,
                experience_requirement=experience_requirement,
                headcount=headcount,
            )
            if not sets:
                return Result.fail(code=400, message="没有需要更新的字段")
            params.append(job_id)
            db.execute(f"UPDATE job_position SET {sets} WHERE id = %s", tuple(params))
            return Result.success(message="岗位已更新")
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def set_job_status(self, job_id: int, user_id: int, status: int,
                       role: str = None) -> Result:
        """设置岗位状态（1=上架, 2=下架）"""
        try:
            job = self.job_dao.get_job_by_id(job_id)
            if not job:
                return Result.fail(code=404, message="岗位不存在")
            if err := self.access.can_operate_job(user_id, role, job.get("company_id", 0)):
                return err
            db.execute("UPDATE job_position SET status = %s WHERE id = %s",
                       (status, job_id))
            action = "上架" if status == 1 else "下架"
            return Result.success(message=f"岗位已{action}")
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def delete_job_cascade(self, job_id: int, user_id: int, role: str = None) -> Result:
        """删除岗位：级联面试数据 → 删agent_config → 删MySQL → 清Milvus"""
        try:
            job = self.job_dao.get_job_by_id(job_id)
            if not job:
                return Result.fail(code=404, message="岗位不存在")
            company_id = job.get("company_id", 0)
            agent_config_id = job.get("agent_config_id")
            if err := self.access.can_operate_job(user_id, role, company_id):
                return err

            company = self.company_dao.get_company_by_id(company_id)
            collection_name = company.get("question_bank_collection", "official_job_question_bank") if company else "official_job_question_bank"

            # 1. 级联删除该岗位下所有面试数据
            try:
                interview_result = self.interview_dao.delete_sessions_by_job(job_id)
                _log.info("删除岗位级联: job_id=%s interviews=%s", job_id, interview_result)
            except Exception as e:
                _log.warning("面试数据删除失败(job_id=%s): %s", job_id, e)

            # 2. 删除岗位绑定的 agent_config
            if agent_config_id:
                try:
                    self.agent_dao.delete_config(agent_config_id)
                    _log.info("agent_config 已删除: id=%s", agent_config_id)
                except Exception as e:
                    _log.warning("agent_config 删除失败(job_id=%s config_id=%s): %s", job_id, agent_config_id, e)

            # 3. 删除 Milvus 题库中该岗位的所有题目
            try:
                milvus_q = MilvusDataBase(collection_name)
                milvus_q._delete_job_questions([job_id])
            except Exception as e:
                _log.warning(f"Milvus题库删除失败(job_id={job_id}): {e}")

            # 4. 删除 Milvus 岗位画像
            try:
                milvus_p = MilvusDataBase(settings.collection_name)
                milvus_p._delete_job_profiles([job_id])
            except Exception as e:
                _log.warning(f"Milvus画像删除失败(job_id={job_id}): {e}")

            # 5. 删除 MySQL 岗位数据
            self.job_dao.delete_job(job_id)
            return Result.success(message="岗位已删除")
        except Exception as e:
            return Result.fail(code=500, message=str(e))
