import bcrypt
from server.dao.user_dao import UserDao
from server.models.result import Result
from server.utils.snowflake import snowflake
from server.utils.content_checker import validate_registration
from server.utils.auth import create_access_token
from server.models.request import UpdateUserInfoRequest


class UserService:

    def __init__(self):
        self.user_dao = UserDao()

    # ── bcrypt 工具方法 ──────────────────────────────────

    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=10),
        ).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    @staticmethod
    def _sanitize_contact(value: str | None) -> str | None:
        """空白字符串/纯空格视为 None"""
        if not value:
            return None
        v = value.strip()
        return v if v else None

    # ── 业务方法 ────────────────────────────────────────

    def register(self, username: str, password: str,
                 email: str = None, phone: str = None) -> Result:
        try:
            # 1.注册信息校验（校验失败时不访问数据库）
            validation_error = validate_registration(username, password)
            if validation_error:
                return Result.fail(code=400, message=validation_error)

            # 2.查重
            exist = self.user_dao.get_user_by_username(username)
            if exist:
                return Result.fail(code=409, message="用户名已存在")

            # 3.哈希加密
            password_hash = self._hash_password(password)

            # 4.生成 Snowflake ID
            user_id = snowflake.next_id()

            # 5.清洗邮箱/电话（空白字符串视为未填写）
            email = self._sanitize_contact(email)
            phone = self._sanitize_contact(phone)

            self.user_dao.create_user(user_id, username, password_hash, email, phone)

            return Result.success()
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def login(self, username: str, password: str) -> Result:
        try:
            user = self.user_dao.get_user_by_username(username)
            if not user or not self._verify_password(password, user["password_hash"]):
                return Result.fail(code=401, message="用户名或密码错误")

            if user.get("status") == 0:
                return Result.fail(code=403, message="账号已被禁用，请联系管理员")

            token=create_access_token(user["id"], user["username"], user["role"])
            return Result.success(data={"token": token})
        except Exception as e:
            return Result.fail(code=500, message=str(e))
        
    def get_user_by_id(self, user_id: int) -> Result:
        try:
            user = self.user_dao.get_user_by_id(user_id)
            if not user:
                return Result.fail(code=404, message="用户不存在")
            user["password_hash"]=None
            return Result.success(data=user)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def update_profile(self, user_id: int, req: UpdateUserInfoRequest) -> Result:
        try:
            user = self.user_dao.get_user_by_id(user_id)
            if not user:
                return Result.fail(code=404, message="用户不存在")
        
            # 清洗输入：空字符串/纯空格视为 None（支持清空字段）
            new_email = self._sanitize_contact(req.email)
            new_phone = self._sanitize_contact(req.phone)

            if new_email and new_email != user.get("email"):
                exist = self.user_dao.get_user_by_email(new_email)
                if exist:
                    return Result.fail(code=409, message="该邮箱已被使用")

            if new_phone and new_phone != user.get("phone"):
                exist = self.user_dao.get_user_by_phone(new_phone)
                if exist:
                    return Result.fail(code=409, message="该手机号已被使用")

            rows = self.user_dao.update_user_profile(
                user_id=user_id,
                real_name=req.real_name,
                email=new_email,
                phone=new_phone,
                avatar_url=req.avatar_url,
            )

            if rows == 0:
                return Result.success(message="没有需要更新的字段")
        
            updated_user = self.user_dao.get_user_by_id(user_id)
            updated_user["password_hash"] = None  # 脱敏
            return Result.success(data=updated_user)
        
        except Exception as e:
            return Result.fail(code=500, message=str(e))
    
    def update_password(self, user_id: int, old_password: str, new_password: str) -> Result:
        try:
            user = self.user_dao.get_user_by_id(user_id)
            if not user:
                return Result.fail(code=404, message="用户不存在")

            if not self._verify_password(old_password, user["password_hash"]):
                return Result.fail(code=401, message="旧密码错误")

            validation_error = validate_registration(username=user["username"], password=new_password)
            if validation_error:
                return Result.fail(code=400, message=validation_error)

            new_password_hash = self._hash_password(new_password)

            self.user_dao.update_password(user_id, new_password_hash)
            return Result.success(message="密码更新成功")
        except Exception as e:
            return Result.fail(code=500, message=str(e))
