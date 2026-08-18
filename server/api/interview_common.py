"""
面试 WebSocket 共享初始化 — 消除 interview_api / voice_interview_api 间的重复代码

提取 token 鉴权 → 上下文加载 → session+Agent 并行初始化。
"""

import asyncio
import logging
from typing import Callable, Awaitable

from fastapi import WebSocket

from server.service.interview_server import InterviewService
from server.agent.interview_agent import InterviewAgent
from server.utils.auth import decode_token
from server.constant import QNS_MAX

_log = logging.getLogger(__name__)

# send_error: async callback(code: int, message: str) → None
SendError = Callable[[int, str], Awaitable[None]]


async def init_interview_ws(
    websocket: WebSocket,
    job_id: int,
    send_error: SendError,
    service: InterviewService,
) -> dict | None:
    """WebSocket 面试初始化公共流程。

    顺序：
      1. WS token 鉴权
      2. 加载面试上下文（岗位/简历/公司/Agent 配置）
      3. session + Agent 并行初始化

    Args:
        websocket: 已 accept 的 WebSocket
        job_id: 岗位 ID
        send_error: 发送错误并关闭连接的异步回调
        service: InterviewService 实例

    Returns:
        {
            "user_id", "cfg", "job_info", "resume_info", "company_info",
            "collection_name", "question_partition",
            "agent", "session_id", "session",
        }
        失败返回 None（已通过 send_error 通知前端并关闭连接）
    """

    # ── 1. 鉴权 ──────────────────────────────────────────
    from server.utils.auth import extract_ws_token
    token = extract_ws_token(websocket)
    if not token:
        _log.warning("[CKPT-AUTH] 缺少 token")
        await send_error(4001, "缺少认证 token")
        return None

    payload = decode_token(token)
    if not payload:
        _log.warning("[CKPT-AUTH] token 无效")
        await send_error(4001, "token 无效或已过期")
        return None

    user_id = payload["user_id"]
    _log.info("[CKPT-AUTH] user_id=%s job_id=%s", user_id, job_id)

    # ── 2. 加载上下文 ────────────────────────────────────
    _log.info("[CKPT-CTX] 加载面试上下文...")
    try:
        ctx = service.prepare_interview_context(user_id, job_id)
    except ValueError as e:
        _log.warning("[CKPT-CTX] 上下文加载失败: %s", e)
        await send_error(4000, str(e))
        return None

    cfg = ctx["agent_config"]
    if not (1 <= cfg.question_nums <= QNS_MAX):
        _log.warning("[CKPT-CTX] 题目数量异常: %s", cfg.question_nums)
        await send_error(4000, f"面试题目数量配置异常（需在 1~{QNS_MAX} 之间）")
        return None

    job_info = ctx["job_info"]
    resume_info = ctx["resume_info"]
    company_info = ctx["company_info"]
    collection_name = company_info.get("question_bank_collection", "official_job_question_bank")
    question_partition = job_info.get("question_bank_partition")
    _log.info("[CKPT-CTX] 加载完成 job=%s resume=%s collection=%s partition=%s qns=%s",
              job_info.get("title"), bool(resume_info), collection_name, question_partition, cfg.question_nums)

    # ── 3. session + Agent 并行初始化 ────────────────────
    agent = InterviewAgent(cfg, job_info, resume_info, collection_name, question_partition)
    _log.info("[CKPT-INIT] 并行初始化 session + agent...")

    loop = asyncio.get_running_loop()
    session_future = loop.run_in_executor(
        None,
        service.start_session,
        user_id, job_id, cfg.id,
        resume_info["id"] if resume_info else None,
        job_info.get("company_id"),
    )
    init_task = asyncio.create_task(agent.init())

    try:
        session_id, session = await session_future
        _log.info("[CKPT-INIT] session_id=%s 创建成功", session_id)
    except Exception:
        _log.exception("[CKPT-INIT] session 创建失败")
        init_task.cancel()
        agent.close()
        await send_error(4000, "创建面试会话失败，请稍后重试")
        return None

    try:
        await init_task
        _log.info("[CKPT-INIT] Agent 初始化完成")
    except Exception:
        _log.exception("[CKPT-INIT] Agent 初始化失败")
        service.cancel_session(session_id, session.start_time)
        agent.close()
        await send_error(4000, "AI 面试官初始化失败，请稍后重试")
        return None

    return {
        "user_id": user_id,
        "cfg": cfg,
        "job_info": job_info,
        "resume_info": resume_info,
        "company_info": company_info,
        "collection_name": collection_name,
        "question_partition": question_partition,
        "agent": agent,
        "session_id": session_id,
        "session": session,
    }
