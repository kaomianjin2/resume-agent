from __future__ import annotations

from interview_agent.agents import run_structured_node
from interview_agent.nodes.spec import NodeContext


def knowledge_search_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    question = _require_text(inputs, "question")
    limit = _read_limit(inputs["top_k"]) if "top_k" in inputs else None
    search_result = run_structured_node(
        "knowledge_search",
        services=_mutable_services(context),
        prompt_inputs={"question": question, "context": question},
        rag_query=question,
        rag_limit=limit,
        fallback_output={"search_results": []},
    )
    search_results = search_result.get("search_results")
    if isinstance(search_results, list) and search_results:
        return {**search_result, "search_results": search_results}
    return {"search_results": []}


def resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "resume_parse",
        services=_mutable_services(context),
        prompt_inputs={"resume_text": _require_text(inputs, "resume_text")},
    )
    resume_profile = result.get("resume_profile")
    if not isinstance(resume_profile, dict):
        return result
    return {**result, "candidate_profile": dict(resume_profile)}


def project_extract_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "project_extract",
        services=_mutable_services(context),
        prompt_inputs={"resume_text": _require_text(inputs, "resume_text")},
    )


def jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "jd_parse",
        services=_mutable_services(context),
        prompt_inputs={"jd_text": _require_text(inputs, "jd_text")},
    )


def jd_match_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "jd_match",
        services=_mutable_services(context),
        prompt_inputs={
            "resume_profile": inputs["resume_profile"],
            "jd_requirements": inputs["jd_requirements"],
        },
        rag_query=_join_query_parts(
            _read_profile_name(inputs.get("resume_profile")),
            _read_role_name(inputs.get("jd_requirements")),
        ),
    )


def question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "question_generate",
        services=_mutable_services(context),
        prompt_inputs={
            "candidate_profile": inputs["candidate_profile"],
            "target_role": _require_text(inputs, "target_role"),
        }
        | _optional_prompt_input(inputs, "jd_requirements")
        | _optional_prompt_input(inputs, "difficulty")
        | _optional_prompt_input(inputs, "question_count"),
        rag_query=_join_query_parts(
            _require_text(inputs, "target_role"),
            _read_profile_name(inputs.get("candidate_profile")),
        ),
    )


def mock_followup_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "mock_followup",
        services=_mutable_services(context),
        prompt_inputs={
            "question": _require_text(inputs, "question"),
            "answer": _require_text(inputs, "answer"),
        }
        | _optional_prompt_input(inputs, "rubric"),
        rag_query=_join_query_parts(_require_text(inputs, "question"), _require_text(inputs, "answer")),
    )


def answer_score_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "answer_score",
        services=_mutable_services(context),
        prompt_inputs={
            "question": _require_text(inputs, "question"),
            "answer": _require_text(inputs, "answer"),
            "rubric": _require_text(inputs, "rubric"),
        },
        rag_query=_join_query_parts(_require_text(inputs, "question"), _require_text(inputs, "rubric")),
    )


def weakness_train_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "weakness_train",
        services=_mutable_services(context),
        prompt_inputs={
            "weaknesses": inputs["weaknesses"],
            "goal": _require_text(inputs, "goal"),
        }
        | _optional_prompt_input(inputs, "candidate_profile"),
        rag_query=_join_query_parts(_read_role_name(inputs.get("candidate_profile")), _require_text(inputs, "goal")),
    )


def resume_optimize_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "resume_optimize",
        services=_mutable_services(context),
        prompt_inputs={
            "resume_text": _require_text(inputs, "resume_text"),
            "target_role": _require_text(inputs, "target_role"),
        }
        | _optional_prompt_input(inputs, "jd_requirements"),
        rag_query=_join_query_parts(_require_text(inputs, "target_role"), "resume optimize"),
    )


def session_summary_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    return run_structured_node(
        "session_summary",
        services=_mutable_services(context),
        prompt_inputs={"session_transcript": _require_text(inputs, "session_transcript")},
        rag_query=_require_text(inputs, "session_transcript"),
    )


def _mutable_services(context: NodeContext) -> dict[str, object]:
    return dict(context.services)


def _optional_prompt_input(inputs: dict[str, object], key: str) -> dict[str, object]:
    if key not in inputs:
        return {}
    return {key: inputs[key]}


def _require_text(inputs: dict[str, object], key: str) -> str:
    value = inputs[key]
    if isinstance(value, str):
        return value
    raise RuntimeError(f"{key} 必须是字符串")


def _read_limit(value: object) -> int:
    if isinstance(value, int) and value > 0:
        return value
    raise RuntimeError("top_k 必须是正整数")


def _read_profile_name(profile: object) -> str:
    if not isinstance(profile, dict):
        return ""
    name = profile.get("name")
    if isinstance(name, str):
        return name
    role = profile.get("role")
    if isinstance(role, str):
        return role
    return ""


def _read_role_name(requirements: object) -> str:
    if not isinstance(requirements, dict):
        return ""
    role = requirements.get("role")
    if isinstance(role, str):
        return role
    return ""


def _join_query_parts(*parts: str) -> str:
    filtered_parts = [part.strip() for part in parts if part.strip()]
    return " ".join(filtered_parts)
