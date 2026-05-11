from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import sys
from typing import Protocol, TextIO

from interview_agent.config import DEFAULT_CONFIG_PATH, ConfigError, LLMConfig, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.llm import FakeLLMClient, OpenAICompatibleClient
from interview_agent.nodes.registry import NodeRegistry, UnknownNodeError, build_default_registry
from interview_agent.planner import (
    ExecutionPlan,
    PlanConfirmation,
    build_execution_plan,
    ensure_plan_confirmation,
)
from interview_agent.router import RouteResult, route_conversation
from interview_agent.session import SessionStore
from interview_agent.storage import get_knowledge_base_status


DEFAULT_SESSION_ID = "interactive-cli-session"
LLMClient = FakeLLMClient | OpenAICompatibleClient
ServiceMap = Mapping[str, object]
InputFunc = Callable[[str], str]
RouteFunc = Callable[[str, NodeRegistry, LLMClient | None], RouteResult]
LLMFactory = Callable[[LLMConfig], LLMClient]


class ExecutorProtocol(Protocol):
    def execute_node(
        self,
        session_id: str,
        node_name: str,
        inputs: dict[str, object] | None = None,
    ) -> NodeExecutionResult: ...


ExecutorFactory = Callable[[Path, NodeRegistry, ServiceMap], ExecutorProtocol]


class InputCancelledError(RuntimeError):
    """Raised when the user stops providing required interactive inputs."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="interview-agent",
        description="Interactive CLI for the interview agent project.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"配置文件路径，默认值: {DEFAULT_CONFIG_PATH}",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    input_func: InputFunc = input,
    output: TextIO | None = None,
    registry_builder: Callable[[], NodeRegistry] = build_default_registry,
    route_func: RouteFunc = route_conversation,
    executor_factory: ExecutorFactory | None = None,
    llm_factory: LLMFactory = OpenAICompatibleClient,
    session_id: str = DEFAULT_SESSION_ID,
) -> int:
    output_stream = output or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
    except ConfigError as error:
        _write_line(output_stream, f"配置错误: {error}")
        return 1

    database_path = Path(config.storage.database_path)
    knowledge_base_status = get_knowledge_base_status(database_path)
    if knowledge_base_status != "ready":
        _write_line(output_stream, "知识库未就绪，请先执行离线构建：")
        _write_line(output_stream, _build_offline_command(config_path, database_path, Path(config.knowledge_base.source)))
        return 1

    registry = registry_builder()
    session_store = SessionStore(database_path)
    session_store.create_session(session_id)
    llm_client = llm_factory(config.llm)
    services = {
        "llm": llm_client,
        "retriever": SQLiteHybridRetriever(database_path, config.embedding),
    }
    executor = (executor_factory or _default_executor_factory)(database_path, registry, services)

    _write_line(output_stream, "请输入需求，输入 exit 退出。")
    while True:
        user_message = _read_line(input_func, output_stream, "> ")
        if user_message is None:
            _write_line(output_stream, "输入结束，已退出。")
            return 0

        normalized_message = user_message.strip()
        if not normalized_message:
            continue
        if normalized_message in {"exit", "quit", "/exit"}:
            _write_line(output_stream, "已退出。")
            return 0

        direct_node_name = _parse_direct_node_name(normalized_message)
        if direct_node_name is not None:
            if not direct_node_name:
                _write_line(output_stream, "节点名不能为空，请使用 /node <节点名>。")
                continue
            if direct_node_name not in registry.list_names():
                _write_line(output_stream, f"未知节点: {direct_node_name}")
                continue
            _write_line(output_stream, f"指定节点: {direct_node_name}")
            selected_node = direct_node_name
        else:
            route_result = route_func(normalized_message, registry, llm_client)
            _write_line(output_stream, f"匹配节点: {route_result.selected_node}")
            if route_result.candidate_nodes:
                _write_line(output_stream, "候选节点: " + ", ".join(route_result.candidate_nodes))
            selected_node = route_result.selected_node

        session_inputs = session_store.get_all_state(session_id)
        try:
            plan = build_execution_plan(
                user_message=normalized_message,
                selected_node=selected_node,
                session_inputs=session_inputs,
                registry=registry,
            )
        except UnknownNodeError:
            _write_line(output_stream, f"未知节点: {selected_node}")
            continue
        _print_plan(output_stream, plan)

        if not _confirm_plan_if_needed(plan, input_func, output_stream):
            _write_line(output_stream, "已取消执行计划。")
            continue

        for step in plan.steps:
            try:
                result = _execute_step_with_prompt(
                    executor=executor,
                    session_store=session_store,
                    session_id=session_id,
                    node_name=step.node_name,
                    input_func=input_func,
                    output=output_stream,
                )
            except InputCancelledError:
                _write_line(output_stream, "输入结束，已取消当前执行。")
                break
            _write_result(output_stream, result)
            if result.status != "success":
                break


def _default_executor_factory(
    database_path: Path,
    registry: NodeRegistry,
    services: ServiceMap,
) -> NodeExecutor:
    return NodeExecutor(database_path, registry, services=dict(services))


def _build_offline_command(config_path: Path, database_path: Path, source_path: Path) -> str:
    return (
        "uv run python -m interview_agent.kb.build "
        f"--source {source_path} --config {config_path} --db {database_path}"
    )


def _read_line(input_func: InputFunc, output: TextIO, prompt: str) -> str | None:
    output.write(prompt)
    output.flush()
    try:
        return input_func("")
    except (EOFError, StopIteration):
        return None


def _parse_direct_node_name(user_message: str) -> str | None:
    if not user_message.startswith("/node"):
        return None

    segments = user_message.split(maxsplit=1)
    if len(segments) != 2:
        return ""
    return segments[1].strip()


def _print_plan(output: TextIO, plan: ExecutionPlan) -> None:
    _write_line(output, f"执行计划: {plan.summary}")
    for index, step in enumerate(plan.steps, start=1):
        _write_line(output, f"{index}. {step.node_name} - {step.description}")


def _confirm_plan_if_needed(plan: ExecutionPlan, input_func: InputFunc, output: TextIO) -> bool:
    if not plan.requires_confirmation:
        return True

    confirmation_text = _read_line(input_func, output, "确认执行计划？[y/N]: ")
    confirmed = (confirmation_text or "").strip().lower() in {"y", "yes"}
    blocked_message = ensure_plan_confirmation(
        plan,
        PlanConfirmation(plan_id=plan.plan_id, confirmed=confirmed),
    )
    return blocked_message is None


def _execute_step_with_prompt(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    node_name: str,
    input_func: InputFunc,
    output: TextIO,
) -> NodeExecutionResult:
    result = executor.execute_node(session_id=session_id, node_name=node_name, inputs=None)
    while result.status == "missing_inputs":
        provided_inputs = _collect_missing_inputs(
            session_store=session_store,
            session_id=session_id,
            input_names=result.missing_inputs,
            input_func=input_func,
            output=output,
        )
        result = executor.execute_node(session_id=session_id, node_name=node_name, inputs=provided_inputs)
    return result


def _collect_missing_inputs(
    session_store: SessionStore,
    session_id: str,
    input_names: list[str],
    input_func: InputFunc,
    output: TextIO,
) -> dict[str, object]:
    collected_inputs: dict[str, object] = {}
    for input_name in input_names:
        raw_value = _read_line(input_func, output, f"请输入 {input_name}（可直接粘贴文本，或输入文件路径）: ")
        if raw_value is None:
            raise InputCancelledError("缺少节点输入")
        input_value = _resolve_input_value(raw_value)
        session_store.set_state(session_id, input_name, input_value)
        collected_inputs[input_name] = input_value
    return collected_inputs


def _resolve_input_value(raw_value: str) -> str:
    candidate_path = Path(raw_value.strip())
    if candidate_path.is_file():
        return candidate_path.read_text(encoding="utf-8")
    return raw_value


def _write_result(output: TextIO, result: NodeExecutionResult) -> None:
    _write_line(output, f"执行结果: {result.status}")
    if result.error_message:
        _write_line(output, f"错误信息: {result.error_message}")


def _write_line(output: TextIO, message: str) -> None:
    output.write(message + "\n")
    output.flush()


if __name__ == "__main__":
    raise SystemExit(main())
