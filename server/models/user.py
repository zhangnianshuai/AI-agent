from datetime import datetime
from server.models.base import BaseEntity


class User(BaseEntity):
    username: str
    password_hash: str
    real_name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    role: str | None='candidate'  # candidate / hr / admin
    status: int = 1
