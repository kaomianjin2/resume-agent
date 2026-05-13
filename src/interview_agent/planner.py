from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from interview_agent.nodes.registry import NodeRegistry


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


@dataclass(frozen=True)
class PlanConfirmation:
    plan_id: str
    confirmed: bool
    reason: str | None = None


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
        missing_inputs.append("resume_text")

    if _requires_jd_parse(selected_node, session_inputs):
        steps.append(_build_step("jd_parse"))
        missing_inputs.append("jd_text")

    if _requires_target_role(selected_node, session_inputs):
        missing_inputs.append("target_role")

    steps.append(_build_step(selected_node))

    requires_confirmation = len(steps) > 1
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


def ensure_plan_confirmation(
    plan: ExecutionPlan,
    confirmation: PlanConfirmation | None,
) -> str | None:
    if not plan.requires_confirmation:
        return None
    if confirmation is None:
        return "执行计划未确认。"
    if confirmation.plan_id != plan.plan_id:
        return "执行计划确认已失效。"
    if not confirmation.confirmed:
        return "执行计划未确认。"
    return None


def _requires_jd_parse(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node not in {"question_generate", "jd_match"}:
        return False

    if "jd_text" in session_inputs:
        return False

    if "jd_requirements" in session_inputs:
        return False

    return True


def _requires_resume_parse(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node not in {"jd_match", "project_extract", "resume_optimize"}:
        return False

    if "resume_text" in session_inputs:
        return False

    if selected_node == "jd_match" and "resume_profile" in session_inputs:
        return False

    return True


def _requires_target_role(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node != "resume_optimize":
        return False

    return "target_role" not in session_inputs


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
