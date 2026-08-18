import pytest

pytest.importorskip("langgraph")

from server.agent.interview_workflow import InterviewWorkflow, build_question_plan


def _score(score=88, **kwargs):
    base = {
        "score": score,
        "completeness": 0.85,
        "relevance": 0.9,
        "technical_depth": 0.82,
        "evidence_strength": 0.8,
        "follow_up_required": False,
        "feedback": "回答较完整",
        "comment": "核心信息充分",
    }
    base.update(kwargs)
    return base


def test_question_plan_keeps_required_stage_order():
    plan = build_question_plan(10)
    assert plan[0] == "self_intro"
    assert plan[-1] == "qa"
    assert "project" in plan
    assert "technical" in plan
    assert "behavioral" in plan
    assert len(plan) == 10


def test_weak_dimension_triggers_one_bounded_follow_up():
    workflow = InterviewWorkflow(5, max_follow_ups_per_question=1)

    # self intro -> project
    assert workflow.advance(_score()).action == "next_question"
    # project -> technical
    assert workflow.advance(_score()).action == "next_question"
    assert workflow.current_stage == "technical"

    weak = _score(
        score=68,
        technical_depth=0.40,
        follow_up_required=True,
        follow_up_reason="缺少底层原理和实际取舍",
    )
    first = workflow.advance(weak)
    assert first.action == "follow_up"
    assert first.focus_dimension == "technical_depth"
    assert workflow.current_stage == "technical"
    assert workflow.current_is_follow_up is True

    # A second weak answer cannot create an unbounded follow-up loop.
    second = workflow.advance(weak)
    assert second.action == "next_question"
    assert workflow.current_stage == "behavioral"
    assert workflow.current_is_follow_up is False


def test_missing_dimension_fields_do_not_force_follow_up_for_strong_answer():
    workflow = InterviewWorkflow(5)
    decision = workflow.advance({"score": 92, "follow_up_required": False})
    assert decision.action == "next_question"
    assert decision.score_data["completeness"] == pytest.approx(0.92)


def test_last_main_question_completes_workflow():
    workflow = InterviewWorkflow(3)
    assert workflow.advance(_score()).action == "next_question"
    assert workflow.advance(_score()).action == "next_question"
    last = workflow.advance(_score())
    assert last.action == "complete"
    assert workflow.completed is True
    assert last.next_stage is None
