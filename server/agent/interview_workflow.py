"""Deterministic interview workflow built on LangGraph StateGraph.

The LLM is responsible for semantic tasks (question wording / answer scoring), while
this workflow owns deterministic control decisions such as stage progression,
follow-up limits, and interview completion. This keeps the interview bounded and
makes the decision path testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


NextAction = Literal["follow_up", "next_question", "complete"]


class InterviewDecisionState(TypedDict, total=False):
    score_data: dict
    current_stage: str
    current_question_index: int
    total_questions: int
    follow_up_count: int
    max_follow_ups: int
    next_action: NextAction
    focus_dimension: str
    reason: str


@dataclass(frozen=True)
class WorkflowDecision:
    """Result of one deterministic workflow transition."""

    action: NextAction
    interaction_index: int
    current_question_index: int
    current_stage: str
    next_question_index: int | None
    next_stage: str | None
    focus_dimension: str | None
    reason: str
    score_data: dict


_STAGE_LABELS = {
    "self_intro": "自我介绍",
    "project": "项目深挖",
    "technical": "专业能力",
    "behavioral": "行为面试",
    "qa": "反问环节",
}

_STAGE_INSTRUCTIONS = {
    "self_intro": (
        "当前环节：自我介绍。请让候选人围绕技术背景、主要技术栈、项目或实践经历做简洁介绍。"
    ),
    "project": (
        "当前环节：项目深挖。优先结合候选人简历中的真实项目，询问技术选型、个人贡献、"
        "关键难点、故障或性能问题以及最终结果；一次只问一个核心问题。"
    ),
    "technical": (
        "当前环节：专业能力。围绕岗位核心技术栈提出可区分候选人能力的问题。"
        "需要题库依据时先调用 search_question_bank，再基于检索结果改写成自然面试问题。"
    ),
    "behavioral": (
        "当前环节：行为面试。围绕协作、沟通、冲突处理、压力或问题解决经历提问，"
        "鼓励候选人用具体情境和结果回答。"
    ),
    "qa": (
        "当前环节：反问。请询问候选人是否有想了解的公司、团队、岗位或技术问题。"
    ),
}

_DIMENSION_LABELS = {
    "completeness": "回答完整性",
    "relevance": "问题相关性",
    "technical_depth": "技术深度",
    "evidence_strength": "事实与案例支撑",
}

_STAGE_DIMENSIONS = {
    "self_intro": ("completeness", "relevance", "evidence_strength"),
    "project": ("completeness", "relevance", "technical_depth", "evidence_strength"),
    "technical": ("relevance", "technical_depth", "completeness"),
    "behavioral": ("completeness", "relevance", "evidence_strength"),
    "qa": ("completeness", "relevance"),
}


def build_question_plan(question_nums: int) -> list[str]:
    """Build a deterministic stage plan for the configured main questions.

    Follow-up questions are *not* counted in ``question_nums``. This allows the
    workflow to deepen weak answers without sacrificing the final required stages.
    """
    n = max(1, int(question_nums))
    if n == 1:
        return ["self_intro"]
    if n == 2:
        return ["self_intro", "qa"]
    if n == 3:
        return ["self_intro", "technical", "qa"]
    if n == 4:
        return ["self_intro", "project", "technical", "qa"]

    middle = n - 2
    project_count = max(1, round(middle * 0.20))
    behavioral_count = max(1, round(middle * 0.15))
    technical_count = middle - project_count - behavioral_count

    if technical_count < 1:
        # Preserve all three middle stages when the question count allows it.
        technical_count = 1
        if project_count > behavioral_count and project_count > 1:
            project_count -= 1
        elif behavioral_count > 1:
            behavioral_count -= 1

    return (
        ["self_intro"]
        + ["project"] * project_count
        + ["technical"] * technical_count
        + ["behavioral"] * behavioral_count
        + ["qa"]
    )


class InterviewWorkflow:
    """Stateful controller for a single interview session.

    The compiled LangGraph only performs deterministic routing. The class keeps
    session-local counters, so it can be shared by text and voice transports.
    """

    def __init__(self, question_nums: int, max_follow_ups_per_question: int = 1):
        self.plan = build_question_plan(question_nums)
        self.max_follow_ups_per_question = max(0, int(max_follow_ups_per_question))
        self._base_index = 0
        self._follow_up_count = 0
        self._interaction_count = 0
        self._current_is_follow_up = False
        self._graph = self._compile_graph()

    @property
    def current_stage(self) -> str:
        return self.plan[self._base_index]

    @property
    def current_stage_label(self) -> str:
        return _STAGE_LABELS[self.current_stage]

    @property
    def current_question_index(self) -> int:
        """1-based index of the current *main* question."""
        return self._base_index + 1

    @property
    def interaction_count(self) -> int:
        """Number of answered prompts including follow-ups."""
        return self._interaction_count

    @property
    def current_is_follow_up(self) -> bool:
        return self._current_is_follow_up

    @property
    def completed(self) -> bool:
        return self._base_index >= len(self.plan)

    @property
    def total_main_questions(self) -> int:
        return len(self.plan)

    def _compile_graph(self):
        graph = StateGraph(InterviewDecisionState)
        graph.add_node("assess", self._assess)
        graph.add_node("follow_up", self._mark_follow_up)
        graph.add_node("next_question", self._mark_next_question)
        graph.add_node("complete", self._mark_complete)

        graph.add_edge(START, "assess")
        graph.add_conditional_edges(
            "assess",
            self._route,
            {
                "follow_up": "follow_up",
                "next_question": "next_question",
                "complete": "complete",
            },
        )
        graph.add_edge("follow_up", END)
        graph.add_edge("next_question", END)
        graph.add_edge("complete", END)
        return graph.compile()

    @staticmethod
    def _clamp(value, low: float, high: float, default: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        return max(low, min(high, value))

    def normalize_score_data(self, raw: dict | None) -> dict:
        """Validate LLM scoring output and fill stable defaults.

        Missing dimension values fall back to the overall score ratio instead of
        zero. This prevents a malformed model response from accidentally forcing
        a follow-up.
        """
        raw = raw if isinstance(raw, dict) else {}
        score = self._clamp(raw.get("score"), 0, 100, 0)
        ratio = score / 100.0

        normalized = dict(raw)
        normalized["score"] = score
        normalized["question_type"] = self.current_stage
        for key in _DIMENSION_LABELS:
            normalized[key] = self._clamp(raw.get(key), 0, 1, ratio)

        normalized["follow_up_required"] = bool(raw.get("follow_up_required", False))
        normalized["feedback"] = str(raw.get("feedback") or "").strip()[:120]
        normalized["comment"] = str(raw.get("comment") or "").strip()[:300]
        normalized["follow_up_reason"] = str(raw.get("follow_up_reason") or "").strip()[:200]
        return normalized

    def _weakest_dimension(self, score_data: dict, stage: str) -> tuple[str, float]:
        dimensions = _STAGE_DIMENSIONS.get(stage, tuple(_DIMENSION_LABELS))
        key = min(dimensions, key=lambda d: score_data.get(d, 1.0))
        return key, float(score_data.get(key, 1.0))

    def _assess(self, state: InterviewDecisionState) -> InterviewDecisionState:
        score_data = self.normalize_score_data(state.get("score_data"))
        stage = state["current_stage"]

        # The final QA stage should terminate cleanly rather than recursively
        # asking the candidate to elaborate on their question to the interviewer.
        if state["current_question_index"] >= state["total_questions"]:
            return {
                **state,
                "score_data": score_data,
                "next_action": "complete",
                "focus_dimension": "",
                "reason": "all_main_questions_completed",
            }

        weakest_key, weakest_value = self._weakest_dimension(score_data, stage)
        explicit = score_data.get("follow_up_required", False)
        score = score_data["score"]

        # Program-owned follow-up policy. The model may suggest a follow-up, but
        # cannot create an unbounded loop on its own.
        weak_answer = weakest_value < 0.62 and score < 85
        very_weak_dimension = weakest_value < 0.50
        suggested_and_not_strong = explicit and weakest_value < 0.72 and score < 90
        can_follow = state["follow_up_count"] < state["max_follow_ups"] and stage != "qa"

        if can_follow and (weak_answer or very_weak_dimension or suggested_and_not_strong):
            reason = score_data.get("follow_up_reason") or (
                f"{_DIMENSION_LABELS.get(weakest_key, weakest_key)}不足"
            )
            return {
                **state,
                "score_data": score_data,
                "next_action": "follow_up",
                "focus_dimension": weakest_key,
                "reason": reason,
            }

        return {
            **state,
            "score_data": score_data,
            "next_action": "next_question",
            "focus_dimension": "",
            "reason": "follow_up_not_needed_or_budget_exhausted",
        }

    @staticmethod
    def _route(state: InterviewDecisionState) -> str:
        return state["next_action"]

    @staticmethod
    def _mark_follow_up(state: InterviewDecisionState) -> InterviewDecisionState:
        return state

    @staticmethod
    def _mark_next_question(state: InterviewDecisionState) -> InterviewDecisionState:
        return state

    @staticmethod
    def _mark_complete(state: InterviewDecisionState) -> InterviewDecisionState:
        return state

    def build_current_question_prompt(self) -> str:
        """Prompt for the current main question."""
        stage = self.current_stage
        instruction = _STAGE_INSTRUCTIONS[stage]
        if self._base_index == 0:
            return (
                "【流程控制】当前是第1道主问题。"
                f"{instruction}\n"
                "你是面试官，只能提问，禁止替候选人回答。只输出本轮要问的问题。"
            )
        return (
            f"【流程控制】当前是第{self.current_question_index}/{self.total_main_questions}道主问题，"
            f"环节为{_STAGE_LABELS[stage]}。\n{instruction}\n"
            "结合已有面试上下文生成一道新的问题，不要重复已问内容，不要输出评分或答案。"
        )

    def build_next_prompt(self, decision: WorkflowDecision, reference: str = "") -> str:
        if decision.action == "complete":
            return ""

        if decision.action == "follow_up":
            dimension = decision.focus_dimension or "completeness"
            dimension_label = _DIMENSION_LABELS.get(dimension, dimension)
            ref_text = f"\n可参考当前题库依据：\n{reference}" if reference else ""
            return (
                "【流程控制】本轮不是新题，而是对上一题进行一次受限追问。\n"
                f"追问目标：{dimension_label}。\n"
                f"触发原因：{decision.reason}。{ref_text}\n"
                "请紧扣候选人上一轮真实回答，提出一个能够补足该维度的信息缺口的问题。"
                "一次只问一个点，不要评价、打分、给答案，也不要切换到新主题。"
            )

        # ``advance`` has already moved the workflow to the next main stage.
        return self.build_current_question_prompt()

    def advance(self, raw_score_data: dict | None) -> WorkflowDecision:
        """Advance the workflow after one candidate answer."""
        current_stage = self.current_stage
        current_question_index = self.current_question_index
        self._interaction_count += 1

        state: InterviewDecisionState = {
            "score_data": raw_score_data or {},
            "current_stage": current_stage,
            "current_question_index": current_question_index,
            "total_questions": self.total_main_questions,
            "follow_up_count": self._follow_up_count,
            "max_follow_ups": self.max_follow_ups_per_question,
        }
        result = self._graph.invoke(state)
        action: NextAction = result["next_action"]
        normalized = result["score_data"]

        if action == "follow_up":
            self._follow_up_count += 1
            self._current_is_follow_up = True
            next_index = current_question_index
            next_stage = current_stage
        elif action == "next_question":
            self._base_index += 1
            self._follow_up_count = 0
            self._current_is_follow_up = False
            next_index = self.current_question_index if self._base_index < len(self.plan) else None
            next_stage = self.current_stage if self._base_index < len(self.plan) else None
        else:
            self._base_index = len(self.plan)
            self._follow_up_count = 0
            self._current_is_follow_up = False
            next_index = None
            next_stage = None

        return WorkflowDecision(
            action=action,
            interaction_index=self._interaction_count,
            current_question_index=current_question_index,
            current_stage=current_stage,
            next_question_index=next_index,
            next_stage=next_stage,
            focus_dimension=result.get("focus_dimension") or None,
            reason=result.get("reason", ""),
            score_data=normalized,
        )
