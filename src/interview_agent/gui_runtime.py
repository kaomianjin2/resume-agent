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
