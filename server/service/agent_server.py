"""
AgentService — Agent 配置管理（通用 CRUD）

面试专用逻辑已迁至 service/interview_server.py 的 InterviewService 类中。
"""

from server.dao.database import db
from server.dao.agent_dao import AgentConfigDao
from server.dao.job_dao import JobDAO
from server.dao.company_dao import CompanyDao
from server.models.agent import agent_config
from server.models.result import Result
from server.utils.permission import AccessControl


class AgentService:
    """Agent 配置管理 —— 通用，同时被面试和 SQL Agent 使用"""

    def __init__(self):
        self.config_dao = AgentConfigDao()
        self.job_dao = JobDAO()
        self.access = AccessControl()

    # ═══════════════════════════════════════════════════════
    # Agent 配置 CRUD
    # ═══════════════════════════════════════════════════════

    def set_up_agent_config(self, job_id: int, config: agent_config,
                            config_id: int | None = None,
                            user: dict | None = None) -> Result:
        """创建或更新 Agent 配置并绑定到岗位。

        - config_id 非空 → 更新已有配置
        - config_id 为空 → 新建；SQL Admin 类型仅允许一条
        - job_id=0  → 仅创建/更新配置，不绑定岗位（SQL Admin 等场景）
        - user       → HR 用户时校验是否属于该岗位所属公司
        """
        try:
            # ── 公司级权限校验（HR 只能配置自己公司的岗位）──
            if user and job_id:
                role = user.get("role", "")
                user_id = user["id"]
                job = self.job_dao.get_job_by_id(job_id)
                if job is None:
                    return Result.fail(code=404, message=f"岗位不存在: id={job_id}")
                company_id = job.get("company_id")
                if company_id:
                    perm = self.access.can_operate_job(user_id, role, company_id)
                    if perm is not None:
                        return perm

            # ── 更新已有配置 ──
            if config_id:
                self.config_dao.update_config(config_id, config)
                return Result.success(data={
                    "agent_id": config_id, "job_id": job_id, "action": "updated",
                })

            # ── 新建配置 ──

            # SQL Admin 类型唯一性检查
            if config.type == "sql_admin":
                existing = self.config_dao.get_config_by_type("sql_admin")
                if existing:
                    return Result.fail(code=409, message="SQL 数据助手配置已存在，仅允许一条")

            # 面试配置：若岗位已有旧配置，先删旧
            if job_id:
                existing_id = self.job_dao.agent_config_id(job_id)
                if existing_id is not None:
                    self.config_dao.delete_config(existing_id)

            # 创建新配置 + 绑定岗位
            with db.transaction() as conn:
                self.config_dao.create_config(config, conn=conn)
                if job_id:
                    self.job_dao.update_agent_config_id(job_id, config.id, conn=conn)

            return Result.success(data={
                "agent_id": config.id, "job_id": job_id, "action": "created",
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def get_config(self, config_id: int) -> Result:
        try:
            cfg = self.config_dao.get_config_by_id(config_id)
            if cfg is None:
                return Result.fail(code=404, message=f"Agent配置不存在: id={config_id}")
            return Result.success(data=cfg.model_dump())
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def list_configs(self, user: dict | None = None) -> Result:
        """查询 Agent 配置列表。

        - admin → 查看全部
        - hr    → 仅查看自己所属公司的配置
        """
        try:
            rows = self.config_dao.list_configs_with_job_info()

            # HR 用户：只返回自己公司的配置
            if user:
                role = user.get("role", "")
                if role == "hr":
                    user_id = user["id"]
                    user_companies = CompanyDao().get_company_list_by_userId(user_id)
                    allowed_company_ids = {c["id"] for c in (user_companies or [])}
                    rows = [
                        r for r in rows
                        if r.get("company_id") is None or r.get("company_id") in allowed_company_ids
                    ]

            return Result.success(data=rows)
        except Exception as e:
            return Result.fail(code=500, message=str(e))
