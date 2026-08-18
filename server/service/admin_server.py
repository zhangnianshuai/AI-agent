from server.dao.user_dao import UserDao
from server.models.result import Result


class AdminService:
    """管理员业务 — 用户权限管理"""

    def __init__(self):
        self.user_dao = UserDao()

    def update_user_status(self, admin_user_id: int, target_user_id: int, status: int) -> Result:
        """管理员封禁/解封用户  status: 0=禁用, 1=正常"""
        try:
            if status not in (0, 1):
                return Result.fail(code=400, message="无效状态值，可选: 0(禁用), 1(正常)")

            target = self.user_dao.get_user_by_id(target_user_id)
            if not target:
                return Result.fail(code=404, message="目标用户不存在")

            if admin_user_id == target_user_id:
                return Result.fail(code=400, message="不能封禁/解封自己")

            if target["role"] == "admin":
                return Result.fail(code=403, message="不能封禁管理员账号")

            rows = self.user_dao.update_user_status(target_user_id, status)
            if rows == 0:
                return Result.fail(code=500, message="更新失败，请重试")

            action = "解封" if status == 1 else "封禁"
            return Result.success(data={
                "user_id": target_user_id,
                "status": status,
                "action": action,
                "updated_by": admin_user_id
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def update_user_role(self, admin_user_id: int, target_user_id: int, new_role: str) -> Result:
        """管理员修改用户角色"""
        try:
            valid_roles = ("candidate", "hr", "admin")
            if new_role not in valid_roles:
                return Result.fail(code=400, message=f"无效角色，可选: 候选人、HR、管理员")

            target = self.user_dao.get_user_by_id(target_user_id)
            if not target:
                return Result.fail(code=404, message="目标用户不存在")

            if admin_user_id == target_user_id:
                return Result.fail(code=400, message="不能修改自己的角色")

            rows = self.user_dao.update_user_role(target_user_id, new_role)
            if rows == 0:
                return Result.fail(code=500, message="更新失败，请重试")

            return Result.success(data={
                "user_id": target_user_id,
                "old_role": target["role"],
                "new_role": new_role,
                "updated_by": admin_user_id
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def list_users(self, role: str = None, status: int = None,
                   page: int = 1, page_size: int = 20) -> Result:
        """查询用户列表（支持按角色和状态筛选）"""
        try:
            users = self.user_dao.list_users(role=role, status=status,
                                              page=page, page_size=page_size)
            total = self.user_dao.count_users(role=role, status=status)
            return Result.success(data={
                "list": users,
                "total": total,
                "page": page,
                "page_size": page_size
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))