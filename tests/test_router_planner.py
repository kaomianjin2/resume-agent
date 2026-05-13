from __future__ import annotations

from interview_agent.llm import FakeLLMClient
from interview_agent.nodes.registry import build_default_registry
from interview_agent.planner import (
    PlanStep,
    build_execution_plan,
)
from interview_agent.router import classify_with_llm, route_conversation


def test_route_conversation_matches_question_generate_for_go_request() -> None:
    registry = build_default_registry()

    result = route_conversation("生成 Go 面试题", registry=registry)

    assert result.selected_node == "question_generate"
    assert result.candidate_nodes == ["question_generate"]
    assert result.via == "rule"


def test_route_conversation_matches_question_generate_for_mock_interview() -> None:
    registry = build_default_registry()

    result = route_conversation("开始模拟面试", registry=registry)

    assert result.selected_node == "question_generate"
    assert result.candidate_nodes == ["question_generate"]
    assert result.via == "rule"


def test_route_conversation_matches_core_nodes_by_rules() -> None:
    registry = build_default_registry()

    examples = {
        "帮我优化简历": "resume_optimize",
        "提炼我的项目经历": "project_extract",
        "请给这道问题打分": "answer_score",
        "整理薄弱点训练计划": "weakness_train",
        "总结本轮准备内容": "session_summary",
        "把简历和岗位做匹配分析": "jd_match",
    }

    for user_message, expected_node in examples.items():
        result = route_conversation(user_message, registry=registry)

        assert result.selected_node == expected_node
        assert result.candidate_nodes[0] == expected_node
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


def test_build_execution_plan_includes_parse_steps_for_downstream_nodes() -> None:
    registry = build_default_registry()

    jd_match_plan = build_execution_plan(
        user_message="把简历和岗位做匹配分析",
        selected_node="jd_match",
        session_inputs={},
        registry=registry,
    )
    project_plan = build_execution_plan(
        user_message="提炼我的项目经历",
        selected_node="project_extract",
        session_inputs={},
        registry=registry,
    )
    optimize_plan = build_execution_plan(
        user_message="优化简历",
        selected_node="resume_optimize",
        session_inputs={},
        registry=registry,
    )

    assert [step.node_name for step in jd_match_plan.steps] == ["resume_parse", "jd_parse", "jd_match"]
    assert jd_match_plan.missing_inputs == ["resume_text", "jd_text"]
    assert jd_match_plan.requires_confirmation is True
    assert [step.node_name for step in project_plan.steps] == ["resume_parse", "project_extract"]
    assert project_plan.missing_inputs == ["resume_text"]
    assert project_plan.requires_confirmation is True
    assert [step.node_name for step in optimize_plan.steps] == ["resume_parse", "resume_optimize"]
    assert optimize_plan.missing_inputs == ["resume_text", "target_role"]
    assert optimize_plan.requires_confirmation is True


def test_plan_dataclasses_support_multi_node_display() -> None:
    plan = build_execution_plan(
        user_message="生成 Go 面试题",
        selected_node="question_generate",
        session_inputs={"candidate_profile": {"skills": ["Go"]}, "target_role": "Go工程师"},
        registry=build_default_registry(),
    )

    assert plan.summary == "jd_parse -> question_generate"
    assert plan.steps[0].title
    assert len(plan.steps) == 2


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

    assert [step.node_name for step in first_plan.steps] == [step.node_name for step in second_plan.steps]
    assert first_plan.plan_id != second_plan.plan_id


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
    assert plan.requires_confirmation is True
