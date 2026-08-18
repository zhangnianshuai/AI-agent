"""
InterviewService — 面试业务逻辑

从 service/agent_server.py 迁出，包含：
  - 面试上下文加载（prepare_interview_context）
  - 会话生命周期（start/cancel/complete）
  - 问答记录（save_answer）
  - 评分回填（fill_score）
  - 报告查询（get_interview_report/record）
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

_log = logging.getLogger(__name__)

# 模块级共享线程池（避免每次请求创建/销毁）
_executor = ThreadPoolExecutor(max_workers=8)


def shutdown_executor():
    """关闭模块级线程池，应在应用 shutdown 事件中调用"""
    _executor.shutdown(wait=True)

from server.dao.database import db
from server.utils.permission import AccessControl
from server.dao.agent_dao import AgentConfigDao
from server.dao.interview_dao import InterviewDao
from server.dao.job_dao import JobDAO
from server.dao.resume_dao import ResumeDao
from server.models.agent import (
    InterviewEvaluation,
    InterviewRecord,
    InterviewSession,
)
from server.models.result import Result


class InterviewService:
    """面试业务逻辑"""

    def __init__(self):
        self.config_dao = AgentConfigDao()
        self.job_dao = JobDAO()
        self.interview_dao = InterviewDao()
        self.resume_dao = ResumeDao()
        self.access = AccessControl()

    # ═══════════════════════════════════════════════════════
    # 面试前 — 上下文加载
    # ═══════════════════════════════════════════════════════

    def prepare_interview_context(self, user_id: int, job_id: int) -> dict:
        """并行加载面试上下文数据，减少 DB 往返延迟。

        流程（最大并行度）：
          1. 同时提交 job / config / resume 到线程池
          2. job 先返回后，立即提交 company 查询
          3. config、resume、company 三种查询在池中并行执行
        """

        def _load_job():
            job = self.job_dao.get_job_by_id(job_id)
            if not job:
                raise ValueError("该岗位不存在")
            return job

        def _load_config():
            config = self.config_dao.get_config_by_job_id(job_id)
            if not config:
                raise ValueError("该岗位尚未配置AI面试官，请联系管理员")
            return config

        def _load_resume():
            resume = self.resume_dao.get_resume_by_id(user_id)
            if not resume:
                raise ValueError("请先上传简历后再参加面试")
            return resume

        def _load_company(company_id: int):
            company = db.query(
                "SELECT id, name, short_name, industry, scale, address, website,"
                " logo_url, description, contact_person, contact_phone, status,"
                " question_bank_collection"
                " FROM company WHERE id = %s",
                params=(company_id,), one=True
            )
            if not company:
                raise ValueError("该岗位所属企业不存在，请联系管理员")
            return company

        pool = _executor

        # 阶段 1：同时提交 job + config + resume
        job_f = pool.submit(_load_job)
        config_f = pool.submit(_load_config)
        resume_f = pool.submit(_load_resume)

        # 阶段 2：等 job 返回后立即提交 company（config/resume 仍在并行执行）
        job = job_f.result()
        cid = job.get("company_id")
        if not cid:
            raise ValueError("该岗位所属企业不存在，请联系管理员")
        company_f = pool.submit(_load_company, cid)

        # 阶段 3：收集所有结果（阻塞等待尚未完成的任务）
        config = config_f.result()
        resume = resume_f.result()
        company = company_f.result()

        return {
            "agent_config": config,
            "job_info": job,
            "resume_info": resume,
            "company_info": company,
        }

    # ═══════════════════════════════════════════════════════
    # 面试中 — Session / Record
    # ═══════════════════════════════════════════════════════

    def start_session(self, user_id: int, job_id: int, agent_config_id: int,
                      resume_id: int | None, company_id: int | None) -> tuple[int, InterviewSession]:
        """创建面试会话，返回 (session_id, session)"""
        session = InterviewSession(
            user_id=user_id,
            job_position_id=job_id,
            agent_config_id=agent_config_id,
            resume_id=resume_id,
            company_id=company_id,
            status="in_progress",
            start_time=datetime.now(),
        )
        self.interview_dao.create_session(session)
        return session.id, session

    def cancel_session(self, session_id: int, start_time: datetime | None = None):
        """将面试标记为已取消"""
        now = datetime.now()
        fields = {"status": "cancelled", "end_time": now}
        if start_time:
            fields["duration"] = int((now - start_time).total_seconds())
        self.interview_dao.update_session(session_id, **fields)

    def complete_session(self, session_id: int, start_time: datetime,
                         eval_data: dict) -> InterviewEvaluation:
        """完成面试：更新 session 状态 + 写入最终评价"""
        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds())
        self.interview_dao.update_session(
            session_id, status="completed", end_time=end_time, duration=duration
        )
        evaluation = InterviewEvaluation(
            session_id=session_id,
            total_score=eval_data.get("total_score"),
            summary=eval_data.get("summary"),
            strengths=eval_data.get("strengths"),
            weaknesses=eval_data.get("weaknesses"),
            suggestion=eval_data.get("suggestion"),
            is_pass=eval_data.get("is_pass"),
        )
        self.interview_dao.create_evaluation(evaluation)
        return evaluation

    def save_answer(self, session_id: int, round_number: int,
                    question: str, answer: str, duration: int,
                    score: float | None = None,
                    question_type: str | None = None,
                    comment: str | None = None) -> InterviewRecord:
        """创建一条问答记录"""
        record = InterviewRecord(
            session_id=session_id,
            round_number=round_number,
            question=question,
            answer=answer,
            duration=duration,
            score=score,
            question_type=question_type,
            comment=comment,
        )
        self.interview_dao.create_record(record)
        return record

    # ═══════════════════════════════════════════════════════
    # 面试后 — 列表 + 报告
    # ═══════════════════════════════════════════════════════

    def list_sessions(self, user: dict, page: int = 1, page_size: int = 20) -> Result:
        """分页返回面试会话列表。candidate 只看自己的，hr/admin 看全部"""
        try:
            user_id = user["id"] if user["role"] == "candidate" else None
            sessions = self.interview_dao.list_recent_sessions(
                user_id=user_id, page=page, page_size=page_size,
            )
            total = self.interview_dao.count_sessions(user_id=user_id)
            return Result.success(data={
                "items": sessions,
                "total": total,
                "page": page,
                "page_size": page_size,
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def get_interview_report(self, session_id: int, user: dict) -> Result:
        """查询完整面试报告（session + 逐题记录 + 最终评价），candidate 只能看自己的"""
        try:
            data = self.interview_dao.get_full_report(session_id)
            if not data:
                return Result.fail(code=404, message="面试记录不存在")

            session = data.get("session", {})
            if err := self.access.can_operate_interview(user["id"], user["role"], session.get("user_id", 0)):
                return err

            return Result.success(data=data)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def delete_session(self, session_id: int, user: dict) -> Result:
        """级联删除面试会话：records → evaluation → session"""
        try:
            session = self.interview_dao.get_session_by_id(session_id)
            if not session:
                return Result.fail(code=404, message="面试记录不存在")
            if err := self.access.can_operate_interview(user["id"], user["role"], session.get("user_id", 0)):
                return err
            with db.transaction() as conn:
                self.interview_dao.delete_session_cascade(session_id, conn)
            return Result.success(message="面试记录已删除")
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    # ═══════════════════════════════════════════════════════
    # 候选人管理（公司 HR / admin）
    # ═══════════════════════════════════════════════════════

    def list_company_candidates(self, company_id: int, user: dict,
                                is_pass: int = None, job_title: str = None,
                                job_location: str = None,
                                page: int = 1, page_size: int = 20) -> Result:
        """查询公司候选人列表。admin 看全部公司，hr 只能看自己关联的公司"""
        try:
            if err := self.access.can_operate_company(
                user["id"], user["role"], company_id,
            ):
                return err

            filters = {}
            if is_pass is not None:
                filters["is_pass"] = is_pass
            if job_title:
                filters["job_title"] = job_title
            if job_location:
                filters["job_location"] = job_location

            items = self.interview_dao.list_company_candidates(
                company_id, page=page, page_size=page_size, **filters,
            )
            total = self.interview_dao.count_company_candidates(
                company_id, **filters,
            )
            return Result.success(data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def set_candidate_pass(self, session_id: int, is_pass: int,
                           user: dict) -> Result:
        """修改候选人面试通过状态。复用 can_operate_interview 权限"""
        try:
            session = self.interview_dao.get_session_by_id(session_id)
            if not session:
                return Result.fail(code=404, message="面试记录不存在")
            if err := self.access.can_operate_interview(
                user["id"], user["role"], session.get("user_id", 0),
            ):
                return err
            self.interview_dao.update_evaluation_pass(session_id, is_pass)
            if is_pass is None:
                action = "待评价"
            elif is_pass:
                action = "通过"
            else:
                action = "未通过"
            return Result.success(message=f"已标记为{action}")
        except Exception as e:
            return Result.fail(code=500, message=str(e))
