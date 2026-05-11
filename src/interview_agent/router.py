from __future__ import annotations

from dataclasses import dataclass

from interview_agent.llm import FakeLLMClient, OpenAICompatibleClient, request_structured_output
from interview_agent.nodes.registry import NodeRegistry


LLMClient = FakeLLMClient | OpenAICompatibleClient


@dataclass(frozen=True)
class RouteResult:
    selected_node: str
    candidate_nodes: list[str]
    via: str


def route_conversation(
    user_message: str,
    registry: NodeRegistry,
    llm_client: LLMClient | None = None,
) -> RouteResult:
    candidate_nodes = match_rule_based_nodes(user_message, registry)
    if candidate_nodes:
        return RouteResult(
            selected_node=candidate_nodes[0],
            candidate_nodes=candidate_nodes,
            via="rule",
        )

    if llm_client is None:
        return RouteResult(
            selected_node="knowledge_search",
            candidate_nodes=["knowledge_search"],
            via="default",
        )

    llm_candidates = classify_with_llm(
        user_message=user_message,
        registry=registry,
        llm_client=llm_client,
    )
    if llm_candidates:
        return RouteResult(
            selected_node=llm_candidates[0],
            candidate_nodes=llm_candidates,
            via="llm",
        )

    return RouteResult(
        selected_node="knowledge_search",
        candidate_nodes=["knowledge_search"],
        via="default",
    )


def classify_with_llm(
    user_message: str,
    registry: NodeRegistry,
    llm_client: LLMClient,
) -> list[str]:
    allowed_names = set(registry.list_names())
    response = request_structured_output(
        llm_client,
        prompt=_build_router_prompt(user_message, registry),
        system_prompt="你是面试助手路由器，只返回 JSON。",
    )
    candidate_nodes = response.get("candidate_nodes")
    if not isinstance(candidate_nodes, list):
        return []

    filtered_nodes: list[str] = []
    for candidate_node in candidate_nodes:
        if not isinstance(candidate_node, str):
            continue
        if candidate_node not in allowed_names:
            continue
        if candidate_node in filtered_nodes:
            continue
        filtered_nodes.append(candidate_node)
    return filtered_nodes


def match_rule_based_nodes(user_message: str, registry: NodeRegistry) -> list[str]:
    normalized_message = user_message.lower()
    matched_nodes: list[str] = []

    if _contains_any(normalized_message, ("面试题", "题目", "问题", "generate question")):
        matched_nodes.append("question_generate")

    if _contains_any(normalized_message, ("jd", "岗位描述", "职位描述")):
        matched_nodes.append("jd_parse")

    allowed_names = set(registry.list_names())
    return [node_name for node_name in matched_nodes if node_name in allowed_names]


def _build_router_prompt(user_message: str, registry: NodeRegistry) -> str:
    available_nodes = ", ".join(registry.list_names())
    return (
        "请基于用户输入返回候选节点。\n"
        f"可选节点: {available_nodes}\n"
        '返回格式: {"candidate_nodes":["node_a","node_b"]}\n'
        f"用户输入: {user_message}"
    )


def _contains_any(user_message: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in user_message for keyword in keywords)
