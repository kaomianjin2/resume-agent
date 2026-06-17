from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from interview_agent.config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
from interview_agent.job_collection import JobCollectionOrchestrator, job_collection_view_model
from interview_agent.job_platform_adapters import ConfirmationApplicationRequest, JobPlatformAdapter, StandardJob
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.llm import OpenAICompatibleClient
from interview_agent.mock_interview import DEFAULT_MOCK_FOLLOWUP_ROUNDS, DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT
from interview_agent.nodes.registry import NodeRegistry, build_default_registry
from interview_agent.planner import ExecutionPlan, build_execution_plan
from interview_agent.router import RouteResult, route_conversation
from interview_agent.session import SessionStore
from interview_agent.storage import get_confirmation_batch, get_job_application_by_id, get_knowledge_base_status, update_job_application_status


ServiceMap = Mapping[str, object]
RegistryBuilder = Callable[[], NodeRegistry]
ServicesBuilder = Callable[[AppConfig], ServiceMap]
ExecutorBuilder = Callable[[Path, NodeRegistry, ServiceMap], NodeExecutor]
MOCK_INTERVIEW_STATE_KEY = "mock_interview_state"
MOCK_INTERVIEW_VIEW_KEY = "mock_interview_view"
JOB_SEARCH_PROFILE_KEY = "job_search_profile"
JOB_SEARCH_FILTERS_KEY = "job_search_filters"
JOB_COLLECTION_PROGRESS_KEY = "job_collection_progress"
JOB_FILTER_RESULTS_KEY = "job_filter_results"
JOB_EVALUATION_RESULTS_KEY = "job_evaluation_results"
JOB_REVALIDATION_RESULTS_KEY = "job_revalidation_results"
JOB_BOSS_SUBMIT_RESULTS_KEY = "job_boss_submit_results"
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

    def filter_and_rank_jobs(
        self,
        *,
        session_id: str,
        jobs: list[StandardJob],
        hard_filters: dict[str, object],
        ranking_preferences: dict[str, object],
        already_applied_job_ids: list[str] | None = None,
    ) -> dict[str, object]:
        applied_ids = set(already_applied_job_ids or [])
        candidate_jobs: list[dict[str, object]] = []
        excluded_jobs: list[dict[str, object]] = []
        for job in jobs:
            exclusion_reason = _hard_filter_exclusion_reason(job, hard_filters, applied_ids)
            if exclusion_reason is not None:
                excluded_jobs.append({"platform_job_id": job.platform_job_id, "platform": job.platform, "reason": exclusion_reason})
                continue
            low_confidence_fields = _low_confidence_fields(job)
            rank_score = _ranking_score(job, ranking_preferences)
            candidate_jobs.append({
                "job": job,
                "low_confidence_fields": low_confidence_fields,
                "rank_score": rank_score,
            })
        candidate_jobs.sort(key=lambda item: item["rank_score"], reverse=True)
        from dataclasses import asdict
        ranked_jobs = [
            {
                **asdict(item["job"]),
                "low_confidence_fields": item["low_confidence_fields"],
                "rank_score": item["rank_score"],
            }
            for item in candidate_jobs
        ]
        view_model = {
            "session_id": session_id,
            "status": "ready",
            "total_job_count": len(jobs),
            "candidate_count": len(ranked_jobs),
            "excluded_count": len(excluded_jobs),
            "candidates": ranked_jobs,
            "excluded": excluded_jobs,
            "hard_filters_applied": {key: value for key, value in hard_filters.items() if value},
            "ranking_preferences_applied": {key: value for key, value in ranking_preferences.items() if value},
        }
        self.session_store.set_state(session_id, JOB_FILTER_RESULTS_KEY, view_model)
        return view_model

    def get_job_filter_results(self, *, session_id: str) -> dict[str, object] | None:
        view_model = self.session_store.get_state(session_id, JOB_FILTER_RESULTS_KEY)
        return view_model if isinstance(view_model, dict) else None

    def evaluate_jobs(
        self,
        *,
        session_id: str,
        resume_profile: dict[str, object],
        jobs: list[StandardJob],
    ) -> dict[str, object]:
        evaluations: list[dict[str, object]] = []
        failed_jobs: list[dict[str, object]] = []
        for job in jobs:
            job_structured = _job_structured_from_standard_job(job)
            try:
                result = self.executor.execute_node(
                    session_id=session_id,
                    node_name="job_evaluation",
                    inputs={
                        "resume_profile": resume_profile,
                        "job_structured": job_structured,
                        "jd_text": job.jd_text or job.title,
                    },
                )
                if result.status != "success":
                    failed_jobs.append({
                        "platform": job.platform,
                        "platform_job_id": job.platform_job_id,
                        "error_message": result.error_message or "评估节点执行失败",
                    })
                    continue
                evaluation_report = result.output.get("evaluation_report")
                if not isinstance(evaluation_report, dict):
                    failed_jobs.append({
                        "platform": job.platform,
                        "platform_job_id": job.platform_job_id,
                        "error_message": "评估报告输出缺失",
                    })
                    continue
                evaluations.append({
                    "platform": job.platform,
                    "platform_job_id": job.platform_job_id,
                    "title": job.title,
                    "company_name": job.company_name,
                    "evaluation_report": evaluation_report,
                })
            except Exception as exc:
                failed_jobs.append({
                    "platform": job.platform,
                    "platform_job_id": job.platform_job_id,
                    "error_message": str(exc),
                })
        view_model = {
            "session_id": session_id,
            "status": "ready",
            "total_job_count": len(jobs),
            "evaluated_count": len(evaluations),
            "failed_count": len(failed_jobs),
            "evaluations": evaluations,
            "failed_jobs": failed_jobs,
        }
        self.session_store.set_state(session_id, JOB_EVALUATION_RESULTS_KEY, view_model)
        return view_model

    def get_job_evaluation_results(self, *, session_id: str) -> dict[str, object] | None:
        view_model = self.session_store.get_state(session_id, JOB_EVALUATION_RESULTS_KEY)
        return view_model if isinstance(view_model, dict) else None

    def revalidate_confirmation_batch(
        self,
        *,
        session_id: str,
        confirmation_batch_id: str,
        adapters: Mapping[str, JobPlatformAdapter],
    ) -> dict[str, object]:
        database_path = Path(self.config.storage.database_path)
        batch = get_confirmation_batch(database_path, confirmation_batch_id=confirmation_batch_id)
        if batch is None:
            view_model = {
                "session_id": session_id,
                "confirmation_batch_id": confirmation_batch_id,
                "status": "not_found",
                "submittable_jobs": [],
                "skipped_jobs": [],
                "stale_reasons": [],
                "total_count": 0,
                "submittable_count": 0,
                "skipped_count": 0,
            }
            self.session_store.set_state(session_id, JOB_REVALIDATION_RESULTS_KEY, view_model)
            return view_model

        approved_records = [record for record in batch["records"] if record["status"] == "approved"]
        if not approved_records:
            view_model = {
                "session_id": session_id,
                "confirmation_batch_id": confirmation_batch_id,
                "status": "empty",
                "submittable_jobs": [],
                "skipped_jobs": [],
                "stale_reasons": [],
                "total_count": 0,
                "submittable_count": 0,
                "skipped_count": 0,
            }
            self.session_store.set_state(session_id, JOB_REVALIDATION_RESULTS_KEY, view_model)
            return view_model

        job_details: dict[str, dict[str, str | None]] = {}
        for record in approved_records:
            job_data = get_job_application_by_id(database_path, job_id=record["job_id"])
            if job_data is not None:
                job_details[record["job_id"]] = job_data

        submittable_jobs: list[dict[str, object]] = []
        skipped_jobs: list[dict[str, object]] = []
        stale_reasons: list[dict[str, str]] = []

        for record in approved_records:
            job_id = record["job_id"]
            platform = record["platform"]
            job_data = job_details.get(job_id)
            if job_data is None:
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "job_not_found")
                stale_reasons.append({"job_id": record.get("platform_job_id", job_id), "reason": "job_not_found"})
                skipped_jobs.append({"job_id": record.get("platform_job_id", job_id), "platform": platform, "reason": "job_not_found"})
                continue

            platform_job_id = str(job_data["platform_job_id"])
            adapter = adapters.get(platform)
            if adapter is None:
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "adapter_not_found")
                stale_reasons.append({"job_id": platform_job_id, "reason": "adapter_not_found"})
                skipped_jobs.append({"job_id": platform_job_id, "platform": platform, "reason": "adapter_not_found"})
                continue

            try:
                fresh_job = adapter.read_job_detail(platform_job_id)
            except Exception:
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "job_offline")
                stale_reasons.append({"job_id": platform_job_id, "reason": "job_offline"})
                skipped_jobs.append({"job_id": platform_job_id, "platform": platform, "reason": "job_offline"})
                continue

            if fresh_job is None:
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "job_offline")
                stale_reasons.append({"job_id": platform_job_id, "reason": "job_offline"})
                skipped_jobs.append({"job_id": platform_job_id, "platform": platform, "reason": "job_offline"})
                continue

            if adapter.is_already_applied(platform_job_id):
                update_job_application_status(
                    database_path,
                    job_id=job_id,
                    status="duplicate",
                    confirmation_batch_id=confirmation_batch_id,
                    confirmation_status="confirmed",
                    duplicate_detected=True,
                )
                stale_reasons.append({"job_id": platform_job_id, "reason": "already_applied"})
                skipped_jobs.append({"job_id": platform_job_id, "platform": platform, "reason": "already_applied"})
                continue

            if not adapter.is_button_available(platform_job_id):
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "button_unavailable")
                stale_reasons.append({"job_id": platform_job_id, "reason": "button_unavailable"})
                skipped_jobs.append({"job_id": platform_job_id, "platform": platform, "reason": "button_unavailable"})
                continue

            if _jd_critical_fields_changed(job_data, fresh_job):
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "jd_changed")
                stale_reasons.append({"job_id": platform_job_id, "reason": "jd_changed"})
                skipped_jobs.append({"job_id": platform_job_id, "platform": platform, "reason": "jd_changed"})
                continue

            submittable_jobs.append({
                "platform": platform,
                "platform_job_id": platform_job_id,
                "title": job_data.get("title"),
                "company_name": job_data.get("company_name"),
            })

        view_model = {
            "session_id": session_id,
            "confirmation_batch_id": confirmation_batch_id,
            "status": "ready",
            "submittable_jobs": submittable_jobs,
            "skipped_jobs": skipped_jobs,
            "stale_reasons": stale_reasons,
            "total_count": len(approved_records),
            "submittable_count": len(submittable_jobs),
            "skipped_count": len(skipped_jobs),
        }
        self.session_store.set_state(session_id, JOB_REVALIDATION_RESULTS_KEY, view_model)
        return view_model

    def get_revalidation_results(self, *, session_id: str) -> dict[str, object] | None:
        view_model = self.session_store.get_state(session_id, JOB_REVALIDATION_RESULTS_KEY)
        return view_model if isinstance(view_model, dict) else None

    def submit_boss_applications(
        self,
        *,
        session_id: str,
        confirmation_batch_id: str,
        adapter: JobPlatformAdapter,
    ) -> dict[str, object]:
        database_path = Path(self.config.storage.database_path)
        batch = get_confirmation_batch(database_path, confirmation_batch_id=confirmation_batch_id)
        if batch is None:
            view_model: dict[str, object] = {
                "session_id": session_id,
                "confirmation_batch_id": confirmation_batch_id,
                "status": "not_found",
                "submitted_jobs": [],
                "failed_jobs": [],
                "skipped_jobs": [],
                "manual_takeover_jobs": [],
                "total_count": 0,
                "submitted_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "manual_takeover_count": 0,
            }
            self.session_store.set_state(session_id, JOB_BOSS_SUBMIT_RESULTS_KEY, view_model)
            return view_model

        # Only confirmed or confirmed-with-approved-records batches can submit
        batch_status = str(batch.get("status", ""))
        approved_records = [r for r in batch.get("records", []) if r.get("status") == "approved"]
        if batch_status not in ("confirmed",) and not approved_records:
            view_model = {
                "session_id": session_id,
                "confirmation_batch_id": confirmation_batch_id,
                "status": "not_confirmed",
                "submitted_jobs": [],
                "failed_jobs": [],
                "skipped_jobs": [],
                "manual_takeover_jobs": [],
                "total_count": 0,
                "submitted_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "manual_takeover_count": 0,
            }
            self.session_store.set_state(session_id, JOB_BOSS_SUBMIT_RESULTS_KEY, view_model)
            return view_model

        submitted_jobs: list[dict[str, object]] = []
        failed_jobs: list[dict[str, object]] = []
        skipped_jobs: list[dict[str, object]] = []
        manual_takeover_jobs: list[dict[str, object]] = []

        from interview_agent.job_platform_adapters import PlatformAdapterErrorType
        _MANUAL_TAKEOVER_ERROR_TYPES = {
            PlatformAdapterErrorType.CAPTCHA_REQUIRED,
            PlatformAdapterErrorType.ACCOUNT_RISK_CONTROL,
            PlatformAdapterErrorType.FORCED_POPUP,
        }

        for record in approved_records:
            job_id = str(record["job_id"])
            job_data = get_job_application_by_id(database_path, job_id=job_id)
            if job_data is None:
                _mark_job_skipped(database_path, job_id, confirmation_batch_id, "job_not_found")
                skipped_jobs.append({"job_id": job_id, "reason": "job_not_found"})
                continue

            platform_job_id = str(job_data["platform_job_id"])
            job_detail = StandardJob(
                platform=str(job_data["platform"]),
                platform_job_id=str(job_data["platform_job_id"]),
                title=str(job_data["title"]),
                company_name=str(job_data["company_name"]),
                location=str(job_data["location"]),
                remote_policy=job_data.get("remote_policy"),
                salary_range=job_data.get("salary_range"),
                level=job_data.get("level"),
                experience_requirement=job_data.get("experience_requirement"),
                education_requirement=job_data.get("education_requirement"),
                industry=job_data.get("industry"),
                company_size=job_data.get("company_size"),
                funding_stage=job_data.get("funding_stage"),
                tech_stack=[],
                benefits=[],
                published_at=job_data.get("published_at"),
                detail_url=str(job_data["detail_url"]),
                jd_text=str(job_data["jd_text"]),
                collected_at=str(job_data["collected_at"]),
                field_confidence={},
            )

            request = ConfirmationApplicationRequest(
                confirmation_batch_id=confirmation_batch_id,
                job=job_detail,
                application_message="",
                confirmed=True,
            )

            try:
                submit_result = adapter.submit_application(request)
            except Exception as exc:
                update_job_application_status(
                    database_path,
                    job_id=job_id,
                    status="failed",
                    confirmation_batch_id=confirmation_batch_id,
                    confirmation_status="confirmed",
                    failure_reason="adapter_error",
                )
                failed_jobs.append({"job_id": job_id, "platform_job_id": platform_job_id, "reason": "adapter_error", "error_message": str(exc)})
                continue

            if submit_result.status == "submitted":
                update_job_application_status(
                    database_path,
                    job_id=job_id,
                    status="submitted",
                    confirmation_batch_id=confirmation_batch_id,
                    confirmation_status="confirmed",
                    submitted_at=submit_result.submitted_at,
                )
                submitted_jobs.append({"job_id": job_id, "platform_job_id": platform_job_id, "submitted_at": submit_result.submitted_at})
            elif submit_result.status == "duplicate":
                update_job_application_status(
                    database_path,
                    job_id=job_id,
                    status="duplicate",
                    confirmation_batch_id=confirmation_batch_id,
                    confirmation_status="confirmed",
                    duplicate_detected=True,
                )
                skipped_jobs.append({"job_id": job_id, "platform_job_id": platform_job_id, "reason": "duplicate"})
            elif submit_result.error and submit_result.error.error_type in _MANUAL_TAKEOVER_ERROR_TYPES:
                update_job_application_status(
                    database_path,
                    job_id=job_id,
                    status="failed",
                    confirmation_batch_id=confirmation_batch_id,
                    confirmation_status="confirmed",
                    failure_reason=str(submit_result.error.error_type.value),
                    platform_message=submit_result.platform_message,
                )
                manual_takeover_jobs.append({
                    "job_id": job_id,
                    "platform_job_id": platform_job_id,
                    "reason": str(submit_result.error.error_type.value),
                    "platform_message": submit_result.platform_message,
                })
            else:
                failure_reason = submit_result.error.error_type.value if submit_result.error else "unknown"
                update_job_application_status(
                    database_path,
                    job_id=job_id,
                    status="failed",
                    confirmation_batch_id=confirmation_batch_id,
                    confirmation_status="confirmed",
                    failure_reason=failure_reason,
                    platform_message=submit_result.platform_message,
                )
                failed_jobs.append({
                    "job_id": job_id,
                    "platform_job_id": platform_job_id,
                    "reason": failure_reason,
                    "platform_message": submit_result.platform_message,
                })

        view_model = {
            "session_id": session_id,
            "confirmation_batch_id": confirmation_batch_id,
            "status": "completed",
            "submitted_jobs": submitted_jobs,
            "failed_jobs": failed_jobs,
            "skipped_jobs": skipped_jobs,
            "manual_takeover_jobs": manual_takeover_jobs,
            "total_count": len(approved_records),
            "submitted_count": len(submitted_jobs),
            "failed_count": len(failed_jobs),
            "skipped_count": len(skipped_jobs),
            "manual_takeover_count": len(manual_takeover_jobs),
        }
        self.session_store.set_state(session_id, JOB_BOSS_SUBMIT_RESULTS_KEY, view_model)
        return view_model

    def get_boss_submit_results(self, *, session_id: str) -> dict[str, object] | None:
        view_model = self.session_store.get_state(session_id, JOB_BOSS_SUBMIT_RESULTS_KEY)
        return view_model if isinstance(view_model, dict) else None

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


def filter_and_rank_jobs(
    runtime: GuiRuntime,
    *,
    session_id: str,
    jobs: list[StandardJob],
    hard_filters: dict[str, object],
    ranking_preferences: dict[str, object],
    already_applied_job_ids: list[str] | None = None,
) -> dict[str, object]:
    return runtime.filter_and_rank_jobs(
        session_id=session_id,
        jobs=jobs,
        hard_filters=hard_filters,
        ranking_preferences=ranking_preferences,
        already_applied_job_ids=already_applied_job_ids,
    )


def get_job_filter_results(runtime: GuiRuntime, *, session_id: str) -> dict[str, object] | None:
    return runtime.get_job_filter_results(session_id=session_id)


def evaluate_jobs(
    runtime: GuiRuntime,
    *,
    session_id: str,
    resume_profile: dict[str, object],
    jobs: list[StandardJob],
) -> dict[str, object]:
    return runtime.evaluate_jobs(
        session_id=session_id,
        resume_profile=resume_profile,
        jobs=jobs,
    )


def get_job_evaluation_results(runtime: GuiRuntime, *, session_id: str) -> dict[str, object] | None:
    return runtime.get_job_evaluation_results(session_id=session_id)


def revalidate_confirmation_batch(
    runtime: GuiRuntime,
    *,
    session_id: str,
    confirmation_batch_id: str,
    adapters: Mapping[str, JobPlatformAdapter],
) -> dict[str, object]:
    return runtime.revalidate_confirmation_batch(
        session_id=session_id,
        confirmation_batch_id=confirmation_batch_id,
        adapters=adapters,
    )


def get_revalidation_results(runtime: GuiRuntime, *, session_id: str) -> dict[str, object] | None:
    return runtime.get_revalidation_results(session_id=session_id)


def submit_boss_applications(
    runtime: GuiRuntime,
    *,
    session_id: str,
    confirmation_batch_id: str,
    adapter: JobPlatformAdapter,
) -> dict[str, object]:
    return runtime.submit_boss_applications(
        session_id=session_id,
        confirmation_batch_id=confirmation_batch_id,
        adapter=adapter,
    )


def get_boss_submit_results(runtime: GuiRuntime, *, session_id: str) -> dict[str, object] | None:
    return runtime.get_boss_submit_results(session_id=session_id)


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
            "manual_takeover_platform_count": 0,
            "backoff_platform_count": 0,
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


# ---------------------------------------------------------------------------
# JOB-011 岗位筛选与排序辅助函数
# ---------------------------------------------------------------------------

_EDUCATION_LEVELS = {"不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}


def _hard_filter_exclusion_reason(
    job: StandardJob,
    hard_filters: dict[str, object],
    applied_ids: set[str],
) -> str | None:
    """返回排除原因字符串；返回 None 表示通过硬过滤。"""
    # 已投递过滤
    if job.platform_job_id in applied_ids:
        return "already_applied"

    # 城市过滤
    cities = _list_value(hard_filters.get("cities"))
    if cities and not any(city in (job.location or "") for city in cities):
        return "city_mismatch"

    # 远程偏好过滤
    remote_policy = hard_filters.get("remote_policy")
    if isinstance(remote_policy, str) and remote_policy.strip():
        job_remote = (job.remote_policy or "").lower()
        required_remote = remote_policy.strip().lower()
        if required_remote == "remote" and job_remote not in ("remote", "fully_remote", "全远程"):
            return "remote_policy_mismatch"
        elif required_remote == "onsite" and job_remote in ("remote", "fully_remote", "全远程"):
            return "remote_policy_mismatch"
        elif required_remote not in ("any", "") and required_remote != job_remote:
            return "remote_policy_mismatch"

    # 薪资下限过滤
    salary_min = hard_filters.get("salary_min")
    if isinstance(salary_min, int | float) and salary_min > 0:
        job_salary_low = _parse_salary_low(job.salary_range)
        if job_salary_low is not None and job_salary_low < salary_min:
            return "salary_below_minimum"

    # 学历过滤
    education = hard_filters.get("education")
    if isinstance(education, str) and education.strip():
        required_level = _EDUCATION_LEVELS.get(education.strip(), -1)
        job_level = _EDUCATION_LEVELS.get((job.education_requirement or "").strip(), -1)
        if required_level >= 0 and job_level >= 0 and job_level < required_level:
            return "education_below_required"

    # 经验上下限过滤
    exp_min = hard_filters.get("experience_years_min")
    exp_max = hard_filters.get("experience_years_max")
    job_exp = _parse_experience_years(job.experience_requirement)
    if isinstance(exp_min, int | float) and exp_min > 0 and job_exp is not None and job_exp < exp_min:
        return "experience_below_minimum"
    if isinstance(exp_max, int | float) and exp_max > 0 and job_exp is not None and job_exp > exp_max:
        return "experience_above_maximum"

    # 黑名单公司过滤
    blacklist = _list_value(hard_filters.get("company_blacklist"))
    if blacklist and any(blacklisted.lower() in (job.company_name or "").lower() for blacklisted in blacklist):
        return "company_blacklisted"

    return None


def _low_confidence_fields(job: StandardJob) -> list[str]:
    """返回字段值为 None 或空字符串的字段名列表。"""
    check_fields = (
        "remote_policy", "salary_range", "level", "experience_requirement",
        "education_requirement", "industry", "company_size", "funding_stage",
        "published_at",
    )
    low_confidence: list[str] = []
    for field_name in check_fields:
        value = getattr(job, field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            low_confidence.append(field_name)
    if not job.tech_stack:
        low_confidence.append("tech_stack")
    # 合并 field_confidence 中已有的低置信度标记
    for field_name, confidence in (job.field_confidence or {}).items():
        if confidence in ("low", "missing", "uncertain") and field_name not in low_confidence:
            low_confidence.append(field_name)
    return low_confidence


def _ranking_score(job: StandardJob, ranking_preferences: dict[str, object]) -> float:
    """根据排序偏好计算岗位得分，用于排序。"""
    score = 0.0

    # 技术栈匹配
    preferred_skills = _list_value(ranking_preferences.get("technical_skills"))
    if preferred_skills and job.tech_stack:
        job_skills_lower = {skill.lower() for skill in job.tech_stack}
        matched_skills = sum(1 for skill in preferred_skills if skill.lower() in job_skills_lower)
        score += matched_skills * 2.0

    # 行业匹配
    preferred_industries = _list_value(ranking_preferences.get("industries"))
    if preferred_industries and job.industry:
        if any(industry.lower() in (job.industry or "").lower() for industry in preferred_industries):
            score += 3.0

    # 公司规模匹配
    preferred_sizes = _list_value(ranking_preferences.get("company_sizes"))
    if preferred_sizes and job.company_size:
        if any(size.lower() in (job.company_size or "").lower() for size in preferred_sizes):
            score += 1.0

    # 融资阶段匹配
    preferred_stages = _list_value(ranking_preferences.get("funding_stages"))
    if preferred_stages and job.funding_stage:
        if any(stage.lower() in (job.funding_stage or "").lower() for stage in preferred_stages):
            score += 1.0

    # 福利匹配
    preferred_benefits = _list_value(ranking_preferences.get("benefits"))
    if preferred_benefits and job.benefits:
        job_benefits_lower = {benefit.lower() for benefit in job.benefits}
        matched_benefits = sum(1 for benefit in preferred_benefits if benefit.lower() in job_benefits_lower)
        score += matched_benefits * 0.5

    # 发布时间新鲜度
    published_within_days = ranking_preferences.get("published_within_days")
    if isinstance(published_within_days, int | float) and published_within_days > 0 and job.published_at:
        try:
            from datetime import UTC, datetime
            published_dt = datetime.fromisoformat(job.published_at)
            days_ago = (datetime.now(UTC) - published_dt).total_seconds() / 86400
            if days_ago <= published_within_days:
                score += 2.0
            elif days_ago <= published_within_days * 2:
                score += 1.0
        except (ValueError, TypeError):
            pass

    return score


def _parse_salary_low(salary_range: str | None) -> float | None:
    """从薪资范围字符串中提取下限数值（单位：k）。"""
    if not salary_range or not isinstance(salary_range, str):
        return None
    import re
    match = re.search(r"(\d+(?:\.\d+)?)", salary_range)
    if match:
        return float(match.group(1))
    return None


def _parse_experience_years(experience_requirement: str | None) -> float | None:
    """从经验要求字符串中提取年限数值。"""
    if not experience_requirement or not isinstance(experience_requirement, str):
        return None
    import re
    match = re.search(r"(\d+(?:\.\d+)?)", experience_requirement)
    if match:
        return float(match.group(1))
    return None


# ---------------------------------------------------------------------------
# JOB-012 岗位评估与建议辅助函数
# ---------------------------------------------------------------------------


def _job_structured_from_standard_job(job: StandardJob) -> dict[str, object]:
    """从 StandardJob 构建岗位结构化信息，供 LLM 评估使用。"""
    return {
        "platform": job.platform,
        "platform_job_id": job.platform_job_id,
        "title": job.title,
        "company_name": job.company_name,
        "location": job.location,
        "remote_policy": job.remote_policy,
        "salary_range": job.salary_range,
        "level": job.level,
        "experience_requirement": job.experience_requirement,
        "education_requirement": job.education_requirement,
        "industry": job.industry,
        "company_size": job.company_size,
        "funding_stage": job.funding_stage,
        "tech_stack": list(job.tech_stack),
        "benefits": list(job.benefits),
        "published_at": job.published_at,
    }


# ---------------------------------------------------------------------------
# JOB-014 确认批次重校验辅助函数
# ---------------------------------------------------------------------------


def _mark_job_skipped(
    database_path: Path,
    job_id: str,
    confirmation_batch_id: str,
    reason: str,
) -> None:
    """将岗位标记为 skipped 并记录原因。"""
    update_job_application_status(
        database_path,
        job_id=job_id,
        status="skipped",
        confirmation_batch_id=confirmation_batch_id,
        confirmation_status="confirmed",
        failure_reason=reason,
    )


def _jd_critical_fields_changed(
    stored_job: dict[str, str | None],
    fresh_job: StandardJob,
) -> bool:
    """检查存储的岗位与平台最新详情之间的关键 JD 字段是否发生变化。"""
    _stored_salary = (stored_job.get("salary_range") or "").strip()
    _fresh_salary = (fresh_job.salary_range or "").strip()
    if _stored_salary and _fresh_salary and _stored_salary != _fresh_salary:
        return True

    _stored_location = (stored_job.get("location") or "").strip()
    _fresh_location = (fresh_job.location or "").strip()
    if _stored_location and _fresh_location and _stored_location != _fresh_location:
        return True

    _stored_education = (stored_job.get("education_requirement") or "").strip()
    _fresh_education = (fresh_job.education_requirement or "").strip()
    if _stored_education and _fresh_education and _stored_education != _fresh_education:
        return True

    _stored_experience = (stored_job.get("experience_requirement") or "").strip()
    _fresh_experience = (fresh_job.experience_requirement or "").strip()
    if _stored_experience and _fresh_experience and _stored_experience != _fresh_experience:
        return True

    _stored_level = (stored_job.get("level") or "").strip()
    _fresh_level = (fresh_job.level or "").strip()
    if _stored_level and _fresh_level and _stored_level != _fresh_level:
        return True

    _stored_jd = " ".join((stored_job.get("jd_text") or "").split())
    _fresh_jd = " ".join((fresh_job.jd_text or "").split())
    if _stored_jd and _fresh_jd and _stored_jd != _fresh_jd:
        return True

    return False
