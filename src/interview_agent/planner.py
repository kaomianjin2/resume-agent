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

    if _requires_jd_parse(selected_node, session_inputs):
        steps.append(
            PlanStep(
                node_name="jd_parse",
                title="解析 JD",
                description="先解析岗位描述，补齐题目生成依赖。",
            )
        )
        missing_inputs.append("jd_text")

    steps.append(_build_step(selected_node))

    requires_confirmation = len(steps) > 1
    summary = " -> ".join(step.node_name for step in steps)
    plan_id = _build_plan_id(
        user_message=user_message,
        steps=steps,
        missing_inputs=missing_inputs,
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
        return "该计划包含多个节点，执行前需要用户确认"

    if confirmation.plan_id != plan.plan_id:
        return "该计划包含多个节点，执行前需要用户确认"

    if not confirmation.confirmed:
        return "该计划包含多个节点，执行前需要用户确认"

    return None


def _requires_jd_parse(selected_node: str, session_inputs: dict[str, object]) -> bool:
    if selected_node != "question_generate":
        return False

    if "jd_text" in session_inputs:
        return False

    if "jd_requirements" in session_inputs:
        return False

    return True


def _build_step(node_name: str) -> PlanStep:
    return PlanStep(
        node_name=node_name,
        title=node_name.replace("_", " ").title(),
        description=f"执行节点 {node_name}。",
    )


def _build_plan_id(
    user_message: str,
    steps: list[PlanStep],
    missing_inputs: list[str],
) -> str:
    plan_payload = {
        "user_message": user_message,
        "steps": [
            {
                "node_name": step.node_name,
                "title": step.title,
                "description": step.description,
            }
            for step in steps
        ],
        "missing_inputs": missing_inputs,
    }
    plan_digest = hashlib.sha256(
        json.dumps(plan_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return plan_digest[:16]
