"""Milvus 操作的数据模型 — 输入/输出类型约束"""

from typing import Optional

from pydantic import BaseModel


class QuestionInput(BaseModel):
    """题库插入"""
    question: str
    answer: str = ""
    scoring_criteria: Optional[str] = None
    difficulty: int = 3
    job_id: int = 0
    company_id: int = 0
    question_md5: str = ""
    question_bank_partition: str = ""


class QuestionHit(BaseModel):
    """题库搜索结果"""
    pk: int
    question: str
    answer: str = ""
    difficulty: int = 0
    job_id: int = 0
    company_id: int = 0
    score: float = 0.0


class JobProfileInput(BaseModel):
    """岗位画像插入"""
    job_id: int
    profile_text: str
    company_id: int = 0


class JobHit(BaseModel):
    """岗位画像搜索结果"""
    job_id: int | None = None
    company_id: int = 0
    text: str = ""
    score: float = 0.0


class RagHit(BaseModel):
    """RAG 检索结果"""
    content: str
    metadata: dict = {}
