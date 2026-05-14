from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from uuid import uuid4

from interview_agent.nodes.registry import NodeRegistry
from interview_agent.nodes.spec import NodeContext, validate_required_inputs
from interview_agent.session import SessionStore, encode_json_payload, ensure_session, write_session_state
from interview_agent.state_contracts import validate_state_entry
from interview_agent.storage import get_connection, transaction


@dataclass(frozen=True)
class NodeExecutionResult:
    run_id: str
    session_id: str
    node_name: str
    status: str
    output: dict[str, object]
    missing_inputs: list[str]
    error_message: str | None = None


class NodeExecutor:
    def __init__(
        self, database_path: Path | str, registry: NodeRegistry, services: dict[str, object] | None = None
    ) -> None:
        self.database_path = Path(database_path)
        self.registry = registry
        self.services = services or {}
        self.session_store = SessionStore(database_path)

    def execute_node(self, session_id: str, node_name: str, inputs: dict[str, object] | None = None) -> NodeExecutionResult:
        spec = self.registry.get(node_name)
        merged_inputs = {**self.session_store.get_all_state(session_id), **(inputs or {})}
        missing_inputs = validate_required_inputs(spec, merged_inputs)
        run_id = uuid4().hex
        started_at = _current_timestamp()

        if missing_inputs:
            result = NodeExecutionResult(
                run_id, session_id, node_name, "missing_inputs", {}, missing_inputs, "缺少输入: " + ", ".join(missing_inputs)
            )
            self._record_result(result, merged_inputs, started_at)
            return result

        try:
            context = NodeContext(session_id=session_id, services=self.services)
            output = spec.handler(context, dict(merged_inputs))
            _validate_node_output(spec.outputs, output)
            _validate_output_state_entries(output)
            result = NodeExecutionResult(
                run_id, session_id, node_name, "success", output, []
            )
        except Exception as exc:
            result = NodeExecutionResult(run_id, session_id, node_name, "failed", {}, [], str(exc))

        self._record_result(result, merged_inputs, started_at)
        return result

    def _record_result(self, result: NodeExecutionResult, input_payload: dict[str, object], started_at: str) -> None:
        with get_connection(self.database_path) as connection:
            with transaction(connection):
                ensure_session(connection, result.session_id)
                _insert_node_run(connection, result, input_payload, started_at)
                if result.status == "success":
                    write_session_state(connection, result.session_id, result.output)


def _insert_node_run(connection: sqlite3.Connection, result: NodeExecutionResult, input_payload: dict[str, object], started_at: str) -> None:
    output_payload = encode_json_payload(result.output) if result.status == "success" else None
    connection.execute(
        "INSERT INTO node_runs "
        "(run_id, session_id, node_name, status, input_payload, output_payload, "
        "error_message, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            result.run_id, result.session_id, result.node_name, result.status,
            encode_json_payload(input_payload),
            output_payload, result.error_message, started_at, _current_timestamp(),
        ),
    )


def _current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _validate_node_output(expected_outputs: tuple[str, ...], output: dict[str, object]) -> None:
    missing_outputs = [output_name for output_name in expected_outputs if output_name not in output]
    if missing_outputs:
        raise RuntimeError("节点输出缺少字段: " + ", ".join(missing_outputs))


def _validate_output_state_entries(output: dict[str, object]) -> None:
    for output_name, output_value in output.items():
        validate_state_entry(output_name, output_value)
