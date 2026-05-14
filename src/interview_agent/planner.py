from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from interview_agent.nodes.registry import NodeRegistry
from interview_agent.state_contracts import (
    TARGET_ROLE,
    find_missing_required_inputs,
    get_node_state_contract,
)


@dataclass(frozen=True)
class PlanStep:
    node_name: str
    title: str
    description: str


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    user_message: str
    steps: list[PlanStep]
    requires_confirmation: bool
    missing_inputs: list[str]
    summary: str


def build_execution_plan(
    user_message: str,
    selected_node: str,
    session_inputs: dict[str, object],
    registry: NodeRegistry,
) -> ExecutionPlan:
    registry.get(selected_node)

    steps: list[PlanStep] = []
    missing_inputs: list[str] = []

    if _requires_resume_parse(selected_node, session_inputs):
        steps.append(_build_step("resume_parse"))
        _append_missing_inputs(missing_inputs, get_node_state_contract("resume_parse")[0], session_inputs)

    if _requires_jd_parse(selected_node, session_inputs):
        steps.append(_build_step("jd_parse"))
        _append_missing_inputs(missing_inputs, get_node_state_contract("jd_parse")[0], session_inputs)

    if _requires_target_role(selected_node, session_inputs):
        _append_missing_inputs(missing_inputs, (TARGET_ROLE,), session_inputs)

    steps.append(_build_step(selected_node))

    # Planner 保留兼容字段，但运行时不再承担用户确认职责。
    requires_confirmation = False
    summary = " -> ".join(step.node_name for step in steps)
    plan_id = _build_plan_id(
        user_message=user_message,
        selected_node=selected_node,
        steps=steps,
        missing_inputs=missing_inputs,
        session_inputs=session_inputs,
    )

    return ExecutionPlan(
        plan_id=plan_id,
        user_message=user_message,
        steps=steps,
        requires_confirmation=requires_confirmation,
        missing_inputs=missing_inputs,
        summary=summary,
    )


def _requires_jd_parse(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node not in {"question_generate", "jd_match"}:
        return False

    required_inputs, _, outputs = get_node_state_contract("jd_parse")
    if not find_missing_required_inputs(required_inputs, session_inputs):
        return False

    if outputs[0] in session_inputs:
        return False

    return True


def _requires_resume_parse(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node not in {"jd_match", "project_extract", "resume_optimize"}:
        return False

    required_inputs, _, outputs = get_node_state_contract("resume_parse")
    if not find_missing_required_inputs(required_inputs, session_inputs):
        return False

    if selected_node == "jd_match" and outputs[0] in session_inputs:
        return False

    return True


def _requires_target_role(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node != "resume_optimize":
        return False

    return bool(find_missing_required_inputs((TARGET_ROLE,), session_inputs))


def _append_missing_inputs(
    missing_inputs: list[str],
    required_inputs: tuple[str, ...],
    session_inputs: dict[str, object],
) -> None:
    for input_name in find_missing_required_inputs(required_inputs, session_inputs):
        if input_name not in missing_inputs:
            missing_inputs.append(input_name)


def _build_step(node_name: str) -> PlanStep:
    return PlanStep(
        node_name=node_name,
        title=node_name.replace("_", " ").title(),
        description=f"执行节点 {node_name}。",
    )


def _build_plan_id(
    user_message: str,
    selected_node: str,
    steps: list[PlanStep],
    missing_inputs: list[str],
    session_inputs: dict[str, object],
) -> str:
    plan_payload = {
        "user_message": user_message,
        "selected_node": selected_node,
        "steps": [
            {
                "node_name": step.node_name,
                "title": step.title,
                "description": step.description,
            }
            for step in steps
        ],
        "missing_inputs": missing_inputs,
        "session_inputs": _make_stable_value(session_inputs),
    }
    plan_digest = hashlib.sha256(
        json.dumps(plan_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return plan_digest[:16]


def _make_stable_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value

    if isinstance(value, dict):
        stable_mapping: dict[str, object] = {}
        for key in sorted(value):
            stable_mapping[str(key)] = _make_stable_value(value[key])
        return stable_mapping

    if isinstance(value, list | tuple):
        return [_make_stable_value(item) for item in value]

    if isinstance(value, set | frozenset):
        stable_items = [_make_stable_value(item) for item in value]
        return sorted(stable_items, key=_stable_sort_key)

    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)

    return value


def _stable_sort_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
