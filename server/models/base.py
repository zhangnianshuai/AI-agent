from datetime import datetime
from pydantic import BaseModel, Field
from server.utils.snowflake import snowflake


class BaseEntity(BaseModel):
    id: int = Field(default_factory=snowflake.next_id)

    # 这两个由数据库自动维护，模型只负责接收，不给默认值
    created_at: datetime | None = None
    updated_at: datetime | None = None

    deleted_at: datetime | None = None  # 需要表里有这个字段

    model_config = {"from_attributes": True}
