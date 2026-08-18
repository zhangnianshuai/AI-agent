"""语音面试 WebSocket 端点 — /interview/voice/{job_id}.

文字与语音面试共享同一个 InterviewWorkflow / InterviewAgent，传输层只负责
音频收发、STT/TTS 和 WebSocket 状态，不再各自维护一套面试推进逻辑。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.agent import InterviewWorkflow
from server.constant import (
    CONFIRM_TO,
    EARLY_EXIT_PROMPT,
    FINAL_EVAL_PROMPT,
    KEEPALIVE,
    RECV_TO,
    REPORT_TO,
    WELCOME,
)
from server.service.interview_server import InterviewService

_log = logging.getLogger("voice_interview")

router = APIRouter(prefix="/interview", tags=["voice_interview"])
service = InterviewService()


async def _send(websocket: WebSocket, data: dict):
    try:
        await websocket.send_text(json.dumps(data, ensure_ascii=False, default=str))
    except Exception:
        pass


async def _recv_json(websocket: WebSocket, timeout: float | None = None) -> dict | None:
    try:
        raw = (
            await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            if timeout
            else await websocket.receive_text()
        )
        return json.loads(raw)
    except (asyncio.TimeoutError, WebSocketDisconnect, json.JSONDecodeError):
        return None


@router.websocket("/voice/{job_id}")
async def voice_interview(websocket: WebSocket, job_id: int):
    await websocket.accept()

    from server.api.interview_common import init_interview_ws

    async def _send_error(code: int, message: str):
        await _send(websocket, {"type": "error", "code": code, "message": message})
        try:
            await websocket.close(code=code)
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

    await _send(
        websocket,
        {
            "type": "status",
            "state": "ready",
            "welcome": WELCOME.format(
                title=job_info["title"], total=workflow.total_main_questions
            ),
            "total": workflow.total_main_questions,
            "session_id": str(session_id),
        },
    )

    # Wait for the explicit front-end start event.
    while True:
        msg = await _recv_json(websocket, timeout=CONFIRM_TO)
        if msg is None:
            service.cancel_session(session_id, session.start_time)
            agent.close()
            await _send_error(4000, "等待开始确认超时")
            return
        if msg.get("type") == "voice_start":
            break

    from server.agent.agent_tools.interview_tools import set_interview_session
    from server.utils.voice_pipeline import VoicePipeline

    pipeline = VoicePipeline()
    set_interview_session(session_id)

    global_tts_seq = 0
    send_lock = asyncio.Lock()
    staged: dict[int, str] = {}
    next_stage_seq = 0
    # Bounded concurrency: concurrent enough to reduce first-audio latency, but
    # deliberately capped to avoid turning TTS into an unbounded fan-out.
    tts_sem = asyncio.Semaphore(2)
    tts_total_timeout = 35

    sentence_ends = set("。！？\n")
    clause_ends = set("，；：、")

    def _should_flush(buf: str) -> bool:
        if not buf:
            return False
        if buf[-1] in sentence_ends:
            return True
        if buf[-1] in clause_ends and len(buf) >= 15:
            return True
        return len(buf) >= 40

    def _reset_tts_staging():
        nonlocal next_stage_seq
        staged.clear()
        next_stage_seq = 0

    async def _tts_stage(text: str, stage_seq: int):
        nonlocal next_stage_seq, global_tts_seq
        audio = ""
        async with tts_sem:
            for attempt in range(3):
                try:
                    audio = await asyncio.wait_for(pipeline.tts_full(text), timeout=15)
                    if audio:
                        break
                except asyncio.TimeoutError:
                    _log.warning("TTS timeout attempt=%s text=%s", attempt + 1, text[:40])
                except Exception:
                    _log.exception("TTS failed attempt=%s", attempt + 1)
                if attempt < 2:
                    await asyncio.sleep(1.5 * (2 ** attempt))

        async with send_lock:
            staged[stage_seq] = audio
            while next_stage_seq in staged:
                ordered_audio = staged.pop(next_stage_seq)
                if ordered_audio:
                    global_tts_seq += 1
                    await _send(
                        websocket,
                        {
                            "type": "tts_sentence",
                            "seq": global_tts_seq,
                            "total": 999,
                            "data": ordered_audio,
                            "text": "",
                        },
                    )
                next_stage_seq += 1

    async def _speak_once(text: str):
        nonlocal global_tts_seq
        await _send(websocket, {"type": "status", "state": "speaking"})
        try:
            audio = await asyncio.wait_for(pipeline.tts_full(text), timeout=15)
        except Exception:
            audio = ""
        if audio:
            global_tts_seq += 1
            await _send(
                websocket,
                {
                    "type": "tts_sentence",
                    "seq": global_tts_seq,
                    "total": 999,
                    "data": audio,
                    "text": "",
                },
            )

    async def _stream_reply_tts(prompt: str) -> str:
        """LLM stream -> sentence segmentation -> bounded concurrent TTS -> ordered send."""
        _reset_tts_staging()
        await _send(websocket, {"type": "status", "state": "speaking"})

        buffer = ""
        full: list[str] = []
        stage_seq = 0
        tasks: list[asyncio.Task] = []

        try:
            async for chunk, is_final in agent.chat_stream(prompt):
                if is_final:
                    break
                if not chunk:
                    continue
                full.append(chunk)
                buffer += chunk
                if _should_flush(buffer):
                    segment = buffer.strip()
                    if segment:
                        tasks.append(asyncio.create_task(_tts_stage(segment, stage_seq)))
                        stage_seq += 1
                    buffer = ""

            if buffer.strip():
                tasks.append(asyncio.create_task(_tts_stage(buffer.strip(), stage_seq)))

            if tasks:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=tts_total_timeout,
                )
        except asyncio.TimeoutError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            _log.error("single-turn TTS exceeded %ss", tts_total_timeout)
        except Exception:
            for task in tasks:
                if not task.done():
                    task.cancel()
            _log.exception("voice reply stream failed")
            raise

        return "".join(full).strip()

    async def _cancel_session():
        try:
            service.cancel_session(session_id, session.start_time)
        except Exception:
            pass

    async def _receive_answer() -> tuple[str | None, int, bool, bool]:
        """Receive and transcribe one candidate answer.

        Returns: (text, duration_seconds, early_exit, aborted)
        """
        stt_failures = 0
        max_stt_failures = 3

        while stt_failures < max_stt_failures:
            await _send(websocket, {"type": "listening"})
            started = time.monotonic()
            audio_chunks: list[bytes] = []

            while True:
                msg = await _recv_json(websocket, timeout=RECV_TO)
                if msg is None:
                    await _send(websocket, {"type": "listening_timeout"})
                    return None, 0, False, True

                msg_type = msg.get("type", "")
                if msg_type == "end_interview":
                    return None, int(time.monotonic() - started), True, False
                if msg_type == "voice_data":
                    try:
                        audio_chunks.append(base64.b64decode(msg.get("data", "")))
                    except Exception:
                        _log.warning("invalid base64 voice chunk ignored")
                    continue
                if msg_type == "voice_end":
                    break

            if not audio_chunks:
                stt_failures += 1
                await _speak_once("我没有收到有效音频，请再回答一次。")
                continue

            await _send(websocket, {"type": "status", "state": "calling"})
            text = await pipeline.stt_bytes(b"".join(audio_chunks))
            if text:
                return text, int(time.monotonic() - started), False, False

            stt_failures += 1
            if stt_failures < max_stt_failures:
                await _speak_once("抱歉，我没有听清楚，能再说一遍吗？")

        await _send_error(5000, "连续多次未能识别语音，本次面试已结束")
        return None, 0, False, True

    try:
        prompt = workflow.build_current_question_prompt()
        early_exit = False
        aborted = False

        while True:
            reply = await _stream_reply_tts(prompt)
            if not reply:
                await _send_error(5000, "AI 面试官未生成有效问题，请稍后重试")
                await _cancel_session()
                return

            current_question = agent.clean_reply(reply)
            answer_text, duration, early_exit, aborted = await _receive_answer()
            if early_exit or aborted:
                break
            if not answer_text:
                aborted = True
                break

            current_stage = workflow.current_stage
            is_follow_up = workflow.current_is_follow_up

            try:
                raw_score, milvus_ref = await agent.score_answer(
                    current_question,
                    answer_text,
                    expected_question_type=current_stage,
                )
            except Exception:
                _log.exception("voice interview scoring failed")
                await _send_error(5000, "AI评分服务异常，请稍后重试")
                await _cancel_session()
                return

            decision = workflow.advance(raw_score)
            score_data = decision.score_data

            service.save_answer(
                session_id=session_id,
                round_number=decision.interaction_index,
                question=current_question,
                answer=answer_text,
                duration=duration,
                score=score_data.get("score"),
                question_type=decision.current_stage,
                comment=score_data.get("comment"),
            )
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
            await _cancel_session()
            return

        if early_exit and workflow.interaction_count == 0:
            await _cancel_session()
            await _send(
                websocket,
                {"type": "status", "state": "done", "summary": "面试未产生有效答题记录，已取消。"},
            )
            return

        await _send(websocket, {"type": "status", "state": "reporting"})
        eval_prompt = EARLY_EXIT_PROMPT if early_exit else FINAL_EVAL_PROMPT
        try:
            eval_data = await asyncio.wait_for(agent.evaluate(eval_prompt), timeout=REPORT_TO)
        except Exception:
            _log.exception("voice interview final evaluation failed")
            eval_data = {}

        if not eval_data or "total_score" not in eval_data:
            # Do not leave a successful interview permanently stuck in_progress.
            eval_data = {
                "total_score": 0,
                "is_pass": False,
                "summary": "面试已完成，但自动评价生成失败，请由HR复核。",
                "strengths": "",
                "weaknesses": "自动评价不可用",
                "suggestion": "建议人工复核本次完整问答记录",
            }

        service.complete_session(session_id, session.start_time, eval_data)
        await _send(
            websocket,
            {
                "type": "status",
                "state": "done",
                "session_id": str(session_id),
                "summary": eval_data.get("summary", "面试已完成"),
            },
        )

    except Exception:
        _log.exception("voice interview unexpected error")
        await _cancel_session()
    finally:
        agent.close()
        try:
            await websocket.close(code=1000)
        except Exception:
            pass
