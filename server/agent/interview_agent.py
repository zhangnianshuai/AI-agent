"""InterviewAgent — AI 面试官 Agent.

LLM responsibilities:
- generate natural interview questions with tool access;
- score one answer with a dedicated evaluator model;
- generate the final HR report from an explicit transcript.

Workflow decisions such as stage switching and follow-up limits live in
``InterviewWorkflow`` rather than in prompts.
"""

from __future__ import annotations

import asyncio
import logging
import time

from server.agent.base_agent import BaseAgent, STREAM_TIMEOUT
from server.constant import SCORE_PATTERN, SYSTEM_PROMPT, SCORE_PROMPT, ANSWER_MAX
from server.utils.llm_utils import async_retry_ainvoke, extract_json_from_reply
from server.utils.agent_trace import AgentTrace

_log = logging.getLogger(__name__)


class InterviewAgent(BaseAgent):
    def __init__(
        self,
        agent_config,
        job_info: dict,
        resume_info: dict | None = None,
        collection_name: str = "official_job_question_bank",
        question_partition: str | None = None,
    ):
        super().__init__(agent_config)
        self.job_info = job_info
        self.resume_info = resume_info
        self.collection_name = collection_name
        self.question_partition = question_partition
        self._eval_llm = None
        self._score_llm = None
        self.transcript: list[dict] = []

        # Milvus 题库检索实例（评分检索走独立链路，不污染 ReAct 工具历史）
        from server.dao.milvus_db import MilvusDataBase

        self.mdb = MilvusDataBase(collection_name)
        self._milvus_filter = (
            f'question_bank_partition == "{question_partition}"'
            if question_partition
            else None
        )

    def close(self):
        self._score_llm = None
        self._eval_llm = None
        self.transcript.clear()
        super().close()

    # ── BaseAgent 抽象方法实现 ──────────────────────────

    def _get_tools(self) -> list:
        from server.agent.agent_tools import interview_tools_list

        return interview_tools_list

    def _build_system_prompt_content(self) -> str:
        resume_section = ""
        if self.resume_info:
            resume_section = f"""
## 候选人背景
- 姓名：{self.resume_info.get('name', '')}
- 工作年限：{self.resume_info.get('work_year', '')}
- 技能：{self.resume_info.get('skills', '')}
- 学历：{self._format_education()}
- 项目经历：{self._format_projects()}
- 自我评价：{self.resume_info.get('self_evaluation', '')}"""

        n = self.agent_config.question_nums
        from server.agent.interview_workflow import build_question_plan
        plan = build_question_plan(n)
        self_intro_nums = plan.count("self_intro")
        project_nums = plan.count("project")
        tech_nums = plan.count("technical")
        behavioral_nums = plan.count("behavioral")
        qa_nums = plan.count("qa")

        return SYSTEM_PROMPT.format(
            base_role=self.agent_config.system_prompt or "你是一位专业的AI面试官。",
            title=self.job_info.get("title", ""),
            description=self.job_info.get("description", "") or "无",
            education=self.job_info.get("education_requirement", "") or "不限",
            experience=self.job_info.get("experience_requirement", "") or "不限",
            location=self.job_info.get("location", "") or "不限",
            resume_section=resume_section,
            question_nums=n,
            self_intro_nums=self_intro_nums,
            project_nums=project_nums,
            tech_nums=tech_nums,
            behavioral_nums=behavioral_nums,
            qa_nums=qa_nums,
            pass_score=int((self.agent_config.score_threshold or 0.6) * 100),
        )

    async def init(self):
        from server.agent.agent_tools.milvus_tools import configure

        configure(self.collection_name, self.question_partition)
        await super().init()

    # ── 简历上下文格式化 ────────────────────────────────

    def _format_education(self) -> str:
        if not self.resume_info:
            return "无"
        edu_list = self.resume_info.get("education", []) or []
        if not edu_list:
            return "无"
        return "；".join(
            f"{e.get('school_name', '')} {e.get('degree', '')} "
            f"{e.get('major', '')} ({e.get('start_date', '')} - {e.get('end_date', '')})"
            for e in edu_list
        )

    def _format_projects(self) -> str:
        if not self.resume_info:
            return "无"
        proj_list = self.resume_info.get("projects", []) or []
        if not proj_list:
            return "无"
        return "\n".join(
            f"[{p.get('project_name', '')}] 角色: {p.get('role', '')} | "
            f"描述: {p.get('description', '')}"
            for p in proj_list
        )

    # ── 评分 ────────────────────────────────────────────

    def _search_reference(self, query: str, top_k: int = 2) -> str:
        """用当前问题检索题库，返回评分参考文本。"""
        try:
            hits = self.mdb._rrf_search(
                query=query,
                top_k=top_k,
                filter_expr=self._milvus_filter,
                output_fields=["question", "answer", "scoring_criteria"],
            )
            if not hits:
                return ""
            lines = []
            for i, hit in enumerate(hits, 1):
                entity = hit.get("entity", {})
                lines.append(
                    f"{i}. {entity.get('question', '')}\n"
                    f"参考答案：{entity.get('answer', '')[:300]}\n"
                    f"评分标准：{entity.get('scoring_criteria', '')[:180]}"
                )
            return "\n".join(lines)
        except Exception as exc:
            _log.warning("Milvus 检索失败: %s", exc)
            return ""

    def _init_scorer(self):
        self._score_llm = self._make_llm(
            streaming=False,
            temperature=0.1,
            max_tokens=900,
        )

    async def score_answer(
        self,
        question: str,
        answer: str,
        expected_question_type: str,
    ) -> tuple[dict, str]:
        """Score one answer without mutating the ReAct conversation history.

        Milvus retrieval runs in a worker thread because the client is synchronous.
        The evaluator uses a dedicated non-streaming LLM, avoiding the old duplicate
        prompt issue caused by temporarily replacing ``self.messages`` and calling
        ``BaseAgent.chat`` again.
        """
        if self._score_llm is None:
            self._init_scorer()

        trace = AgentTrace(
            "interview.score",
            model=self._model_name,
            question_type=expected_question_type,
            question_chars=len(question),
            answer_chars=min(len(answer), ANSWER_MAX),
        )
        retrieval_started = time.perf_counter()
        ref = await asyncio.to_thread(self._search_reference, question)
        trace.event(
            "retrieval",
            latency_ms=round((time.perf_counter() - retrieval_started) * 1000, 2),
            reference_found=bool(ref),
            reference_chars=len(ref),
        )
        prompt = SCORE_PROMPT.format(
            expected_question_type=expected_question_type,
            question=question,
            answer=answer[:ANSWER_MAX],
            reference=ref or "无",
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是独立的面试评分组件，只负责根据真实问答输出结构化 JSON。"
                    "不得生成新的面试问题，也不得补写候选人未表达的信息。"
                ),
            },
            {"role": "user", "content": prompt},
        ]

        llm_started = time.perf_counter()
        try:
            async with asyncio.timeout(STREAM_TIMEOUT):
                reply = await async_retry_ainvoke(self._score_llm, messages)
        except TimeoutError as exc:
            trace.finish(status="timeout", error=str(exc))
            raise asyncio.TimeoutError("评分模型调用超时") from exc
        except Exception as exc:
            trace.finish(status="error", error=str(exc))
            raise

        trace.event("llm", latency_ms=round((time.perf_counter() - llm_started) * 1000, 2))
        content = reply.content if hasattr(reply, "content") else str(reply)
        score_data = extract_json_from_reply(content)
        if not score_data:
            _log.warning("[score_answer] JSON解析失败, reply=%s", content[:300])
            trace.finish(status="invalid_output", output_chars=len(content))
            raise ValueError("评分结果不是合法 JSON")
        trace.finish(score=score_data.get("score"), output_chars=len(content))
        return score_data, ref

    # ── 面试上下文 / Transcript ─────────────────────────

    def record_turn(
        self,
        question: str,
        answer: str,
        score_data: dict,
        question_type: str,
        is_follow_up: bool = False,
    ):
        """Persist an in-memory structured transcript and compact Agent context.

        The transcript is the source of truth for final evaluation. Candidate
        answers are no longer stored only as system messages and then accidentally
        filtered out during report generation.
        """
        turn = {
            "question": question,
            "answer": answer,
            "question_type": question_type,
            "is_follow_up": bool(is_follow_up),
            "score": score_data.get("score"),
            "feedback": score_data.get("feedback", ""),
            "comment": score_data.get("comment", ""),
            "completeness": score_data.get("completeness"),
            "relevance": score_data.get("relevance"),
            "technical_depth": score_data.get("technical_depth"),
            "evidence_strength": score_data.get("evidence_strength"),
        }
        self.transcript.append(turn)

        compact = (
            "【系统记录：候选人真实回答，仅用于后续出题，不得模仿候选人口吻】\n"
            f"题目：{question}\n"
            f"回答：{answer[:ANSWER_MAX]}\n"
            f"后台评估：score={score_data.get('score')}, "
            f"completeness={score_data.get('completeness')}, "
            f"relevance={score_data.get('relevance')}, "
            f"technical_depth={score_data.get('technical_depth')}, "
            f"evidence_strength={score_data.get('evidence_strength')}"
        )
        self.messages["messages"].append({"role": "system", "content": compact})
        self._trim_history()

    # 兼容旧调用；新代码应使用 record_turn。
    def inject_feedback(self, answer: str, feedback: str):
        self.messages["messages"].append(
            {
                "role": "system",
                "content": (
                    "【系统记录：候选人真实回答，仅供上下文参考】\n"
                    f"候选人回答：{answer[:ANSWER_MAX]}\n反馈摘要：{feedback[:120]}"
                ),
            }
        )
        self._trim_history()

    # ── 最终评价 ────────────────────────────────────────

    def _init_evaluator(self):
        self._eval_llm = self._make_llm(
            streaming=False,
            temperature=0.2,
            max_tokens=2048,
        )

    def _format_transcript(self) -> str:
        if not self.transcript:
            return "（无有效问答记录）"
        parts = []
        for i, turn in enumerate(self.transcript, 1):
            follow = "（追问）" if turn.get("is_follow_up") else ""
            parts.append(
                f"第{i}轮 {turn.get('question_type', '')}{follow}\n"
                f"面试官：{turn.get('question', '')}\n"
                f"候选人：{turn.get('answer', '')}\n"
                f"后台单轮评分：{turn.get('score')}；备注：{turn.get('comment', '')}"
            )
        return "\n\n".join(parts)

    async def evaluate(self, eval_prompt: str) -> dict:
        """Generate final evaluation from the explicit candidate transcript."""
        if self._eval_llm is None:
            self._init_evaluator()

        transcript = self._format_transcript()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是招聘评估组件。只能依据提供的真实面试记录形成 HR 报告，"
                    "不得把简历信息当作候选人在面试中已经证明的事实。"
                ),
            },
            {
                "role": "user",
                "content": f"## 完整面试记录\n{transcript}\n\n## 输出要求\n{eval_prompt}",
            },
        ]

        trace = AgentTrace(
            "interview.report",
            model=self._model_name,
            turns=len(self.transcript),
            transcript_chars=len(transcript),
        )
        try:
            async with asyncio.timeout(STREAM_TIMEOUT):
                reply = await async_retry_ainvoke(self._eval_llm, messages)
        except TimeoutError as exc:
            trace.finish(status="timeout", error=str(exc))
            raise asyncio.TimeoutError("最终评价模型调用超时") from exc
        except Exception as exc:
            trace.finish(status="error", error=str(exc))
            raise

        content = reply.content if hasattr(reply, "content") else str(reply)
        result = extract_json_from_reply(content)
        if not result:
            _log.warning("[evaluate] JSON解析失败, reply=%s", content[:300])
            trace.finish(status="invalid_output", output_chars=len(content))
        else:
            trace.finish(total_score=result.get("total_score"), output_chars=len(content))
        return result

    @staticmethod
    def parse_score(reply: str) -> dict:
        m = SCORE_PATTERN.search(reply)
        if m:
            return {
                "score": float(m.group(1)),
                "question_type": m.group(2),
                "comment": m.group(3).strip(),
            }
        return {}

    @staticmethod
    def clean_reply(reply: str) -> str:
        return SCORE_PATTERN.sub("", reply).strip()
