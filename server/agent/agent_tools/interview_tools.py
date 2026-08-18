"""
面试工具 — Agent 可直接调用的 MySQL 写入工具
  - save_interview_record: 保存每题问答记录（带去重）
  - save_interview_evaluation: 保存最终评价
"""

import json
import logging
from contextvars import ContextVar

from langchain_core.tools import tool
from server.dao.database import db

_log = logging.getLogger(__name__)

_current_session_ctx: ContextVar[int] = ContextVar("interview_session_id", default=0)


def set_interview_session(session_id: int):
    """API 层调用：注入当前协程的面试 session_id"""
    _current_session_ctx.set(session_id)


@tool
def save_interview_record(
    session_id: int,
    round_number: int,
    question: str,
    answer: str,
    question_type: str = "",
    score: float = None,
    comment: str = "",
) -> str:
    """保存面试中每一轮的问答记录到 interview_record 表。

    每问完一道题就要调用一次。不需要手动解析 JSON，直接传参即可。

    Args:
        session_id: 面试会话ID（必填）
        round_number: 第几轮/题号（必填，从1开始）
        question: 面试官提问内容（必填）
        answer: 候选人回答内容（必填）
        question_type: 题型（可选：self_intro/project/technical/behavioral/qa）
        score: 得分 0-100（可选，不确定可不传）
        comment: AI 点评（可选）
    """
    try:
        # 优先级：ContextVar > LLM 传参；sid 必须 >0
        sid = _current_session_ctx.get() or session_id
        if not sid or sid <= 0:
            return json.dumps({"error": "缺少有效的 session_id"}, ensure_ascii=False)
        _log.info("save record: sid=%s round=%s score=%s answer_len=%s",
                  sid, round_number, score, len(answer) if answer else 0)

        db.execute(
            "INSERT INTO interview_record"
            " (session_id, round_number, question, answer, question_type, score, comment)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (sid, round_number, question, answer,
             question_type or None, score, comment or None),
        )
        return json.dumps(
            {"ok": True, "message": f"第{round_number}轮记录已保存"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def save_interview_evaluation(
    session_id: int,
    total_score: float,
    is_pass: bool,
    summary: str,
    strengths: str = "",
    weaknesses: str = "",
    suggestion: str = "",
) -> str:
    """保存面试最终评价到 interview_evaluation 表。

    所有题目问完后调用一次。不需要手动解析 JSON，直接传参即可。

    Args:
        session_id: 面试会话ID（必填）
        total_score: 综合得分 0-100（必填）
        is_pass: 是否建议通过（必填，true/false）
        summary: 综合评价总结（必填，100-300字）
        strengths: 优势亮点（可选，100字以内）
        weaknesses: 不足之处（必填，100字左右）
        suggestion: 改进建议（必填，200字左右）
    """
    try:
        sid = _current_session_ctx.get() or session_id
        if not sid or sid <= 0:
            return json.dumps({"error": "缺少有效的 session_id"}, ensure_ascii=False)
        db.execute(
            "DELETE FROM interview_evaluation WHERE session_id = %s",
            (sid,),
        )
        db.execute(
            "INSERT INTO interview_evaluation"
            " (session_id, total_score, is_pass, summary, strengths, weaknesses, suggestion)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (sid, total_score, 1 if is_pass else 0,
             summary, strengths or None, weaknesses or None, suggestion or None),
        )
        return json.dumps(
            {"ok": True, "message": f"最终评价已保存，总分{total_score}，{'通过' if is_pass else '未通过'}"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
