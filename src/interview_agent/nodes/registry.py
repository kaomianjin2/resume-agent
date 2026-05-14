from __future__ import annotations

from collections.abc import Iterable

from .interview import (
    answer_score_handler,
    jd_match_handler,
    jd_parse_handler,
    knowledge_search_handler,
    mock_followup_handler,
    project_extract_handler,
    question_generate_handler,
    resume_optimize_handler,
    resume_parse_handler,
    session_summary_handler,
    weakness_train_handler,
)
from .spec import NodeSpec


class UnknownNodeError(KeyError):
    """Raised when a node name is not registered."""


class NodeRegistry:
    def __init__(self, specs: Iterable[NodeSpec]) -> None:
        self._specs: dict[str, NodeSpec] = {}
        for spec in specs:
            if spec.name in self._specs:
                raise ValueError(f"重复节点: {spec.name}")
            self._specs[spec.name] = spec

    def list_names(self) -> list[str]:
        return sorted(self._specs)

    def get(self, name: str) -> NodeSpec:
        spec = self._specs.get(name)
        if spec is None:
            raise UnknownNodeError(f"未知节点: {name}")
        return spec


def build_default_registry() -> NodeRegistry:
    return NodeRegistry(_build_default_specs())


DEFAULT_NODE_CONTRACTS = {
    "knowledge_search": (("question",), ("top_k",), ("search_results",)),
    "resume_parse": (("resume_text",), (), ("resume_profile",)),
    "project_extract": (("resume_text",), ("resume_profile",), ("project_experiences",)),
    "jd_parse": (("jd_text",), (), ("jd_requirements",)),
    "jd_match": (("resume_profile", "jd_requirements"), (), ("match_report",)),
    "question_generate": (
        ("candidate_profile", "target_role"),
        ("jd_requirements", "difficulty", "question_count"),
        ("questions",),
    ),
    "mock_followup": (("question", "answer"), ("rubric",), ("followup_questions",)),
    "answer_score": (("question", "answer", "rubric"), (), ("score_report",)),
    "weakness_train": (("weaknesses", "goal"), ("candidate_profile",), ("training_plan",)),
    "resume_optimize": (
        ("resume_text", "target_role"),
        ("jd_requirements",),
        ("optimization_advice",),
    ),
    "session_summary": (("session_transcript",), (), ("summary",)),
}


def _build_default_specs() -> list[NodeSpec]:
    return [
        _runtime_spec(name, required_inputs, optional_inputs, outputs)
        for name, (required_inputs, optional_inputs, outputs) in DEFAULT_NODE_CONTRACTS.items()
    ]


def _runtime_spec(
    name: str,
    required_inputs: tuple[str, ...],
    optional_inputs: tuple[str, ...],
    outputs: tuple[str, ...],
) -> NodeSpec:
    handler = _RUNTIME_HANDLERS[name]
    return NodeSpec(
        name=name,
        description=f"Runtime node: {name.replace('_', ' ')}.",
        required_inputs=required_inputs,
        optional_inputs=optional_inputs,
        outputs=outputs,
        handler=handler,
    )


_RUNTIME_HANDLERS = {
    "knowledge_search": knowledge_search_handler,
    "resume_parse": resume_parse_handler,
    "project_extract": project_extract_handler,
    "jd_parse": jd_parse_handler,
    "jd_match": jd_match_handler,
    "question_generate": question_generate_handler,
    "mock_followup": mock_followup_handler,
    "answer_score": answer_score_handler,
    "weakness_train": weakness_train_handler,
    "resume_optimize": resume_optimize_handler,
    "session_summary": session_summary_handler,
}
