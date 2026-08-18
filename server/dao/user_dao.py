from server.dao.database import db
from server.utils.sql_builder import build_set, build_where

class UserDao:

    # 统一字段列表，所有按用户查询共用
    _USER_FIELDS = (
        "id, username, password_hash, real_name, email, phone, avatar_url,"
        " role, status, created_at, updated_at"
    )

    def _get_user_by_field(self, field: str, value) -> dict | None:
        """按指定字段查询用户，返回用户 dict 或 None"""
        sql = f"SELECT {self._USER_FIELDS} FROM user WHERE {field} = %s"
        return db.query(sql, params=(value,), one=True)

    def get_user_by_username(self, username: str) -> dict | None:
        return self._get_user_by_field("username", username)

    def get_user_by_id(self, user_id: int) -> dict | None:
        return self._get_user_by_field("id", user_id)

    def get_user_by_email(self, email: str) -> dict | None:
        return self._get_user_by_field("email", email)

    def get_user_by_phone(self, phone: str) -> dict | None:
        return self._get_user_by_field("phone", phone)

    def create_user(self, user_id: int, username: str, password_hash: str,
                    email: str = None, phone: str = None) -> int:
        """
        创建用户
        :param user_id: 用户id
        :param username: 用户名
        :param password_hash: 密码hash
        :param email: 邮箱
        :param phone: 手机号
        :return: 创建结果
        """
        sql = """INSERT INTO user (id, username, password_hash, email, phone, role)
                 VALUES (%s, %s, %s, %s, %s, 'candidate')"""
        return db.execute(sql, (user_id, username, password_hash, email, phone))
    
    def update_user_role(self, user_id: int, new_role: str) -> int:
        """修改用户角色"""
        sql = "UPDATE user SET role = %s WHERE id = %s"
        return db.execute(sql, (new_role, user_id))

    def update_user_status(self, user_id: int, status: int) -> int:
        """封禁/解封用户  status: 0=禁用, 1=正常"""
        sql = "UPDATE user SET status = %s WHERE id = %s"
        return db.execute(sql, (status, user_id))

    _USER_LIST_FIELDS = (
        "id, username, real_name, email, phone, role, status, created_at"
    )
    _USER_FILTER_MAP = {"role": "role = %s", "status": "status = %s"}

    def list_users(self, role: str = None, status: int = None,
                   page: int = 1, page_size: int = 20) -> list:
        """分页查询用户列表，支持按角色和状态筛选"""
        offset = (page - 1) * page_size
        where, params = build_where({"role": role, "status": status}, self._USER_FILTER_MAP)
        sql = (f"SELECT {self._USER_LIST_FIELDS} FROM user {where}"
               f" ORDER BY created_at DESC LIMIT %s OFFSET %s")
        params.extend([page_size, offset])
        return db.query(sql, params=tuple(params))

    def count_users(self, role: str = None, status: int = None) -> int:
        """统计用户数量"""
        where, params = build_where({"role": role, "status": status}, self._USER_FILTER_MAP)
        sql = f"SELECT COUNT(*) as total FROM user {where}"
        result = db.query(sql, params=tuple(params) if params else None, one=True)
        return result["total"] if result else 0
        
    def update_user_profile(self, user_id: int, real_name: str = None,
                        email: str = None, phone: str = None,
                        avatar_url: str = None) -> int:
        """更新用户个人信息"""
        sets, params = build_set(
            real_name=real_name, email=email, phone=phone, avatar_url=avatar_url,
        )
        if not sets:
            return 0
        params.append(user_id)
        return db.execute(f"UPDATE user SET {sets} WHERE id = %s", tuple(params))   
    
    def update_password(self, user_id: int, new_password_hash: str) -> int:
        """
        更新用户密码  
        :param new_password_hash: 新密码hash  
        :return: 更新结果  
        """
        sql = "UPDATE user SET password_hash = %s WHERE id = %s"
        return db.execute(sql, (new_password_hash, user_id))
