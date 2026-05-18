from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from interview_agent.config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.llm import OpenAICompatibleClient
from interview_agent.nodes.registry import NodeRegistry, build_default_registry
from interview_agent.planner import ExecutionPlan, build_execution_plan
from interview_agent.router import RouteResult, route_conversation
from interview_agent.session import SessionStore
from interview_agent.storage import get_knowledge_base_status


ServiceMap = Mapping[str, object]
RegistryBuilder = Callable[[], NodeRegistry]
ServicesBuilder = Callable[[AppConfig], ServiceMap]
ExecutorBuilder = Callable[[Path, NodeRegistry, ServiceMap], NodeExecutor]


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
