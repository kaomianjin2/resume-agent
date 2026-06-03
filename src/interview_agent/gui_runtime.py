from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from interview_agent.config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
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

        resume_result = self.executor.execute_node(
            session_id=session_id,
            node_name="resume_parse",
            inputs={"resume_text": resume_text},
        )
        if resume_result.status != "success":
            return _prep_error_view_model(session_id, resume_result)

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

    def start_mock_interview(
        self,
        *,
        session_id: str,
        target_role: str,
        question_count: int = DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT,
        followup_rounds: int = DEFAULT_MOCK_FOLLOWUP_ROUNDS,
        question_type: str = "行为面试",
    ) -> dict[str, object]:
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
    missing_inputs = []
    if not resume_text.strip():
        missing_inputs.append("resume_text")
    if not jd_text.strip():
        missing_inputs.append("jd_text")
    return missing_inputs


def _read_mock_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
        "match_summary": _match_summary(session_state.get("match_report")),
        "missing_inputs": [],
    }


def _resume_summary(resume_profile: object) -> dict[str, object]:
    if not isinstance(resume_profile, dict):
        return {}
    return {
        "name": _text_value(resume_profile.get("name"), "未命名候选人"),
        "headline": _text_value(resume_profile.get("headline"), "暂无简历摘要"),
        "highlights": _list_value(resume_profile.get("highlights") or resume_profile.get("skills")),
    }


def _jd_summary(jd_requirements: object) -> dict[str, object]:
    if not isinstance(jd_requirements, dict):
        return {}
    return {
        "role": _text_value(jd_requirements.get("role"), "未命名岗位"),
        "focus": _list_value(jd_requirements.get("focus") or jd_requirements.get("must_have") or jd_requirements.get("skills")),
    }


def _match_summary(match_report: object) -> dict[str, object]:
    if not isinstance(match_report, dict):
        return {}
    return {
        "score": match_report.get("score", "未评分"),
        "strengths": _list_value(match_report.get("strengths") or match_report.get("matched_skills")),
        "risks": _list_value(match_report.get("risks") or match_report.get("gaps")),
        "follow_up_focus": _list_value(match_report.get("follow_up_focus") or match_report.get("followups")),
    }


def _text_value(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def _list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
