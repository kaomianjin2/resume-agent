from __future__ import annotations

from interview_agent.llm import FakeLLMClient
from interview_agent.nodes.registry import build_default_registry
from interview_agent.planner import (
    PlanConfirmation,
    PlanStep,
    build_execution_plan,
    ensure_plan_confirmation,
)
from interview_agent.router import classify_with_llm, route_conversation


def test_route_conversation_matches_question_generate_for_go_request() -> None:
    registry = build_default_registry()

    result = route_conversation("生成 Go 面试题", registry=registry)

    assert result.selected_node == "question_generate"
    assert result.candidate_nodes == ["question_generate"]
    assert result.via == "rule"


def test_route_conversation_uses_rule_fallback_without_llm() -> None:
    registry = build_default_registry()

    result = route_conversation("帮我解析这个 JD", registry=registry)

    assert result.selected_node == "jd_parse"
    assert "jd_parse" in result.candidate_nodes
    assert result.via == "rule"


def test_classify_with_llm_returns_candidate_nodes_from_fake_llm() -> None:
    registry = build_default_registry()
    llm_client = FakeLLMClient(
        response_text='{"candidate_nodes":["question_generate","jd_parse"]}'
    )

    result = classify_with_llm(
        user_message="按 JD 生成后端面试题",
        registry=registry,
        llm_client=llm_client,
    )

    assert result == ["question_generate", "jd_parse"]


def test_route_conversation_falls_back_to_knowledge_search_when_llm_returns_non_json() -> None:
    registry = build_default_registry()
    llm_client = FakeLLMClient(response_text="not json")

    result = route_conversation(
        "请帮我处理一个没有规则关键词的请求",
        registry=registry,
        llm_client=llm_client,
    )

    assert result.selected_node == "knowledge_search"
    assert result.candidate_nodes == ["knowledge_search"]
    assert result.via == "default"


def test_build_execution_plan_includes_jd_parse_before_question_generation_when_jd_missing() -> None:
    registry = build_default_registry()

    plan = build_execution_plan(
        user_message="生成 Go 面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Go"]}, "target_role": "Go工程师"},
        registry=registry,
    )

    assert isinstance(plan.steps[0], PlanStep)
    assert [step.node_name for step in plan.steps] == ["jd_parse", "question_generate"]
    assert plan.requires_confirmation is True
    assert plan.missing_inputs == ["jd_text"]


def test_plan_dataclasses_support_multi_node_display() -> None:
    plan = build_execution_plan(
        user_message="生成 Go 面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Go"]}, "target_role": "Go工程师"},
        registry=build_default_registry(),
    )

    confirmation = PlanConfirmation(
        plan_id=plan.plan_id,
        confirmed=True,
        reason="用户已确认",
    )

    assert plan.summary == "jd_parse -> question_generate"
    assert plan.steps[0].title
    assert len(plan.steps) == 2
    assert confirmation.confirmed is True


def test_old_confirmation_cannot_confirm_new_plan() -> None:
    registry = build_default_registry()
    first_plan = build_execution_plan(
        user_message="生成 Go 面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Go"]}, "target_role": "Go工程师"},
        registry=registry,
    )
    second_plan = build_execution_plan(
        user_message="生成 Java 面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Java"]}, "target_role": "Java工程师"},
        registry=registry,
    )

    stale_confirmation = PlanConfirmation(
        plan_id=first_plan.plan_id,
        confirmed=True,
        reason="旧计划已确认",
    )

    blocked_message = ensure_plan_confirmation(second_plan, stale_confirmation)

    assert first_plan.plan_id != second_plan.plan_id
    assert blocked_message == "该计划包含多个节点，执行前需要用户确认"


def test_plan_id_changes_when_session_inputs_change_for_same_message_and_steps() -> None:
    registry = build_default_registry()
    first_plan = build_execution_plan(
        user_message="生成面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Go"]}, "target_role": "Go工程师"},
        registry=registry,
    )
    second_plan = build_execution_plan(
        user_message="生成面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Java"]}, "target_role": "Java工程师"},
        registry=registry,
    )

    reused_confirmation = PlanConfirmation(
        plan_id=first_plan.plan_id,
        confirmed=True,
        reason="旧确认",
    )

    blocked_message = ensure_plan_confirmation(second_plan, reused_confirmation)

    assert [step.node_name for step in first_plan.steps] == [step.node_name for step in second_plan.steps]
    assert first_plan.plan_id != second_plan.plan_id
    assert blocked_message == "该计划包含多个节点，执行前需要用户确认"


def test_build_execution_plan_accepts_non_json_serializable_session_inputs() -> None:
    registry = build_default_registry()

    plan = build_execution_plan(
        user_message="生成面试题",
        selected_node="question_generate",
        session_inputs={
            "candidate_profile": {"skills": ["Go"]},
            "target_role": "Go工程师",
            "opaque_value": object(),
        },
        registry=registry,
    )

    assert plan.plan_id
    assert plan.summary == "jd_parse -> question_generate"


def test_multi_node_plan_requires_confirmation() -> None:
    plan = build_execution_plan(
        user_message="生成 Go 面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Go"]}, "target_role": "Go工程师"},
        registry=build_default_registry(),
    )

    confirmation = PlanConfirmation(plan_id=plan.plan_id, confirmed=False, reason="未确认")

    blocked_message = ensure_plan_confirmation(plan, confirmation)

    assert blocked_message == "该计划包含多个节点，执行前需要用户确认"
