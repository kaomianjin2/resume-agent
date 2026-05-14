from __future__ import annotations

import pytest

from interview_agent.nodes.registry import (
    DEFAULT_NODE_CONTRACTS,
    NodeRegistry,
    UnknownNodeError,
    build_default_registry,
)
from interview_agent.nodes.spec import NodeContext, NodeSpec, validate_required_inputs
from interview_agent.state_contracts import (
    CANDIDATE_PROFILE,
    JD_REQUIREMENTS,
    QUESTION,
    QUESTIONS,
    RESUME_PROFILE,
    RESUME_TEXT,
    TARGET_ROLE,
    get_node_state_contract,
)


EXPECTED_NODE_NAMES = {
    "algorithm_practice",
    "practice_answer_review",
    "knowledge_search",
    "resume_parse",
    "project_extract",
    "jd_parse",
    "jd_match",
    "question_generate",
    "mock_followup",
    "answer_score",
    "weakness_train",
    "resume_optimize",
    "session_summary",
}


def fake_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    return {"received": inputs}


def test_default_registry_lists_all_runtime_nodes_with_io_contracts() -> None:
    registry = build_default_registry()

    assert set(registry.list_names()) == EXPECTED_NODE_NAMES

    for node_name in EXPECTED_NODE_NAMES:
        spec = registry.get(node_name)
        assert spec.name == node_name
        assert spec.description.strip()
        assert isinstance(spec.required_inputs, tuple)
        assert isinstance(spec.optional_inputs, tuple)
        assert isinstance(spec.outputs, tuple)
        assert spec.outputs
        assert spec.handler is not None


def test_default_node_contracts_use_shared_state_contracts() -> None:
    assert get_node_state_contract("algorithm_practice") == (
        (),
        ("practice_topic", "difficulty", "question_count"),
        ("practice_set",),
    )
    assert get_node_state_contract("practice_answer_review") == (
        ("practice_question", "reference_answer", "answer"),
        (),
        ("practice_answer_feedback",),
    )
    assert get_node_state_contract("resume_parse") == ((RESUME_TEXT,), (), (RESUME_PROFILE, CANDIDATE_PROFILE))
    assert get_node_state_contract("question_generate") == (
        (CANDIDATE_PROFILE, TARGET_ROLE),
        (JD_REQUIREMENTS, "difficulty", "question_count"),
        (QUESTIONS,),
    )
    assert DEFAULT_NODE_CONTRACTS["question_generate"] == get_node_state_contract("question_generate")


def test_node_spec_contains_required_contract_fields() -> None:
    spec = NodeSpec(
        name="fake_node",
        description="Fake node for registry tests.",
        required_inputs=(QUESTION,),
        optional_inputs=("context",),
        outputs=("answer",),
        handler=fake_handler,
    )

    assert spec.name == "fake_node"
    assert spec.description == "Fake node for registry tests."
    assert spec.required_inputs == (QUESTION,)
    assert spec.optional_inputs == ("context",)
    assert spec.outputs == ("answer",)
    assert spec.handler(NodeContext(), {"question": "hi"}) == {"received": {"question": "hi"}}


def test_validate_required_inputs_accepts_two_fake_nodes_when_inputs_are_present() -> None:
    first_spec = NodeSpec(
        name="fake_resume_parse",
        description="Parse a resume.",
        required_inputs=("resume_text",),
        optional_inputs=(),
        outputs=("resume_profile",),
        handler=fake_handler,
    )
    second_spec = NodeSpec(
        name="fake_question_generate",
        description="Generate interview questions.",
        required_inputs=("candidate_profile", "target_role"),
        optional_inputs=("difficulty",),
        outputs=("questions",),
        handler=fake_handler,
    )

    assert validate_required_inputs(first_spec, {"resume_text": "Python developer"}) == []
    assert validate_required_inputs(
        second_spec,
        {"candidate_profile": {"skills": ["Python"]}, "target_role": "Backend"},
    ) == []


def test_validate_required_inputs_returns_missing_fields_for_two_fake_nodes() -> None:
    first_spec = NodeSpec(
        name="fake_resume_parse",
        description="Parse a resume.",
        required_inputs=("resume_text",),
        optional_inputs=(),
        outputs=("resume_profile",),
        handler=fake_handler,
    )
    second_spec = NodeSpec(
        name="fake_question_generate",
        description="Generate interview questions.",
        required_inputs=("candidate_profile", "target_role"),
        optional_inputs=("difficulty",),
        outputs=("questions",),
        handler=fake_handler,
    )

    assert validate_required_inputs(first_spec, {}) == ["resume_text"]
    assert validate_required_inputs(second_spec, {"target_role": "Backend"}) == [
        "candidate_profile"
    ]


def test_registry_rejects_unknown_node_with_clear_error() -> None:
    registry = build_default_registry()

    with pytest.raises(UnknownNodeError, match="未知节点: unknown_node"):
        registry.get("unknown_node")


def test_registry_rejects_duplicate_node_names() -> None:
    first_spec = NodeSpec(
        name="fake_node",
        description="First fake node.",
        required_inputs=(),
        optional_inputs=(),
        outputs=("result",),
        handler=fake_handler,
    )
    second_spec = NodeSpec(
        name="fake_node",
        description="Second fake node.",
        required_inputs=(),
        optional_inputs=(),
        outputs=("result",),
        handler=fake_handler,
    )

    with pytest.raises(ValueError, match="重复节点: fake_node"):
        NodeRegistry([first_spec, second_spec])
