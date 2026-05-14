from __future__ import annotations

import json
from typing import TypeAlias

QUESTION = "question"
ANSWER = "answer"
RUBRIC = "rubric"
TOP_K = "top_k"
RESUME_TEXT = "resume_text"
RESUME_PROFILE = "resume_profile"
CANDIDATE_PROFILE = "candidate_profile"
PROJECT_EXPERIENCES = "project_experiences"
JD_TEXT = "jd_text"
JD_REQUIREMENTS = "jd_requirements"
TARGET_ROLE = "target_role"
MATCH_REPORT = "match_report"
DIFFICULTY = "difficulty"
QUESTION_COUNT = "question_count"
QUESTIONS = "questions"
PRACTICE_TOPIC = "practice_topic"
PRACTICE_SET = "practice_set"
PRACTICE_QUESTION = "practice_question"
REFERENCE_ANSWER = "reference_answer"
PRACTICE_ANSWER_FEEDBACK = "practice_answer_feedback"
FOLLOWUP_QUESTIONS = "followup_questions"
SCORE_REPORT = "score_report"
WEAKNESSES = "weaknesses"
GOAL = "goal"
TRAINING_PLAN = "training_plan"
OPTIMIZATION_ADVICE = "optimization_advice"
SESSION_TRANSCRIPT = "session_transcript"
SUMMARY = "summary"
SEARCH_RESULTS = "search_results"

ALLOWED_EMPTY_LIST_STATE_KEYS = frozenset({SEARCH_RESULTS, QUESTIONS, FOLLOWUP_QUESTIONS})

NodeStateContract: TypeAlias = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]


DEFAULT_NODE_STATE_CONTRACTS: dict[str, NodeStateContract] = {
    "algorithm_practice": ((), (PRACTICE_TOPIC, DIFFICULTY, QUESTION_COUNT), (PRACTICE_SET,)),
    "practice_answer_review": (
        (PRACTICE_QUESTION, REFERENCE_ANSWER, ANSWER),
        (),
        (PRACTICE_ANSWER_FEEDBACK,),
    ),
    "knowledge_search": ((QUESTION,), (TOP_K,), (SEARCH_RESULTS,)),
    "resume_parse": ((RESUME_TEXT,), (), (RESUME_PROFILE, CANDIDATE_PROFILE)),
    "project_extract": ((RESUME_TEXT,), (RESUME_PROFILE,), (PROJECT_EXPERIENCES,)),
    "jd_parse": ((JD_TEXT,), (), (JD_REQUIREMENTS,)),
    "jd_match": ((RESUME_PROFILE, JD_REQUIREMENTS), (), (MATCH_REPORT,)),
    "question_generate": (
        (CANDIDATE_PROFILE, TARGET_ROLE),
        (JD_REQUIREMENTS, DIFFICULTY, QUESTION_COUNT),
        (QUESTIONS,),
    ),
    "mock_followup": ((QUESTION, ANSWER), (RUBRIC,), (FOLLOWUP_QUESTIONS,)),
    "answer_score": ((QUESTION, ANSWER, RUBRIC), (), (SCORE_REPORT,)),
    "weakness_train": ((WEAKNESSES, GOAL), (CANDIDATE_PROFILE,), (TRAINING_PLAN,)),
    "resume_optimize": (
        (RESUME_TEXT, TARGET_ROLE),
        (JD_REQUIREMENTS,),
        (OPTIMIZATION_ADVICE,),
    ),
    "session_summary": ((SESSION_TRANSCRIPT,), (), (SUMMARY,)),
}


def get_node_state_contract(node_name: str) -> NodeStateContract:
    contract = DEFAULT_NODE_STATE_CONTRACTS.get(node_name)
    if contract is None:
        raise KeyError(f"未知节点状态契约: {node_name}")
    return contract


def find_missing_required_inputs(required_inputs: tuple[str, ...], inputs: dict[str, object]) -> list[str]:
    return [input_name for input_name in required_inputs if input_name not in inputs]


def validate_state_entry(key: str, value: object) -> None:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("state key 必须是非空字符串")
    if value is None:
        raise ValueError("state value 不能为 None")
    if _is_empty_state_value(key, value):
        raise ValueError("state value 不能为空")
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError as exc:
        raise ValueError("state value 必须可 JSON 编码") from exc


def _is_empty_state_value(key: str, value: object) -> bool:
    if isinstance(value, str):
        return not value.strip()
    if _allows_empty_state_value(key, value):
        return False
    if isinstance(value, list | dict | tuple):
        return len(value) == 0
    return False


def _allows_empty_state_value(key: str, value: object) -> bool:
    return key in ALLOWED_EMPTY_LIST_STATE_KEYS and isinstance(value, list)
