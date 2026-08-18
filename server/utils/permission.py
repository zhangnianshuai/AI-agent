"""
统一权限鉴定器 — 所有资源级权限判断收口于此。

约定：每个方法返回 Result | None
  - 返回 None  → 鉴定通过，放行
  - 返回 Result → 鉴定拒绝，调用方直接 return err
"""

from server.models.result import Result
from server.dao.company_dao import CompanyDao


class AccessControl:
    """权限鉴定器，无状态，可在 Service 中作为成员复用"""

    def __init__(self, company_dao: CompanyDao | None = None):
        self._cd = company_dao or CompanyDao()

    # ═══════════════════════════════════════════════════════
    # 公司资源权限（岗位、题库同理 — 都按公司归属判断）
    # ═══════════════════════════════════════════════════════

    def can_operate_company(self, user_id: int, role: str, company_id: int) -> Result | None:
        """
        admin  → 直接放行
        hr     → 需在 user_company 表有该公司的关联记录
        其他   → 拒绝
        """
        if role == "admin":
            return None
        if role == "hr" and self._cd.check_user_in_company(user_id, company_id):
            return None
        return Result.fail(code=403, message="无权操作该公司")

    # 语义别名 — 实际逻辑完全一致，命名区分让调用方更可读
    def can_operate_job(self, user_id: int, role: str, company_id: int) -> Result | None:
        return self.can_operate_company(user_id, role, company_id)

    def can_operate_question(self, user_id: int, role: str, company_id: int) -> Result | None:
        return self.can_operate_company(user_id, role, company_id)

    # ═══════════════════════════════════════════════════════
    # 面试资源权限
    # ═══════════════════════════════════════════════════════

    def can_operate_interview(self, user_id: int, role: str, owner_id: int) -> Result | None:
        """
        candidate → 只能操作自己的面试记录
        hr/admin  → 无限制
        """
        if role == "candidate" and user_id != owner_id:
            return Result.fail(code=403, message="无权操作此面试记录")
        return None

    # ═══════════════════════════════════════════════════════
    # 角色校验
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def require_roles(role: str, *allowed: str) -> Result | None:
        """角色白名单检查 — 不在列表则拒绝"""
        if role not in allowed:
            labels = {
                "admin": "管理员", "hr": "HR", "candidate": "候选人",
            }
            allowed_labels = [labels.get(r, r) for r in allowed]
            return Result.fail(code=403, message=f"权限不足，需要角色: {allowed_labels}")
        return None

    @staticmethod
    def require_admin(role: str) -> Result | None:
        """仅管理员"""
        if role != "admin":
            return Result.fail(code=403, message="仅管理员可操作")
        return None
