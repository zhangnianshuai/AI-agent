from .interview_constant import (
    # ── WS 标记 ──
    STREAM_START,
    STREAM_END,
    KEEPALIVE,
    # ── Prompt 模板 ──
    WELCOME,
    FIRST_Q,
    NEXT_Q,
    FINAL_EVAL_PROMPT,
    EARLY_EXIT_PROMPT,
    SCORE_PROMPT,
    # ── 面试配置 ──
    EXIT_KW,
    RECV_TO,
    CONFIRM_TO,
    REPORT_TO,
    ANSWER_MAX,
    QNS_MAX,
)
from .agent_constant import SCORE_PATTERN, SYSTEM_PROMPT
from .sql_agent_constant import SQL_SYSTEM_PROMPT

__all__ = [
    "STREAM_START", "STREAM_END", "KEEPALIVE",
    "WELCOME", "FIRST_Q", "NEXT_Q",
    "FINAL_EVAL_PROMPT", "EARLY_EXIT_PROMPT", "SCORE_PROMPT",
    "EXIT_KW", "RECV_TO", "CONFIRM_TO", "REPORT_TO",
    "ANSWER_MAX", "QNS_MAX",
    "SCORE_PATTERN", "SYSTEM_PROMPT",
    "SQL_SYSTEM_PROMPT",
]
