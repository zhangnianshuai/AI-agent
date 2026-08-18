from datetime import datetime
from typing import Optional
from enum import Enum
from server.models.base import BaseEntity


class AgentType(str, Enum):
    interview = "interview"
    sql_admin = "sql_admin"


class agent_config(BaseEntity):
    type: AgentType = AgentType.interview
    model_name: Optional[str] = "deepseek-v4-flash"
    temperature: Optional[float] = 0.70
    max_tokens: Optional[int] = 4096
    system_prompt: Optional[str] = None
    ranker_params: Optional[int] = 5             # interview 专用
    score_threshold: Optional[float] = 0.70      # interview 专用
    question_nums: Optional[int] = 10            # interview 专用

class SessionStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class InterviewSession(BaseEntity):
    """对应 interview_session 表"""
    user_id: int
    job_position_id: int
    agent_config_id: int
    resume_id: Optional[int] = None
    company_id: Optional[int] = None
    status: str = "pending"       # pending | in_progress | completed | cancelled
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[int] = None

class InterviewRecord(BaseEntity):
    """对应 interview_record 表（一问一答明细）"""
    session_id: int
    round_number: int = 1
    question_type: Optional[str] = None   # self_intro | project | technical | behavioral | qa
    question: str
    answer: Optional[str] = None
    score: Optional[float] = None         # 0-100
    comment: Optional[str] = None         # AI 点评
    duration: Optional[int] = None

class InterviewEvaluation(BaseEntity):
    """对应 interview_evaluation 表（最终评价）"""
    session_id: int
    total_score: Optional[float] = None
    summary: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    suggestion: Optional[str] = None
    is_pass: Optional[bool] = None