from datetime import datetime, timedelta, timezone
from functools import wraps
from fastapi import Request, HTTPException
from jose import JWTError, jwt
from server.config import settings
from server.dao.user_dao import UserDao

_ROLE_LABELS = {"admin": "管理员", "hr": "HR", "candidate": "候选人"}

def _role_label(role: str) -> str:
    return _ROLE_LABELS.get(role, role)


def create_access_token(user_id: int, username: str, role: str) -> str:
    """生成 JWT Token 把角色信息写进 payload"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """解析 JWT Token"""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None


def get_current_user(request: Request) -> dict:
    """从请求头提取 Token 并解析成用户字典"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证 Token")

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    # 可选：回库校验用户是否被禁用
    user = UserDao().get_user_by_id(user_id)
    if not user or user.get("status") != 1:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")

    # 安全：不泄露密码哈希
    user.pop("password_hash", None)
    return user


def extract_ws_token(websocket) -> str | None:
    """从 WebSocket 连接中提取 Bearer token。

    优先取 query string 中的 token 参数，其次从 Authorization header 解析。
    返回 token 字符串或 None。
    """
    token = websocket.query_params.get("token", "")
    if token:
        return token

    auth = websocket.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return auth or None


def get_optional_user(request: Request) -> dict | None:
    """尝试从请求头提取 Token，解析失败不抛异常，返回 None"""
    try:
        return get_current_user(request)
    except HTTPException:
        return None


def require_role(*allowed_roles: str):
    """
    权限装饰器(FastAPI Depends 用)
    用法:user: dict = Depends(require_role("admin"))
    """
    def dependency(request: Request) -> dict:
        user = get_current_user(request)
        if user["role"] not in allowed_roles:
            allowed_labels = [_role_label(r) for r in allowed_roles]
            raise HTTPException(
                status_code=403,
                detail=f"权限不足，需要角色: {allowed_labels}，当前角色: {_role_label(user['role'])}"
            )
        return user
    return dependency