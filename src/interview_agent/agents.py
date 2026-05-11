from __future__ import annotations

import json

from interview_agent.llm import request_structured_output
from interview_agent.prompts import render_prompt


def run_structured_node(
    node_name: str,
    *,
    services: dict[str, object],
    prompt_inputs: dict[str, object],
    rag_query: str | None = None,
    rag_limit: int = 3,
    fallback_output: dict[str, object] | None = None,
) -> dict[str, object]:
    llm = services.get("llm")
    if llm is None:
        raise RuntimeError("缺少 llm 服务")

    rag_results = resolve_rag_results(services=services, query=rag_query, limit=rag_limit)
    prompt = build_prompt(node_name=node_name, prompt_inputs=prompt_inputs, rag_results=rag_results)
    structured_output = request_structured_output(llm, prompt=prompt)
    if fallback_output is None:
        return structured_output

    return {**fallback_output, **structured_output}


def build_prompt(
    *,
    node_name: str,
    prompt_inputs: dict[str, object],
    rag_results: list[dict[str, object]],
) -> str:
    serialized_inputs = {
        key: _serialize_prompt_value(value)
        for key, value in prompt_inputs.items()
    }
    base_prompt = render_prompt(node_name, **serialized_inputs)
    node_inputs = json.dumps(prompt_inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    rag_context = _format_rag_context(rag_results)
    return f"{base_prompt}\nnode_inputs:\n{node_inputs}\nrag_context:\n{rag_context}"


def resolve_rag_results(
    *,
    services: dict[str, object],
    query: str | None,
    limit: int,
) -> list[dict[str, object]]:
    if not query:
        return []

    retriever = services.get("retriever")
    if retriever is None:
        return []

    if callable(retriever):
        results = retriever(query, limit)
    else:
        search = getattr(retriever, "search", None)
        if search is None:
            raise RuntimeError("retriever 服务缺少 search 能力")
        results = search(query, limit)

    return [dict(result) for result in results]


def _serialize_prompt_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_rag_context(rag_results: list[dict[str, object]]) -> str:
    if not rag_results:
        return "[]"

    context_items = []
    for result in rag_results:
        context_items.append(
            {
                "chunk_id": result.get("chunk_id"),
                "source_path": result.get("source_path"),
                "score": result.get("score"),
                "content": result.get("content"),
            }
        )
    return json.dumps(context_items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
