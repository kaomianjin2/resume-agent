from __future__ import annotations

import json

from interview_agent.llm import request_structured_output
from interview_agent.llm import LLMError
from interview_agent.prompts import render_prompt
from interview_agent.sensitive import assert_no_sensitive_payload


def run_structured_node(
    node_name: str,
    *,
    services: dict[str, object],
    prompt_inputs: dict[str, object],
    rag_query: str | None = None,
    rag_limit: int | None = 3,
    fallback_output: dict[str, object] | None = None,
) -> dict[str, object]:
    llm = services.get("llm")
    if llm is None:
        raise RuntimeError("缺少 llm 服务")

    rag_results = resolve_rag_results(services=services, query=rag_query, limit=rag_limit)
    prompt = build_prompt(node_name=node_name, prompt_inputs=prompt_inputs, rag_results=rag_results)
    try:
        structured_output = request_structured_output(llm, prompt=prompt)
    except LLMError:
        if fallback_output is not None:
            return fallback_output
        raise
    structured_output = _preserve_rag_source_metadata(structured_output, rag_results)
    if fallback_output is None:
        return structured_output

    return {**fallback_output, **structured_output}


def build_prompt(
    *,
    node_name: str,
    prompt_inputs: dict[str, object],
    rag_results: list[dict[str, object]],
) -> str:
    assert_no_sensitive_payload(prompt_inputs, error_message="LLM prompt 输入包含敏感字段")
    assert_no_sensitive_payload(rag_results, error_message="LLM prompt 输入包含敏感字段")
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
    limit: int | None,
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


def _preserve_rag_source_metadata(
    structured_output: dict[str, object],
    rag_results: list[dict[str, object]],
) -> dict[str, object]:
    search_results = structured_output.get("search_results")
    if not isinstance(search_results, list) or not rag_results:
        return structured_output

    merged_results: list[dict[str, object]] = []
    for index, rag_result in enumerate(rag_results):
        merged_result = dict(rag_result)
        llm_result = search_results[index] if index < len(search_results) else None
        if isinstance(llm_result, dict):
            for key, value in llm_result.items():
                if key in {"chunk_id", "source_path", "score", "content"}:
                    continue
                merged_result[key] = value
        merged_results.append(merged_result)

    return {**structured_output, "search_results": merged_results}
