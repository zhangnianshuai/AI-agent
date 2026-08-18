from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from openai import OpenAI
from pymilvus import MilvusClient
# 找到项目根目录的 .env 文件
# server/config.py → 向上找到 AI-agent/.env
import os
from pathlib import Path


# 自动定位 .env：从当前文件向上找，直到找到 .env
_env_path = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = {
        "env_file": str(_env_path),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }
    # 数据库
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=3306, validation_alias="DB_PORT")
    db_user: str = Field(default="", validation_alias="DB_USER")
    db_password: str = Field(default="", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="", validation_alias="DB_NAME")

    # 应用
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8080, validation_alias="APP_PORT")
    app_debug: bool = Field(default=True, validation_alias="APP_DEBUG")

    # JWT
    jwt_secret_key: str = Field(default="change-me-in-production", validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, validation_alias="JWT_EXPIRE_MINUTES")

    # Milvus
    milvus_host: str = Field(default="localhost", validation_alias="MILVUS_HOST")
    milvus_port: int = Field(default=19530, validation_alias="MILVUS_PORT")
    milvus_username: str = Field(default="", validation_alias="MILVUS_USERNAME")
    milvus_password: str = Field(default="yourpassword", validation_alias="MILVUS_PASSWORD")
    milvus_db_name: str = Field(default="root", validation_alias="MILVUS_DB_NAME")

    collection_name: str = Field(default="job_profile", validation_alias="COLLECTION_NAME")

    # embedding 模型
    embedding_model: str = Field(default="text-embedding-v4", validation_alias="EMBEDDING_MODEL")
    embedding_api_key: str = Field(default="placeholder", validation_alias="DASHSCOPE_API_KEY")
    embedding_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", validation_alias="DASHSCOPE_API_URL")

    # OpenAI (DeepSeek)
    openai_api_key: str = Field(default="placeholder", validation_alias="DEEPSEEK_API_KEY")
    openai_model: str = Field(default="deepseek-v4-flash", validation_alias="OPENAI_MODEL")
    base_url: str = Field(default="https://api.deepseek.com", validation_alias="BASE_URL")

# 全局单例
settings = Settings(_env_file=_env_path)


# ── 客户端单例（懒加载，首次访问时初始化）────────────────

class _Clients:
    """API 客户端懒加载单例，避免 import 时阻塞启动。"""

    _llm: OpenAI | None = None
    _embedding: OpenAI | None = None
    _milvus_client: MilvusClient | None = None

    @property
    def llm(self) -> OpenAI:
        if self._llm is None:
            self._llm = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.base_url,
            )
        return self._llm

    @property
    def embedding(self) -> OpenAI:
        if self._embedding is None:
            self._embedding = OpenAI(
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_base_url,
            )
        return self._embedding

    @property
    def milvus_client(self) -> MilvusClient:
        if self._milvus_client is None:
            self._milvus_client = MilvusClient(
                uri=f"http://{settings.milvus_host}:{settings.milvus_port}",
                user=settings.milvus_username,
                password=settings.milvus_password,
                db_name=settings.milvus_db_name,
            )
        return self._milvus_client

clients = _Clients()


# ── 向后兼容：保留模块级访问（from server.config import llm）──

def __getattr__(name: str):
    """模块级懒加载兼容层，新代码推荐使用 clients.xxx 显式访问"""
    if name == "llm":
        return clients.llm
    if name == "embedding":
        return clients.embedding
    if name == "milvus_client":
        return clients.milvus_client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

