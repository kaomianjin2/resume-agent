from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from interview_agent.config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
from interview_agent.job_collection import JobCollectionOrchestrator, job_collection_view_model
from interview_agent.job_platform_adapters import JobPlatformAdapter
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.llm import OpenAICompatibleClient
from interview_agent.mock_interview import DEFAULT_MOCK_FOLLOWUP_ROUNDS, DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT
from interview_agent.nodes.registry import NodeRegistry, build_default_registry
from interview_agent.planner import ExecutionPlan, build_execution_plan
from interview_agent.router import RouteResult, route_conversation
from interview_agent.session import SessionStore
from interview_agent.storage import get_knowledge_base_status


ServiceMap = Mapping[str, object]
RegistryBuilder = Callable[[], NodeRegistry]
ServicesBuilder = Callable[[AppConfig], ServiceMap]
ExecutorBuilder = Callable[[Path, NodeRegistry, ServiceMap], NodeExecutor]
MOCK_INTERVIEW_STATE_KEY = "mock_interview_state"
MOCK_INTERVIEW_VIEW_KEY = "mock_interview_view"
JOB_SEARCH_PROFILE_KEY = "job_search_profile"
JOB_SEARCH_FILTERS_KEY = "job_search_filters"
JOB_COLLECTION_PROGRESS_KEY = "job_collection_progress"
ALGORITHM_PRACTICE_BANK_KEY = "algorithm_practice_bank"
DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT = 3
DEFAULT_ALGORITHM_PRACTICE_BANK_PATH = Path(__file__).with_name("algorithm_practice_bank.json")


class GuiRuntimeError(RuntimeError):
    """Raised when the GUI runtime cannot start or execute a request."""


@dataclass(frozen=True)
class GuiRuntime:
    config_path: Path
    config: AppConfig
    registry: NodeRegistry
    session_store: SessionStore
    executor: NodeExecutor
    knowledge_base_status: str
    job_collection_orchestrators: dict[str, JobCollectionOrchestrator]

    def get_status(self) -> dict[str, object]:
        return {
            "config_path": self.config_path.as_posix(),
            "database_path": Path(self.config.storage.database_path).as_posix(),
            "knowledge_base_status": self.knowledge_base_status,
            "ready": self.knowledge_base_status == "ready",
        }

    def create_or_open_session(self, session_id: str) -> dict[str, str]:
        self.session_store.create_session(session_id)
        return {"session_id": session_id, "status": "active"}

    def list_nodes(self) -> list[str]:
        return self.registry.list_names()

    def route_request(self, message: str) -> dict[str, object]:
        return _route_result_to_dict(route_conversation(message, self.registry, None))

    def build_plan(
        self,
        *,
        message: str,
        selected_node: str,
        session_id: str,
    ) -> dict[str, object]:
        plan = build_execution_plan(
            user_message=message,
            selected_node=selected_node,
            session_inputs=self.session_store.get_all_state(session_id),
            registry=self.registry,
        )
        return _plan_to_dict(plan)

    def execute_node(
        self,
        *,
        session_id: str,
        node_name: str,
        inputs: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = self.executor.execute_node(session_id=session_id, node_name=node_name, inputs=inputs)
        return _execution_result_to_dict(result)

    def start_algorithm_practice(
        self,
        *,
        session_id: str,
        practice_topic: str,
        difficulty: str = "medium",
        question_count: int = DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT,
    ) -> dict[str, object]:
        practice_set = _select_algorithm_practice_set(
            self.session_store.get_all_state(session_id).get(ALGORITHM_PRACTICE_BANK_KEY),
            practice_topic=practice_topic,
            question_count=question_count,
        )
        topic = _algorithm_practice_topic(practice_set, practice_topic)
        resolved_difficulty = _algorithm_practice_difficulty(practice_set, difficulty)
        exercises = _algorithm_exercise_view_models(practice_set)[:question_count]
        if not exercises:
            return _failed_algorithm_practice_view_model(session_id, topic, resolved_difficulty, "还没有生成可用于练习的题目。")

        return {
            "session_id": session_id,
            "status": "ready",
            "error_message": None,
            "topic": topic,
            "difficulty": resolved_difficulty,
            "exercises": exercises,
            "current_exercise_index": 0,
            "progress": {
                "current_exercise_index": 1,
                "total_exercises": len(exercises),
            },
        }

    def get_session_state(self, session_id: str) -> dict[str, object]:
        return self.session_store.get_all_state(session_id)

    def prepare_interview_materials(
        self,
        *,
        session_id: str,
        resume_text: str,
        jd_text: str,
    ) -> dict[str, object]:
        missing_inputs = _missing_prep_inputs(resume_text=resume_text, jd_text=jd_text)
        if missing_inputs:
            return {
                "session_id": session_id,
                "status": "missing_inputs",
                "resume_summary": {},
                "jd_summary": {},
                "match_summary": {},
                "missing_inputs": missing_inputs,
            }

        session_state = self.session_store.get_all_state(session_id)
        if not _has_prepared_interview_materials(session_state):
            resume_result = self.executor.execute_node(
                session_id=session_id,
                node_name="resume_parse",
                inputs={"resume_text": resume_text},
            )
            if resume_result.status != "success":
                return _prep_error_view_model(session_id, resume_result)

        if jd_text.strip():
            jd_result = self.executor.execute_node(
                session_id=session_id,
                node_name="jd_parse",
                inputs={"jd_text": jd_text},
            )
            if jd_result.status != "success":
                return _prep_error_view_model(session_id, jd_result)

            match_result = self.executor.execute_node(
                session_id=session_id,
                node_name="jd_match",
                inputs={},
            )
            if match_result.status != "success":
                return _prep_error_view_model(session_id, match_result)

        session_state = self.session_store.get_all_state(session_id)
        return _prep_view_model(session_id, session_state)

    def prepare_job_search_profile(
        self,
        *,
        session_id: str,
        overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        session_state = self.session_store.get_all_state(session_id)
        view_model = _job_search_profile_view_model(session_id, session_state.get("resume_profile"), overrides or {})
        if view_model["status"] != "missing_inputs":
            self.session_store.set_state(session_id, JOB_SEARCH_PROFILE_KEY, view_model)
            self.session_store.set_state(
                session_id,
                JOB_SEARCH_FILTERS_KEY,
                {
                    "hard_filters": view_model["hard_filters"],
                    "ranking_preferences": view_model["ranking_preferences"],
                },
            )
        return view_model

    def collect_job_applications(
        self,
        *,
        session_id: str,
        collection_task_id: str,
        adapters: Mapping[str, JobPlatformAdapter],
        platforms: list[str],
        job_profile: dict[str, object],
        hard_filters: dict[str, object],
        ranking_preferences: dict[str, object],
        keyword: str,
    ) -> dict[str, object]:
        orchestrator = JobCollectionOrchestrator(
            adapters,
            database_path=Path(self.config.storage.database_path),
            progress_callback=lambda result: self._write_job_collection_progress(session_id, result),
        )
        self.job_collection_orchestrators[collection_task_id] = orchestrator
        result = orchestrator.collect(
            collection_task_id=collection_task_id,
            platforms=platforms,
            job_profile=job_profile,
            hard_filters=hard_filters,
            ranking_preferences=ranking_preferences,
            keyword=keyword,
        )
        view_model = job_collection_view_model(result)
        self.session_store.set_state(session_id, JOB_COLLECTION_PROGRESS_KEY, view_model)
        return view_model

    def retry_failed_job_collection_platform(
        self,
        *,
        session_id: str,
        collection_task_id: str,
        platform: str,
        adapter: JobPlatformAdapter | None = None,
    ) -> dict[str, object]:
        orchestrator = self.job_collection_orchestrators.get(collection_task_id)
        if orchestrator is None:
            raise ValueError("采集任务不存在")
        result = orchestrator.retry_failed_platform(collection_task_id=collection_task_id, platform=platform, adapter=adapter)
        return self._write_job_collection_progress(session_id, result)

    def get_job_collection_progress(self, *, session_id: str) -> dict[str, object]:
        view_model = self.session_store.get_state(session_id, JOB_COLLECTION_PROGRESS_KEY)
        return view_model if isinstance(view_model, dict) else _empty_job_collection_progress_view_model()

    def _write_job_collection_progress(self, session_id: str, result: dict[str, object]) -> dict[str, object]:
        view_model = job_collection_view_model(result)
        self.session_store.set_state(session_id, JOB_COLLECTION_PROGRESS_KEY, view_model)
        return view_model

    def start_mock_interview(
        self,
        *,
        session_id: str,
        target_role: str,
        question_count: int = DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT,
        followup_rounds: int = DEFAULT_MOCK_FOLLOWUP_ROUNDS,
        question_type: str = "行为面试",
    ) -> dict[str, object]:
        if not _has_prepared_interview_materials(self.session_store.get_all_state(session_id)):
            return self._write_mock_interview_state(
                session_id,
                _failed_mock_interview_state(session_id, "请先导入简历，并完成面试准备。"),
            )

        question_result = self.executor.execute_node(
            session_id=session_id,
            node_name="question_generate",
            inputs={
                "target_role": target_role,
                "question_count": question_count,
                "question_type": question_type,
            },
        )
        if question_result.status != "success":
            return self._write_mock_interview_state(
                session_id,
                _failed_mock_interview_state(session_id, question_result.error_message or "模拟面试启动失败。"),
            )

        questions = _read_mock_text_list(question_result.output.get("questions"))[:question_count]
        if not questions:
            return self._write_mock_interview_state(
                session_id,
                _failed_mock_interview_state(session_id, "还没有生成可用于模拟面试的问题。"),
            )

        return self._write_mock_interview_state(
            session_id,
            {
                "session_id": session_id,
                "status": "ready_for_answer",
                "error_message": None,
                "target_role": target_role,
                "question_type": question_type,
                "questions": questions,
                "current_question_index": 0,
                "followup_rounds": followup_rounds,
                "question_count": question_count,
                "pending_followups": [],
                "current_followup_index": 0,
                "total_followups": 0,
                "current_prompt_kind": "question",
                "current_prompt_text": questions[0],
                "score_reports": [],
                "transcript": [],
                "review_panel": None,
            },
        )

    def submit_mock_answer(self, *, session_id: str, answer: str) -> dict[str, object]:
        state = self.session_store.get_state(session_id, MOCK_INTERVIEW_STATE_KEY)
        if not isinstance(state, dict):
            return _idle_mock_interview_view_model(session_id)
        if state.get("status") in {"completed", "failed", "ended", "idle"}:
            return _mock_interview_view_model(state)
        if not str(answer).strip():
            return self._write_mock_interview_state(session_id, {**state, "status": "answer_required", "error_message": "请先输入当前题回答。"})

        current_prompt_text = str(state.get("current_prompt_text", ""))
        current_prompt_kind = str(state.get("current_prompt_kind", "question"))
        transcript = list(state.get("transcript", []))
        score_reports = list(state.get("score_reports", []))
        score_report = _score_mock_answer(self.executor, session_id, current_prompt_text, str(answer).strip())
        score_reports.append(score_report)
        transcript.append(
            {
                "prompt_kind": current_prompt_kind,
                "prompt_text": current_prompt_text,
                "answer": str(answer).strip(),
                "score": score_report.get("score"),
            }
        )

        next_state = {
            **state,
            "status": "ready_for_answer",
            "error_message": None,
            "transcript": transcript,
            "score_reports": score_reports,
        }
        if current_prompt_kind == "question":
            followup_result = self.executor.execute_node(
                session_id=session_id,
                node_name="mock_followup",
                inputs={"question": current_prompt_text, "answer": str(answer).strip()},
            )
            if followup_result.status == "success":
                followups = _read_mock_text_list(followup_result.output.get("followup_questions"))[: int(state.get("followup_rounds", 0))]
                if followups:
                    return self._write_mock_interview_state(
                        session_id,
                        {
                            **next_state,
                            "pending_followups": followups[1:],
                            "current_followup_index": 1,
                            "total_followups": len(followups),
                            "current_prompt_kind": "followup",
                            "current_prompt_text": followups[0],
                        },
                    )

        pending_followups = list(next_state.get("pending_followups", []))
        if current_prompt_kind == "followup" and pending_followups:
            return self._write_mock_interview_state(
                session_id,
                {
                    **next_state,
                    "pending_followups": pending_followups[1:],
                    "current_followup_index": int(next_state.get("current_followup_index", 0)) + 1,
                    "current_prompt_kind": "followup",
                    "current_prompt_text": pending_followups[0],
                },
            )

        questions = list(next_state.get("questions", []))
        next_question_index = int(next_state.get("current_question_index", 0)) + 1
        if next_question_index < len(questions):
            return self._write_mock_interview_state(
                session_id,
                {
                    **next_state,
                    "current_question_index": next_question_index,
                    "pending_followups": [],
                    "current_followup_index": 0,
                    "total_followups": 0,
                    "current_prompt_kind": "question",
                    "current_prompt_text": questions[next_question_index],
                },
            )

        return self._write_mock_interview_state(
            session_id,
            {
                **next_state,
                "status": "completed",
                "pending_followups": [],
                "current_followup_index": 0,
                "total_followups": 0,
                "current_prompt_kind": "",
                "current_prompt_text": "",
                "review_panel": _build_mock_review_panel(score_reports),
            },
        )

    def end_mock_interview(self, session_id: str) -> dict[str, object]:
        ended_view_model = {
            "session_id": session_id,
            "status": "ended",
            "error_message": None,
            "current_prompt": None,
            "progress": _empty_mock_progress(),
            "review_panel": None,
            "transcript": [],
        }
        self._write_mock_interview_state(session_id, _idle_mock_interview_state(session_id))
        return ended_view_model

    def _write_mock_interview_state(self, session_id: str, state: dict[str, object]) -> dict[str, object]:
        self.session_store.set_state(session_id, MOCK_INTERVIEW_STATE_KEY, state)
        view_model = _mock_interview_view_model(state)
        self.session_store.set_state(session_id, MOCK_INTERVIEW_VIEW_KEY, view_model)
        return view_model


def load_runtime(
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    *,
    registry_builder: RegistryBuilder = build_default_registry,
    services_builder: ServicesBuilder | None = None,
    executor_builder: ExecutorBuilder = NodeExecutor,
) -> GuiRuntime:
    resolved_config_path = Path(config_path)
    config = load_config(resolved_config_path)
    database_path = Path(config.storage.database_path)
    knowledge_base_status = get_knowledge_base_status(database_path)
    if knowledge_base_status != "ready":
        raise GuiRuntimeError("知识库未就绪，请先执行离线构建")

    registry = registry_builder()
    resolved_services_builder = services_builder or _build_default_services
    services = resolved_services_builder(config)
    return GuiRuntime(
        config_path=resolved_config_path,
        config=config,
        registry=registry,
        session_store=SessionStore(database_path),
        executor=executor_builder(database_path, registry, services),
        knowledge_base_status=knowledge_base_status,
        job_collection_orchestrators={},
    )


def create_or_open_session(runtime: GuiRuntime, session_id: str) -> dict[str, str]:
    return runtime.create_or_open_session(session_id)


def list_nodes(runtime: GuiRuntime) -> list[str]:
    return runtime.list_nodes()


def route_request(runtime: GuiRuntime, message: str) -> dict[str, object]:
    return runtime.route_request(message)


def build_plan(
    runtime: GuiRuntime,
    *,
    message: str,
    selected_node: str,
    session_id: str,
) -> dict[str, object]:
    return runtime.build_plan(message=message, selected_node=selected_node, session_id=session_id)


def execute_node(
    runtime: GuiRuntime,
    *,
    session_id: str,
    node_name: str,
    inputs: dict[str, object] | None = None,
) -> dict[str, object]:
    return runtime.execute_node(session_id=session_id, node_name=node_name, inputs=inputs)


def get_session_state(runtime: GuiRuntime, session_id: str) -> dict[str, object]:
    return runtime.get_session_state(session_id)


def prepare_interview_materials(
    runtime: GuiRuntime,
    *,
    session_id: str,
    resume_text: str,
    jd_text: str,
) -> dict[str, object]:
    return runtime.prepare_interview_materials(session_id=session_id, resume_text=resume_text, jd_text=jd_text)


def prepare_job_search_profile(
    runtime: GuiRuntime,
    *,
    session_id: str,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    return runtime.prepare_job_search_profile(session_id=session_id, overrides=overrides)


def collect_job_applications(
    runtime: GuiRuntime,
    *,
    session_id: str,
    collection_task_id: str,
    adapters: Mapping[str, JobPlatformAdapter],
    platforms: list[str],
    job_profile: dict[str, object],
    hard_filters: dict[str, object],
    ranking_preferences: dict[str, object],
    keyword: str,
) -> dict[str, object]:
    return runtime.collect_job_applications(
        session_id=session_id,
        collection_task_id=collection_task_id,
        adapters=adapters,
        platforms=platforms,
        job_profile=job_profile,
        hard_filters=hard_filters,
        ranking_preferences=ranking_preferences,
        keyword=keyword,
    )


def get_job_collection_progress(runtime: GuiRuntime, *, session_id: str) -> dict[str, object]:
    return runtime.get_job_collection_progress(session_id=session_id)


def retry_failed_job_collection_platform(
    runtime: GuiRuntime,
    *,
    session_id: str,
    collection_task_id: str,
    platform: str,
    adapter: JobPlatformAdapter | None = None,
) -> dict[str, object]:
    return runtime.retry_failed_job_collection_platform(
        session_id=session_id,
        collection_task_id=collection_task_id,
        platform=platform,
        adapter=adapter,
    )


def start_mock_interview(
    runtime: GuiRuntime,
    *,
    session_id: str,
    target_role: str,
    question_count: int = DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT,
    followup_rounds: int = DEFAULT_MOCK_FOLLOWUP_ROUNDS,
    question_type: str = "行为面试",
) -> dict[str, object]:
    return runtime.start_mock_interview(
        session_id=session_id,
        target_role=target_role,
        question_count=question_count,
        followup_rounds=followup_rounds,
        question_type=question_type,
    )


def start_algorithm_practice(
    runtime: GuiRuntime,
    *,
    session_id: str,
    practice_topic: str,
    difficulty: str = "medium",
    question_count: int = DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT,
) -> dict[str, object]:
    return runtime.start_algorithm_practice(
        session_id=session_id,
        practice_topic=practice_topic,
        difficulty=difficulty,
        question_count=question_count,
    )


def submit_mock_answer(runtime: GuiRuntime, *, session_id: str, answer: str) -> dict[str, object]:
    return runtime.submit_mock_answer(session_id=session_id, answer=answer)


def end_mock_interview(runtime: GuiRuntime, session_id: str) -> dict[str, object]:
    return runtime.end_mock_interview(session_id)


def _build_default_services(config: AppConfig) -> dict[str, object]:
    database_path = Path(config.storage.database_path)
    return {
        "llm": OpenAICompatibleClient(config.llm),
        "retriever": SQLiteHybridRetriever(
            database_path,
            config.embedding,
            default_limit=config.knowledge_base.top_k,
        ),
    }


def _route_result_to_dict(route_result: RouteResult) -> dict[str, object]:
    return {
        "selected_node": route_result.selected_node,
        "candidate_nodes": route_result.candidate_nodes,
        "via": route_result.via,
        "needs_user_choice": route_result.needs_user_choice,
    }


def _plan_to_dict(plan: ExecutionPlan) -> dict[str, object]:
    return {
        "plan_id": plan.plan_id,
        "user_message": plan.user_message,
        "steps": [
            {
                "node_name": step.node_name,
                "title": step.title,
                "description": step.description,
            }
            for step in plan.steps
        ],
        "requires_confirmation": plan.requires_confirmation,
        "missing_inputs": plan.missing_inputs,
        "summary": plan.summary,
    }


def _execution_result_to_dict(result: NodeExecutionResult) -> dict[str, object]:
    return {
        "run_id": result.run_id,
        "session_id": result.session_id,
        "node_name": result.node_name,
        "status": result.status,
        "output": result.output,
        "missing_inputs": result.missing_inputs,
        "error_message": result.error_message,
    }


def _missing_prep_inputs(*, resume_text: str, jd_text: str) -> list[str]:
    del jd_text
    missing_inputs = []
    if not resume_text.strip():
        missing_inputs.append("resume_text")
    return missing_inputs


def _has_prepared_interview_materials(session_state: dict[str, object]) -> bool:
    return isinstance(session_state.get("candidate_profile"), dict) or isinstance(session_state.get("resume_profile"), dict)


def _read_mock_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _select_algorithm_practice_set(
    practice_bank: object,
    *,
    practice_topic: str,
    question_count: int,
) -> dict[str, object]:
    if not isinstance(practice_bank, dict):
        practice_bank = _load_default_algorithm_practice_bank()

    exercises = _algorithm_exercise_bank_items(practice_bank)
    matched_exercises = _matching_algorithm_exercises(exercises, practice_topic)
    selected_exercises = matched_exercises[:question_count] if matched_exercises else exercises[:question_count]
    return {
        "topic": _text_value(practice_bank.get("topic"), practice_topic),
        "difficulty": _text_value(practice_bank.get("difficulty"), "medium"),
        "exercises": selected_exercises,
    }


def _load_default_algorithm_practice_bank() -> dict[str, object]:
    bank = json.loads(DEFAULT_ALGORITHM_PRACTICE_BANK_PATH.read_text(encoding="utf-8"))
    if not isinstance(bank, dict):
        raise RuntimeError("内部算法题库必须是 JSON 对象")
    return bank


def _algorithm_exercise_bank_items(practice_bank: dict[str, object]) -> list[object]:
    exercises = practice_bank.get("exercises")
    if isinstance(exercises, list):
        return exercises

    practice_sets = practice_bank.get("practice_sets")
    if not isinstance(practice_sets, list):
        return []

    bank_items: list[object] = []
    for practice_set in practice_sets:
        if not isinstance(practice_set, dict):
            continue
        practice_set_exercises = practice_set.get("exercises")
        if isinstance(practice_set_exercises, list):
            bank_items.extend(practice_set_exercises)
    return bank_items


def _matching_algorithm_exercises(exercises: list[object], practice_topic: str) -> list[object]:
    topic_keyword = practice_topic.strip().lower()
    if not topic_keyword:
        return exercises

    return [exercise for exercise in exercises if topic_keyword in _algorithm_exercise_search_text(exercise)]


def _algorithm_exercise_search_text(exercise: object) -> str:
    if isinstance(exercise, str):
        return exercise.lower()
    if not isinstance(exercise, dict):
        return ""

    search_parts = [
        _text_value(_first_present_value(exercise, ("title", "name")), ""),
        _text_value(_first_present_value(exercise, ("prompt", "description", "question", "content")), ""),
        " ".join(_list_value(exercise.get("tags"))),
    ]
    return " ".join(search_parts).lower()


def _algorithm_practice_topic(practice_set: object, fallback: str) -> str:
    if not isinstance(practice_set, dict):
        return fallback
    return _text_value(practice_set.get("topic"), fallback)


def _algorithm_practice_difficulty(practice_set: object, fallback: str) -> str:
    if not isinstance(practice_set, dict):
        return fallback
    return _text_value(practice_set.get("difficulty"), fallback)


def _algorithm_exercise_view_models(practice_set: object) -> list[dict[str, object]]:
    if not isinstance(practice_set, dict):
        return []
    exercises = practice_set.get("exercises")
    if not isinstance(exercises, list):
        return []

    view_models: list[dict[str, object]] = []
    for exercise_index, exercise in enumerate(exercises, start=1):
        view_model = _algorithm_exercise_view_model(exercise, exercise_index)
        if view_model:
            view_models.append(view_model)
    return view_models


def _algorithm_exercise_view_model(exercise: object, exercise_index: int) -> dict[str, object]:
    if isinstance(exercise, str):
        exercise_text = exercise.strip()
        if not exercise_text:
            return {}
        return {
            "id": f"exercise-{exercise_index}",
            "title": f"练习题 {exercise_index}",
            "prompt": exercise_text,
            "tags": [],
            "constraints": [],
            "examples": [],
            "edge_cases": [],
        }
    if not isinstance(exercise, dict):
        return {}

    title = _text_value(_first_present_value(exercise, ("title", "name")), f"练习题 {exercise_index}")
    prompt = _text_value(_first_present_value(exercise, ("prompt", "description", "question", "content")), title)
    return {
        "id": f"exercise-{exercise_index}",
        "title": title,
        "prompt": prompt,
        "tags": _list_value(exercise.get("tags")),
        "constraints": _list_value(exercise.get("constraints")),
        "examples": _list_value(exercise.get("examples")),
        "edge_cases": _list_value(_first_present_value(exercise, ("edge_cases", "edgeCases", "boundaries"))),
    }


def _failed_algorithm_practice_view_model(
    session_id: str,
    topic: str,
    difficulty: str,
    error_message: str,
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "status": "failed",
        "error_message": error_message,
        "topic": topic,
        "difficulty": difficulty,
        "exercises": [],
        "current_exercise_index": 0,
        "progress": {
            "current_exercise_index": 0,
            "total_exercises": 0,
        },
    }


def _score_mock_answer(
    executor: NodeExecutor,
    session_id: str,
    question: str,
    answer: str,
) -> dict[str, object]:
    score_result = executor.execute_node(
        session_id=session_id,
        node_name="answer_score",
        inputs={
            "question": question,
            "answer": answer,
            "rubric": "按完整性、准确性、结构化表达和项目细节评分，并输出 gaps、suggestions、reference_answer。",
        },
    )
    if score_result.status != "success":
        return {"score": 0, "gaps": ["评分失败"], "suggestions": ["请重试本轮回答评分。"], "reference_answer": []}
    score_report = score_result.output.get("score_report")
    if isinstance(score_report, dict):
        return score_report
    return {"score": 0, "gaps": ["评分结果缺失"], "suggestions": ["请重试本轮回答评分。"], "reference_answer": []}


def _build_mock_review_panel(score_reports: list[dict[str, object]]) -> dict[str, object]:
    scores = [float(score_report["score"]) for score_report in score_reports if isinstance(score_report.get("score"), int | float)]
    average_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    risks: list[str] = []
    suggestions: list[str] = []
    for score_report in score_reports:
        risks.extend(_read_mock_text_list(score_report.get("gaps")))
        suggestions.extend(_read_mock_text_list(score_report.get("suggestions")))
    return {
        "average_score": average_score,
        "risks": risks,
        "suggestions": suggestions,
    }


def _mock_interview_view_model(state: dict[str, object]) -> dict[str, object]:
    current_prompt_text = str(state.get("current_prompt_text", "")).strip()
    current_prompt_kind = str(state.get("current_prompt_kind", "")).strip()
    current_question_index = int(state.get("current_question_index", 0))
    current_followup_index = int(state.get("current_followup_index", 0))
    current_prompt = None
    if current_prompt_text:
        current_prompt = {
            "kind": current_prompt_kind,
            "label": f"第 {current_question_index + 1} 题" if current_prompt_kind == "question" else f"追问 {current_followup_index}",
            "text": current_prompt_text,
        }
    return {
        "session_id": state["session_id"],
        "status": state["status"],
        "error_message": state.get("error_message"),
        "current_prompt": current_prompt,
        "progress": {
            "current_question_index": current_question_index + 1 if state["status"] not in {"idle", "ended", "failed"} and state.get("questions") else current_question_index,
            "total_questions": len(list(state.get("questions", []))),
            "current_followup_index": current_followup_index,
            "total_followups": int(state.get("total_followups", 0)),
        },
        "review_panel": state.get("review_panel"),
        "transcript": list(state.get("transcript", [])),
    }


def _failed_mock_interview_state(session_id: str, error_message: str) -> dict[str, object]:
    return {
        **_idle_mock_interview_state(session_id),
        "status": "failed",
        "error_message": error_message,
    }


def _idle_mock_interview_view_model(session_id: str) -> dict[str, object]:
    return _mock_interview_view_model(_idle_mock_interview_state(session_id))


def _idle_mock_interview_state(session_id: str) -> dict[str, object]:
    return {
        "session_id": session_id,
        "status": "idle",
        "error_message": None,
        "question_type": "行为面试",
        "questions": [],
        "current_question_index": 0,
        "followup_rounds": 0,
        "question_count": 0,
        "pending_followups": [],
        "current_followup_index": 0,
        "total_followups": 0,
        "current_prompt_kind": "",
        "current_prompt_text": "",
        "score_reports": [],
        "transcript": [],
        "review_panel": None,
    }


def _empty_mock_progress() -> dict[str, int]:
    return {
        "current_question_index": 0,
        "total_questions": 0,
        "current_followup_index": 0,
        "total_followups": 0,
    }


def _empty_job_collection_progress_view_model() -> dict[str, object]:
    return {
        "status": "idle",
        "summary": {
            "platform_count": 0,
            "completed_platform_count": 0,
            "failed_platform_count": 0,
            "collected_job_count": 0,
        },
        "platforms": {},
        "jobs": [],
    }


def _prep_error_view_model(session_id: str, result: NodeExecutionResult) -> dict[str, object]:
    return {
        "session_id": session_id,
        "status": result.status,
        "resume_summary": {},
        "jd_summary": {},
        "match_summary": {},
        "missing_inputs": result.missing_inputs,
        "error_message": result.error_message,
    }


def _prep_view_model(session_id: str, session_state: dict[str, object]) -> dict[str, object]:
    return {
        "session_id": session_id,
        "status": "ready",
        "resume_summary": _resume_summary(session_state.get("resume_profile")),
        "jd_summary": _jd_summary(session_state.get("jd_requirements")),
        "match_summary": _match_summary(session_state.get("match_report"), include_empty=True),
        "missing_inputs": [],
    }


def _job_search_profile_view_model(
    session_id: str,
    resume_profile: object,
    overrides: dict[str, object],
) -> dict[str, object]:
    if not isinstance(resume_profile, dict):
        return {
            "session_id": session_id,
            "status": "missing_inputs",
            "job_profile": {},
            "default_search_keywords": [],
            "hard_filters": {},
            "ranking_preferences": {},
            "pending_confirmation_fields": ["resume_profile"],
        }

    basic_info = _dict_value(resume_profile.get("basic_info"))
    salary_expectation = _dict_value(resume_profile.get("salary_expectation"))
    technical_skills = _overridden_list(overrides, "technical_skills", _resume_list(resume_profile, ("skills", "core_skills", "technical_skills")))
    years_of_experience = _overridden_value(overrides, "years_of_experience", _resume_years_of_experience(resume_profile, basic_info))
    cities = _overridden_list(overrides, "cities", _resume_list(resume_profile, ("preferred_cities", "cities", "locations")))
    target_roles = _resume_list(resume_profile, ("target_roles", "preferred_roles", "roles"))
    if not target_roles:
        target_roles = [_resume_headline(resume_profile, basic_info)]

    confirmed_fields = _confirmed_job_profile_fields(resume_profile, overrides)
    education = _overridden_value(overrides, "education", _resume_education(resume_profile, basic_info))
    salary_min = _overridden_value(overrides, "salary_min", salary_expectation.get("min"))
    salary_max = _overridden_value(overrides, "salary_max", salary_expectation.get("max"))
    hard_filters = {
        "cities": cities,
        "remote_policy": _overridden_value(overrides, "remote_policy", _first_present_value(resume_profile, ("remote_preference", "remote_policy"))),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "levels": _overridden_list(overrides, "levels", _resume_list(resume_profile, ("preferred_levels", "levels"))),
        "experience_years_min": _overridden_value(overrides, "experience_years_min", years_of_experience),
        "experience_years_max": _overridden_value(overrides, "experience_years_max", years_of_experience),
        "education": education,
        "company_blacklist": _overridden_list(overrides, "company_blacklist", _resume_list(resume_profile, ("company_blacklist", "blacklist_companies"))),
        "company_whitelist": _overridden_list(overrides, "company_whitelist", _resume_list(resume_profile, ("company_whitelist", "whitelist_companies"))),
    }
    ranking_preferences = {
        "industries": _overridden_list(overrides, "industries", _resume_list(resume_profile, ("preferred_industries", "industries"))),
        "company_sizes": _overridden_list(overrides, "company_sizes", _resume_list(resume_profile, ("preferred_company_sizes", "company_sizes"))),
        "funding_stages": _overridden_list(overrides, "funding_stages", _resume_list(resume_profile, ("preferred_funding_stages", "funding_stages"))),
        "technical_skills": technical_skills,
        "benefits": _overridden_list(overrides, "benefits", _resume_list(resume_profile, ("preferred_benefits", "benefits"))),
        "published_within_days": _overridden_value(overrides, "published_within_days", resume_profile.get("published_within_days")),
    }
    search_preferences = {**hard_filters, **ranking_preferences}
    job_profile = {
        "candidate_name": _text_value(_first_present_value(resume_profile, ("name",)) or basic_info.get("name"), "未命名候选人"),
        "target_roles": target_roles,
        "headline": _resume_headline(resume_profile, basic_info),
        "years_of_experience": years_of_experience,
        "education_level": education,
        "technical_skills": technical_skills,
        "project_keywords": _resume_list(resume_profile, ("projects", "project_keywords", "project_experience", "project_experiences")),
        "search_preferences": search_preferences,
    }
    pending_fields = _pending_job_profile_fields(job_profile, hard_filters, ranking_preferences, confirmed_fields)
    return {
        "session_id": session_id,
        "status": "needs_confirmation" if pending_fields else "ready",
        "job_profile": job_profile,
        "default_search_keywords": _default_job_search_keywords(target_roles, technical_skills),
        "hard_filters": hard_filters,
        "ranking_preferences": ranking_preferences,
        "pending_confirmation_fields": pending_fields,
    }


def _overridden_value(overrides: dict[str, object], key: str, fallback: object) -> object:
    return overrides[key] if key in overrides else fallback


def _overridden_list(overrides: dict[str, object], key: str, fallback: list[str]) -> list[str]:
    return _list_value(overrides.get(key)) if key in overrides else fallback


def _resume_list(resume_profile: dict[str, object], keys: tuple[str, ...]) -> list[str]:
    return _merged_list_values(resume_profile, keys)


def _resume_years_of_experience(resume_profile: dict[str, object], basic_info: dict[str, object]) -> object:
    return _first_present_value(resume_profile, ("years_of_experience", "work_years", "experience_years")) or basic_info.get("years_of_experience")


def _resume_education(resume_profile: dict[str, object], basic_info: dict[str, object]) -> object:
    return _first_present_value(resume_profile, ("education_level", "education")) or basic_info.get("education_level")


def _confirmed_job_profile_fields(resume_profile: dict[str, object], overrides: dict[str, object]) -> set[str]:
    field_sources = {
        "technical_skills": ("technical_skills", "skills", "core_skills"),
        "years_of_experience": ("years_of_experience", "work_years", "experience_years"),
        "cities": ("cities", "preferred_cities", "locations"),
        "remote_policy": ("remote_policy", "remote_preference"),
        "salary": ("salary_min", "salary_max", "salary_expectation"),
        "levels": ("levels", "preferred_levels"),
        "education": ("education", "education_level"),
        "industries": ("industries", "preferred_industries"),
        "company_sizes": ("company_sizes", "preferred_company_sizes"),
        "funding_stages": ("funding_stages", "preferred_funding_stages"),
        "benefits": ("benefits", "preferred_benefits"),
        "published_within_days": ("published_within_days",),
        "company_blacklist": ("company_blacklist", "blacklist_companies"),
        "company_whitelist": ("company_whitelist", "whitelist_companies"),
    }
    return {
        field_name
        for field_name, source_keys in field_sources.items()
        if any(source_key in overrides or source_key in resume_profile for source_key in source_keys)
    }


def _pending_job_profile_fields(
    job_profile: dict[str, object],
    hard_filters: dict[str, object],
    ranking_preferences: dict[str, object],
    confirmed_fields: set[str],
) -> list[str]:
    checks = (
        ("technical_skills", ranking_preferences.get("technical_skills")),
        ("years_of_experience", job_profile.get("years_of_experience")),
        ("cities", hard_filters.get("cities")),
        ("remote_policy", hard_filters.get("remote_policy")),
        ("salary", (hard_filters.get("salary_min"), hard_filters.get("salary_max"))),
        ("levels", hard_filters.get("levels")),
        ("education", hard_filters.get("education")),
        ("industries", ranking_preferences.get("industries")),
        ("company_sizes", ranking_preferences.get("company_sizes")),
        ("funding_stages", ranking_preferences.get("funding_stages")),
        ("benefits", ranking_preferences.get("benefits")),
        ("published_within_days", ranking_preferences.get("published_within_days")),
        ("company_blacklist", hard_filters.get("company_blacklist")),
        ("company_whitelist", hard_filters.get("company_whitelist")),
    )
    return [field_name for field_name, value in checks if field_name not in confirmed_fields and _needs_job_profile_confirmation(value)]


def _needs_job_profile_confirmation(value: object) -> bool:
    if isinstance(value, tuple):
        return all(_needs_job_profile_confirmation(item) for item in value)
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value
    return False


def _default_job_search_keywords(target_roles: list[str], technical_skills: list[str]) -> list[str]:
    primary_skill = technical_skills[0] if technical_skills else ""
    keywords: list[str] = []
    for role in target_roles:
        keyword = " ".join(part for part in (role, primary_skill) if part)
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    return keywords


def _resume_summary(resume_profile: object) -> dict[str, object]:
    if not isinstance(resume_profile, dict):
        return {}
    basic_info = _dict_value(resume_profile.get("basic_info"))
    return {
        "name": _text_value(_first_present_value(resume_profile, ("name",)) or basic_info.get("name"), "未命名候选人"),
        "headline": _resume_headline(resume_profile, basic_info),
        "highlights": _merged_list_values(
            resume_profile,
            (
                "highlights",
                "core_skills",
                "skills",
                "strengths",
                "projects",
                "project_experience",
                "project_experiences",
                "achievements",
                "responsibilities",
                "experience",
            ),
        ),
    }


def _jd_summary(jd_requirements: object) -> dict[str, object]:
    if not isinstance(jd_requirements, dict):
        return {}
    qualification = _dict_value(jd_requirements.get("任职资格"))
    return {
        "role": _text_value(
            _first_present_value(jd_requirements, ("role", "title", "position", "job_title", "岗位名称")),
            "未命名岗位",
        ),
        "focus": _merged_nested_list_values(
            jd_requirements,
            qualification,
            (
                "focus",
                "must_have",
                "requirements",
                "required_skills",
                "skills",
                "responsibilities",
                "岗位职责",
                "技能要求",
                "经验要求",
                "优先条件",
            ),
        ),
    }


def _match_summary(match_report: object, *, include_empty: bool = False) -> dict[str, object]:
    if not isinstance(match_report, dict):
        if include_empty:
            return {
                "score": "未评分",
                "strengths": [],
                "risks": [],
                "follow_up_focus": [],
            }
        return {}
    return {
        "score": _first_present_value(match_report, ("score", "overall_match_score")) or "未评分",
        "strengths": _list_value(_first_present_value(match_report, ("strengths", "matched_points", "matched_skills", "matches"))),
        "risks": _list_value(_first_present_value(match_report, ("risks", "weaknesses", "gaps", "missing_skills", "potential_gaps"))),
        "follow_up_focus": _list_value(
            _first_present_value(
                match_report,
                ("follow_up_focus", "interview_focus", "followups", "follow_up_questions", "interview_focus_suggestions"),
            )
        ),
    }


def _first_present_value(mapping: dict[str, object], keys: tuple[str, ...]) -> object:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and value:
            return value
        if isinstance(value, int | float):
            return value
    return None


def _text_value(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _list_value(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value]
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        values.extend(_flatten_summary_item(item))
    return values


def _merged_list_values(mapping: dict[str, object], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    seen_values: set[str] = set()
    for key in keys:
        for item in _list_value(mapping.get(key)):
            if item in seen_values:
                continue
            seen_values.add(item)
            values.append(item)
    return values


def _dict_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _resume_headline(resume_profile: dict[str, object], basic_info: dict[str, object]) -> str:
    explicit_headline = _first_present_value(resume_profile, ("headline", "summary", "profile_summary", "title", "role"))
    if isinstance(explicit_headline, str) and explicit_headline.strip():
        return explicit_headline

    headline_parts = [
        _text_value(basic_info.get("primary_position"), ""),
        _format_years_of_experience(basic_info.get("years_of_experience")),
        _text_value(basic_info.get("education_level"), ""),
    ]
    headline = "，".join(part for part in headline_parts if part)
    return headline or "暂无简历摘要"


def _format_years_of_experience(value: object) -> str:
    if isinstance(value, int | float):
        return f"{value:g} 年经验"
    if isinstance(value, str) and value.strip():
        return value
    return ""


def _merged_nested_list_values(
    first_mapping: dict[str, object],
    second_mapping: dict[str, object],
    keys: tuple[str, ...],
) -> list[str]:
    values = _merged_list_values(first_mapping, keys)
    seen_values = set(values)
    for item in _merged_list_values(second_mapping, keys):
        if item in seen_values:
            continue
        seen_values.add(item)
        values.append(item)
    return values


def _flatten_summary_item(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value]
    if not isinstance(value, dict):
        return []

    flattened_values: list[str] = []
    for key in ("project_name", "name", "description", "impact"):
        text = _text_value(value.get(key), "")
        if text:
            flattened_values.append(text)
    for key in ("responsibilities", "achievements", "technologies"):
        flattened_values.extend(_list_value(value.get(key)))
    return flattened_values
