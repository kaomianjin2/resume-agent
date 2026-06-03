from __future__ import annotations

from interview_agent.agents import run_structured_node
from interview_agent.nodes.spec import NodeContext


def algorithm_practice_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    practice_topic = _optional_text(inputs, "practice_topic", "算法和数据结构")
    difficulty = _optional_text(inputs, "difficulty", "medium")
    question_count = _optional_positive_int(inputs, "question_count", 5)
    result = run_structured_node(
        "algorithm_practice",
        services=_mutable_services(context),
        prompt_inputs={
            "practice_topic": practice_topic,
            "difficulty": difficulty,
            "question_count": question_count,
        },
        rag_query=_join_query_parts(practice_topic, "算法 数据结构 练习"),
    )
    output = _normalize_node_output(result, {"practice_set": dict})
    _require_object_fields(
        output["practice_set"],
        "practice_set",
        {"topic": str, "difficulty": str, "exercises": list},
    )
    _require_practice_exercises(output["practice_set"]["exercises"])
    return output


def practice_answer_review_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "practice_answer_review",
        services=_mutable_services(context),
        prompt_inputs={
            "practice_question": _require_text(inputs, "practice_question"),
            "reference_answer": _require_text(inputs, "reference_answer"),
            "answer": _require_text(inputs, "answer"),
        },
        rag_query=_require_text(inputs, "practice_question"),
    )
    output = _normalize_node_output(result, {"practice_answer_feedback": dict})
    _require_object_fields(
        output["practice_answer_feedback"],
        "practice_answer_feedback",
        {"is_correct": bool, "feedback": str, "correct_answer": str},
    )
    return output


def knowledge_search_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    question = _require_text(inputs, "question")
    limit = _read_limit(inputs["top_k"]) if "top_k" in inputs else None
    result = run_structured_node(
        "knowledge_search",
        services=_mutable_services(context),
        prompt_inputs={"question": question, "context": question},
        rag_query=question,
        rag_limit=limit,
    )
    return _normalize_node_output(result, {"search_results": list})


def resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "resume_parse",
        services=_mutable_services(context),
        prompt_inputs={"resume_text": _require_text(inputs, "resume_text")},
    )
    output = _normalize_node_output(result, {"resume_profile": dict})
    return {**output, "candidate_profile": dict(output["resume_profile"])}


def project_extract_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "project_extract",
        services=_mutable_services(context),
        prompt_inputs={"resume_text": _require_text(inputs, "resume_text")},
    )
    return _normalize_node_output(result, {"project_experiences": list})


def jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "jd_parse",
        services=_mutable_services(context),
        prompt_inputs={"jd_text": _require_text(inputs, "jd_text")},
    )
    return _normalize_node_output(result, {"jd_requirements": dict})


def jd_match_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "jd_match",
        services=_mutable_services(context),
        prompt_inputs={
            "resume_profile": inputs["resume_profile"],
            "jd_requirements": inputs["jd_requirements"],
        },
    )
    return _normalize_node_output(result, {"match_report": dict})


def question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    question_type = _optional_text(inputs, "question_type", "行为面试")
    result = run_structured_node(
        "question_generate",
        services=_mutable_services(context),
        prompt_inputs={
            "candidate_profile": inputs["candidate_profile"],
            "target_role": _require_text(inputs, "target_role"),
        }
        | _optional_prompt_input(inputs, "jd_requirements")
        | _optional_prompt_input(inputs, "difficulty")
        | _optional_prompt_input(inputs, "question_count")
        | {"question_type": question_type},
        rag_query=_join_query_parts(
            _require_text(inputs, "target_role"),
            _read_profile_name(inputs.get("candidate_profile")),
        ),
    )
    return _normalize_node_output(result, {"questions": list})


def mock_followup_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "mock_followup",
        services=_mutable_services(context),
        prompt_inputs={
            "question": _require_text(inputs, "question"),
            "answer": _require_text(inputs, "answer"),
        }
        | _optional_prompt_input(inputs, "rubric"),
        rag_query=_join_query_parts(_require_text(inputs, "question"), _require_text(inputs, "answer")),
    )
    return _normalize_node_output(result, {"followup_questions": list})


def answer_score_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "answer_score",
        services=_mutable_services(context),
        prompt_inputs={
            "question": _require_text(inputs, "question"),
            "answer": _require_text(inputs, "answer"),
            "rubric": _require_text(inputs, "rubric"),
        },
        rag_query=_join_query_parts(_require_text(inputs, "question"), _require_text(inputs, "rubric")),
    )
    output = _normalize_node_output(result, {"score_report": dict})
    _require_object_fields(
        output["score_report"],
        "score_report",
        {"score": (int, float), "gaps": list, "suggestions": list, "reference_answer": str},
    )
    return output


def weakness_train_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "weakness_train",
        services=_mutable_services(context),
        prompt_inputs={
            "weaknesses": inputs["weaknesses"],
            "goal": _require_text(inputs, "goal"),
        }
        | _optional_prompt_input(inputs, "candidate_profile"),
        rag_query=_join_query_parts(_read_role_name(inputs.get("candidate_profile")), _require_text(inputs, "goal")),
    )
    output = _normalize_node_output(result, {"training_plan": dict})
    _require_object_fields(
        output["training_plan"],
        "training_plan",
        {"focus": str, "steps": list, "drills": list, "schedule": list},
    )
    return output


def resume_optimize_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "resume_optimize",
        services=_mutable_services(context),
        prompt_inputs={
            "resume_text": _require_text(inputs, "resume_text"),
            "target_role": _require_text(inputs, "target_role"),
        }
        | _optional_prompt_input(inputs, "jd_requirements"),
        rag_query=_join_query_parts(_require_text(inputs, "target_role"), "resume optimize"),
    )
    output = _normalize_node_output(result, {"optimization_advice": dict})
    _require_object_fields(
        output["optimization_advice"],
        "optimization_advice",
        {"summary": str, "bullets": list, "risks": list, "rewrite_examples": list},
    )
    return output


def session_summary_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    result = run_structured_node(
        "session_summary",
        services=_mutable_services(context),
        prompt_inputs={"session_transcript": _require_text(inputs, "session_transcript")},
        rag_query=_require_text(inputs, "session_transcript"),
    )
    return _normalize_node_output(result, {"summary": dict})


def _mutable_services(context: NodeContext) -> dict[str, object]:
    return dict(context.services)


def _normalize_node_output(
    output: dict[str, object],
    expected_types: dict[str, type | tuple[type, ...]],
) -> dict[str, object]:
    normalized_output = {}
    for output_key, expected_type in expected_types.items():
        if output_key not in output:
            raise RuntimeError("节点输出缺少字段: " + output_key)
        output_value = output[output_key]
        if not isinstance(output_value, expected_type):
            raise RuntimeError(f"节点输出字段类型错误: {output_key}")
        if isinstance(output_value, dict) and not output_value:
            raise RuntimeError(f"节点输出字段为空: {output_key}")
        normalized_output[output_key] = output_value
    return normalized_output


def _require_object_fields(
    value: object,
    object_name: str,
    expected_fields: dict[str, type | tuple[type, ...]],
) -> None:
    if not isinstance(value, dict):
        raise RuntimeError(f"节点输出字段类型错误: {object_name}")
    for field_name, expected_type in expected_fields.items():
        if field_name not in value:
            raise RuntimeError(f"节点输出缺少字段: {object_name}.{field_name}")
        if not isinstance(value[field_name], expected_type):
            raise RuntimeError(f"节点输出字段类型错误: {object_name}.{field_name}")


def _require_practice_exercises(exercises: object) -> None:
    if not isinstance(exercises, list):
        raise RuntimeError("节点输出字段类型错误: practice_set.exercises")
    for exercise_index, exercise in enumerate(exercises, start=1):
        if not isinstance(exercise, dict):
            raise RuntimeError(f"节点输出字段类型错误: practice_set.exercises[{exercise_index}]")
        _require_object_fields(
            exercise,
            f"practice_set.exercises[{exercise_index}]",
            {"title": str, "prompt": str, "hints": list, "solution_outline": list},
        )


def _optional_prompt_input(inputs: dict[str, object], key: str) -> dict[str, object]:
    if key not in inputs:
        return {}
    return {key: inputs[key]}


def _require_text(inputs: dict[str, object], key: str) -> str:
    value = inputs[key]
    if isinstance(value, str):
        return value
    raise RuntimeError(f"{key} 必须是字符串")


def _optional_text(inputs: dict[str, object], key: str, default_value: str) -> str:
    if key not in inputs:
        return default_value
    return _require_text(inputs, key)


def _optional_positive_int(inputs: dict[str, object], key: str, default_value: int) -> int:
    if key not in inputs:
        return default_value
    value = inputs[key]
    if isinstance(value, int) and value > 0:
        return value
    raise RuntimeError(f"{key} 必须是正整数")


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
