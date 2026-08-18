"""
SQL Agent API — 管理员数据库助手接口

会话生命周期：
  1. 前端打开页面 → GET /status 查询是否有活跃 Agent
  2. 有 → 弹窗"是否恢复历史记录?"
     - 是 → GET /messages 获取历史 → 前端渲染 → 连接 WS
     - 否 → POST /messages/clear 或 DELETE /reset → 连接 WS（全新）
  3. 无 → 直接连接 WS

WebSocket 断开时：
  - "关闭本次会话" → 仅断开 WS，Agent 保留（30min 超时自动清理）
  - "关闭 Agent"  → 断开 WS + DELETE /reset 销毁
"""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import JSONResponse

from server.models.result import Result
from server.service.sql_agent_server import sql_agent_service as _svc
from server.utils.auth import decode_token
from server.utils.permission import AccessControl

router = APIRouter(prefix="/agent/sql", tags=["sql_agent"])



def _auth(token: str) -> dict | None:
    """解析 token，返回 payload 或 None"""
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    if AccessControl.require_admin(payload.get("role", "")):
        return None
    return payload


# ═══════════════════════════════════════════════════════════
# HTTP 接口
# ═══════════════════════════════════════════════════════════

@router.get("/status")
async def session_status(authorization: str = Header(default="")):
    """查询当前用户 Agent 会话状态。

    前端据此决定：
    - status=idle       → 直接连接 WS，显示"连接中→初始化中→已连接"
    - status=disconnected → 弹窗询问恢复/不恢复
    - status=ready      → Agent 存活且可能已有连接（极少见，WS 断开会变 disconnected）

    Returns:
        {"code":200, "data":{"status":"idle|disconnected|ready", "message_count":N}}
    """
    token = authorization.removeprefix("Bearer ").strip()
    payload = _auth(token)
    if not payload:
        return JSONResponse(status_code=401, content={"code": 4001, "message": "token 无效或已过期"})

    user_id = payload.get("user_id")
    entry = _svc._agents.get(user_id)

    if not entry or entry["agent"].app is None:
        return {"code": 200, "data": {"status": "idle", "message_count": 0}}

    msg_count = len([m for m in entry["agent"].messages.get("messages", [])
                     if m.get("role") != "system"])
    # 有 agent 但没有活跃 WS → disconnected（等待用户决定恢复与否）
    return {"code": 200, "data": {"status": "disconnected", "message_count": msg_count}}


@router.get("/messages")
async def get_messages(authorization: str = Header(default="")):
    """获取当前用户的对话历史消息（用于前端恢复渲染）。

    Returns:
        {"code":200, "data": {"messages": [{"role":"user|assistant","content":"..."}, ...]}}
        或 404 表示无活跃会话
    """
    token = authorization.removeprefix("Bearer ").strip()
    payload = _auth(token)
    if not payload:
        return JSONResponse(status_code=401, content={"code": 4001, "message": "token 无效或已过期"})

    user_id = payload.get("user_id")
    msgs = _svc.get_messages(user_id)

    if msgs is None:
        return JSONResponse(status_code=404, content={"code": 4004, "message": "无活跃会话"})

    return {"code": 200, "data": {"messages": msgs}}


@router.post("/messages/clear")
async def clear_messages(authorization: str = Header(default="")):
    """仅清空对话历史，保留 Agent 实例（不清空则下次 WS 连接会复用旧消息）。

    Returns:
        {"code":200, "message":"对话历史已清空"} 或 404
    """
    token = authorization.removeprefix("Bearer ").strip()
    payload = _auth(token)
    if not payload:
        return JSONResponse(status_code=401, content={"code": 4001, "message": "token 无效或已过期"})

    user_id = payload.get("user_id")
    ok = _svc.clear_messages(user_id)
    if not ok:
        return JSONResponse(status_code=404, content={"code": 4004, "message": "无活跃会话"})

    return {"code": 200, "message": "对话历史已清空"}


@router.delete("/reset")
async def reset_session(authorization: str = Header(default="")):
    """完全销毁 Agent 实例（清空对话 + 释放资源）。

    前端在退出登录、点击"关闭 Agent"时调用。

    Returns:
        {"code":200, "message":"会话已重置"}
    """
    token = authorization.removeprefix("Bearer ").strip()
    payload = _auth(token)
    if not payload:
        return JSONResponse(status_code=401, content={"code": 4001, "message": "token 无效或已过期"})

    user_id = payload.get("user_id")
    _svc.destroy_agent(user_id)
    return {"code": 200, "message": "会话已重置"}


# ═══════════════════════════════════════════════════════════
# WebSocket 接口
# ═══════════════════════════════════════════════════════════

@router.websocket("/chat")
async def sql_chat_ws(websocket: WebSocket):
    await websocket.accept()

    # ── 鉴权 ──
    from server.utils.auth import extract_ws_token
    token = extract_ws_token(websocket)
    payload = _auth(token or "")
    if not payload:
        await websocket.send_text(Result.ws_msg(code=4001, message="token 无效或已过期"))
        await websocket.close(code=4001)
        return

    if err := AccessControl.require_admin(payload.get("role", "")):
        await websocket.send_text(Result.ws_msg(code=4003, message=err.message))
        await websocket.close(code=4003)
        return

    user_id = payload.get("user_id")

    # ── 清理超时 Agent ──
    try:
        await _svc.cleanup_stale()
    except Exception:
        pass

    # ── 获取或复用 Agent ──
    await websocket.send_text(Result.ws_msg(code=200, message="连接成功"))
    try:
        agent = await _svc.get_or_create_agent(user_id)
    except Exception as e:
        await websocket.send_text(Result.ws_msg(code=4000, message=f"Agent 初始化失败: {e}"))
        await websocket.close(code=4000)
        return

    is_reconnect = len([m for m in agent.messages.get("messages", [])
                        if m.get("role") != "system"]) > 0
    await websocket.send_text(Result.ws_msg(
        code=200,
        message="对话历史已恢复" if is_reconnect else "初始化完成，可以开始查询",
    ))

    # ── 对话循环 ──
    try:
        while True:
            try:
                user_msg = await asyncio.wait_for(websocket.receive_text(), timeout=600)
            except asyncio.TimeoutError:
                await websocket.send_text(Result.ws_msg(message="会话超时，连接已关闭"))
                break
            except WebSocketDisconnect:
                break

            try:
                async for event in agent.chat_stream(user_msg):
                    await websocket.send_text(Result.ws_msg(data=event))
                _svc.touch(user_id)
            except Exception as e:
                await websocket.send_text(
                    Result.ws_msg(code=4000, message=f"处理失败: {e}")
                )
    finally:
        # 仅断开 WS 连接，Agent 保留在缓存中
        try:
            await websocket.close()
        except Exception:
            pass
