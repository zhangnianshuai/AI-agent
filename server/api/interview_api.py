import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from server.service.interview_server import InterviewService
from server.agent import InterviewAgent
from server.utils.auth import get_current_user
from server.models.result import Result
from server.constant import (
    STREAM_START, STREAM_END, KEEPALIVE,
    WELCOME, FINAL_EVAL_PROMPT, EARLY_EXIT_PROMPT,
    EXIT_KW, RECV_TO, CONFIRM_TO, REPORT_TO,
)


router = APIRouter(prefix="/interview", tags=["interview"])
service = InterviewService()


# ── 心跳辅助（防止反向代理/负载均衡器空闲断开 WebSocket）──

async def _heartbeat(websocket: WebSocket, interval: int = 45):
    """定期发送 ping 帧，保持 WebSocket 连接活跃"""
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket.send_text(KEEPALIVE)
        except Exception:
            break


# ═══════════════════════════════════════════════════════════
# 参加面试（WebSocket）
# ═══════════════════════════════════════════════════════════

@router.websocket("/{job_id}")
async def start_interview(websocket: WebSocket, job_id: int):
    await websocket.accept()

    from server.api.interview_common import init_interview_ws
    from server.agent import InterviewWorkflow

    async def _send_error(code: int, message: str):
        try:
            await websocket.send_text(Result.ws_msg(code=code, message=message))
        except Exception:
            pass
        try:
            await websocket.close(code=code, reason=message)
        except Exception:
            pass

    init = await init_interview_ws(websocket, job_id, _send_error, service)
    if init is None:
        return

    cfg = init["cfg"]
    job_info = init["job_info"]
    agent = init["agent"]
    session_id = init["session_id"]
    session = init["session"]
    workflow = InterviewWorkflow(cfg.question_nums, max_follow_ups_per_question=1)

    async def _recv_with_heartbeat(timeout: int) -> str:
        hb = asyncio.create_task(_heartbeat(websocket))
        try:
            return await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        finally:
            hb.cancel()

    async def _fail(code: int = 4000, message: str = ""):
        try:
            service.cancel_session(session_id, session.start_time)
        except Exception:
            pass
        if message:
            try:
                await websocket.send_text(Result.ws_msg(code=code, message=message))
            except Exception:
                pass
        try:
            await websocket.close(code=code, reason=message or "error")
        except Exception:
            pass

    try:
        await websocket.send_text(Result.ws_msg(message=WELCOME.format(
            title=job_info["title"], total=workflow.total_main_questions
        )))
        try:
            await _recv_with_heartbeat(CONFIRM_TO)
        except (asyncio.TimeoutError, WebSocketDisconnect):
            await _fail()
            return

        early_exit = False
        aborted = False
        prompt = workflow.build_current_question_prompt()

        while True:
            # 1) 由 Workflow 指定阶段，Agent 只负责当前问题的自然语言生成。
            await websocket.send_text(STREAM_START)
            ai_reply = ""
            try:
                async for chunk, is_final in agent.chat_stream(prompt):
                    if is_final:
                        ai_reply = chunk
                    else:
                        await websocket.send_text(chunk)
            except Exception as exc:
                await _fail(message=f"AI服务异常：{exc}")
                return
            await websocket.send_text(STREAM_END)

            current_question = InterviewAgent.clean_reply(ai_reply)
            if not current_question:
                await _fail(message="AI未生成有效面试问题，请稍后重试")
                return

            # 2) 等待候选人真实回答。
            t0 = time.time()
            try:
                answer_text = await _recv_with_heartbeat(RECV_TO)
            except asyncio.TimeoutError:
                await _fail(message="等待回答超时，面试已结束")
                aborted = True
                break
            except WebSocketDisconnect:
                await _fail()
                aborted = True
                break
            elapsed = int(time.time() - t0)

            if answer_text.strip() in EXIT_KW:
                early_exit = True
                break

            # 3) 独立评分链路：RAG参考 + 结构化多维评分。
            current_stage = workflow.current_stage
            is_follow_up = workflow.current_is_follow_up
            try:
                raw_score, milvus_ref = await agent.score_answer(
                    current_question,
                    answer_text,
                    expected_question_type=current_stage,
                )
            except Exception as exc:
                await _fail(message=f"AI评分服务异常：{exc}")
                return

            # 4) StateGraph 根据结构化结果做受限决策：追问 / 下一主问题 / 完成。
            decision = workflow.advance(raw_score)
            score_data = decision.score_data

            try:
                service.save_answer(
                    session_id=session_id,
                    round_number=decision.interaction_index,
                    question=current_question,
                    answer=answer_text,
                    duration=elapsed,
                    score=score_data.get("score"),
                    question_type=decision.current_stage,
                    comment=score_data.get("comment"),
                )
            except Exception as exc:
                await _fail(message=f"保存面试记录失败：{exc}")
                return

            # 5) 显式 transcript 作为最终报告的数据源；同时向出题 Agent 注入压缩上下文。
            agent.record_turn(
                question=current_question,
                answer=answer_text,
                score_data=score_data,
                question_type=decision.current_stage,
                is_follow_up=is_follow_up,
            )

            if decision.action == "complete":
                break

            prompt = workflow.build_next_prompt(decision, reference=milvus_ref)

        if aborted:
            return

        if early_exit and workflow.interaction_count == 0:
            service.cancel_session(session_id, session.start_time)
            await websocket.send_text(Result.ws_msg(message="面试尚未产生答题记录，已取消。"))
            await websocket.close(code=1000, reason="无答题记录")
            return

        await websocket.send_text(Result.ws_msg(message="⏳ 正在生成面试报告，请稍候..."))
        eval_prompt = EARLY_EXIT_PROMPT if early_exit else FINAL_EVAL_PROMPT

        try:
            eval_data = await asyncio.wait_for(agent.evaluate(eval_prompt), timeout=REPORT_TO)
        except asyncio.TimeoutError:
            await _fail(message="报告生成超时，请稍后重试")
            return
        except Exception as exc:
            await _fail(message=f"报告生成失败：{exc}")
            return

        if not eval_data or "total_score" not in eval_data:
            await _fail(message="面试报告解析失败，请稍后重试")
            return

        service.complete_session(session_id, session.start_time, eval_data)
        await websocket.send_text(Result.ws_msg(
            message="🎉 面试已完成！点击下方按钮查看面试报告。",
            data={"session_id": session_id},
        ))
        await websocket.close(code=1000, reason="面试完成")

    except Exception:
        try:
            service.cancel_session(session_id, session.start_time)
        except Exception:
            pass
        try:
            await websocket.send_text(Result.ws_msg(code=4000, message="服务器内部异常，请稍后重试"))
        except Exception:
            pass
        try:
            await websocket.close(code=4000, reason="服务器内部异常")
        except Exception:
            pass
    finally:
        agent.close()


# ═══════════════════════════════════════════════════════════
# 面试报告
# ═══════════════════════════════════════════════════════════

@router.get("/report/{session_id}")
def get_interview_report(session_id: int, user: dict = Depends(get_current_user)):
    """查询面试报告（仅允许本人或 HR/admin 查看）"""
    return service.get_interview_report(session_id, user)


@router.get("/sessions")
def list_interview_sessions(
    page: int = 1, page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    """分页返回面试会话列表，候选人只看自己的"""
    return service.list_sessions(user, page=page, page_size=page_size)


@router.delete("/sessions/{session_id}")
def delete_interview_session(session_id: int, user: dict = Depends(get_current_user)):
    """级联删除面试会话：records → evaluation → session"""
    return service.delete_session(session_id, user)


# ═══════════════════════════════════════════════════════════
# 候选人管理（公司 HR / admin）
# ═══════════════════════════════════════════════════════════

@router.get("/company/{company_id}/candidates")
def list_company_candidates(
    company_id: int,
    is_pass: int = None,
    job_title: str = None,
    job_location: str = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
):
    """查询公司候选人列表（含筛选）。admin 可看全部，hr 只看自己关联公司"""
    return service.list_company_candidates(
        company_id, user,
        is_pass=is_pass, job_title=job_title, job_location=job_location,
        page=page, page_size=page_size,
    )


@router.put("/candidates/{session_id}/pass")
def set_candidate_pass(
    session_id: int,
    is_pass: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    """修改候选人面试通过状态（is_pass: 1=通过, 0=未通过, null=待评价）"""
    return service.set_candidate_pass(session_id, is_pass, user)
