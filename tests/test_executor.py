from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from interview_agent.executor import NodeExecutor
from interview_agent.nodes.registry import NodeRegistry
from interview_agent.nodes.spec import NodeContext, NodeSpec
from interview_agent.session import SessionStore, write_session_state
from interview_agent.state_contracts import CANDIDATE_PROFILE
from interview_agent.storage import initialize_database


def profile_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    assert context.session_id is not None
    return {
        "candidate_profile": {
            "name": inputs["resume_text"],
            "source": context.services["source"],
        }
    }


def question_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    assert isinstance(profile, dict)
    return {"questions": [f"{profile['name']}:{inputs['target_role']}"]}


def failing_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    raise RuntimeError("handler failed")


def build_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="profile_parse",
                description="Parse candidate profile.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("candidate_profile",),
                handler=profile_handler,
            ),
            NodeSpec(
                name="question_generate",
                description="Generate interview questions.",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=(),
                outputs=("questions",),
                handler=question_handler,
            ),
            NodeSpec(
                name="failing_node",
                description="Failing node.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("failed_output",),
                handler=failing_handler,
            ),
        ]
    )


def test_single_node_executes_and_writes_outputs_to_session_state(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    executor = NodeExecutor(database_path, build_registry(), services={"source": "fake"})

    result = executor.execute_node(
        session_id="session-1",
        node_name="profile_parse",
        inputs={"resume_text": "Alice"},
    )

    assert result.status == "success"
    assert result.missing_inputs == []
    assert result.output == {"candidate_profile": {"name": "Alice", "source": "fake"}}
    assert session_store.get_state("session-1", "candidate_profile") == {
        "name": "Alice",
        "source": "fake",
    }


def test_executor_creates_session_before_recording_node_run(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    executor = NodeExecutor(database_path, build_registry(), services={"source": "fake"})

    result = executor.execute_node(
        session_id="new-session",
        node_name="profile_parse",
        inputs={"resume_text": "Alice"},
    )

    with sqlite3.connect(database_path) as connection:
        session_row = connection.execute(
            "SELECT session_id, status FROM sessions WHERE session_id = ?",
            ("new-session",),
        ).fetchone()
        run_row = connection.execute(
            "SELECT run_id, status FROM node_runs WHERE session_id = ?",
            ("new-session",),
        ).fetchone()

    assert result.status == "success"
    assert session_row == ("new-session", "active")
    assert run_row == (result.run_id, "success")


def test_nodes_share_state_only_through_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    session_store.create_session("session-1")
    first_executor = NodeExecutor(database_path, build_registry(), services={"source": "fake"})
    second_executor = NodeExecutor(database_path, build_registry())

    first_executor.execute_node(
        session_id="session-1",
        node_name="profile_parse",
        inputs={"resume_text": "Alice"},
    )
    result = second_executor.execute_node(
        session_id="session-1",
        node_name="question_generate",
        inputs={"target_role": "Backend"},
    )

    assert result.status == "success"
    assert result.output == {"questions": ["Alice:Backend"]}
    assert session_store.get_state("session-1", "questions") == ["Alice:Backend"]


def test_node_runs_records_success_and_failure_statuses(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    SessionStore(database_path).create_session("session-1")
    executor = NodeExecutor(database_path, build_registry(), services={"source": "fake"})

    success_result = executor.execute_node(
        session_id="session-1",
        node_name="profile_parse",
        inputs={"resume_text": "Alice"},
    )
    failure_result = executor.execute_node(
        session_id="session-1",
        node_name="failing_node",
        inputs={"resume_text": "Alice"},
    )

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT run_id, node_name, status, output_payload, error_message
            FROM node_runs
            ORDER BY started_at, run_id
            """
        ).fetchall()

    assert rows[0][0] == success_result.run_id
    assert rows[0][1:] == (
        "profile_parse",
        "success",
        '{"candidate_profile":{"name":"Alice","source":"fake"}}',
        None,
    )
    assert rows[1][0] == failure_result.run_id
    assert rows[1][1] == "failing_node"
    assert rows[1][2] == "failed"
    assert rows[1][3] is None
    assert rows[1][4] == "handler failed"


def test_missing_required_inputs_returns_fields_without_running_handler(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    session_store.create_session("session-1")
    executor = NodeExecutor(database_path, build_registry())

    result = executor.execute_node(
        session_id="session-1",
        node_name="question_generate",
        inputs={"target_role": "Backend"},
    )

    assert result.status == "missing_inputs"
    assert result.missing_inputs == ["candidate_profile"]
    assert result.output == {}
    assert session_store.get_state("session-1", "questions") is None


def test_failed_node_records_error_without_writing_outputs(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    session_store.create_session("session-1")
    executor = NodeExecutor(database_path, build_registry())

    result = executor.execute_node(
        session_id="session-1",
        node_name="failing_node",
        inputs={"resume_text": "Alice"},
    )

    assert result.status == "failed"
    assert result.error_message == "handler failed"
    assert session_store.get_state("session-1", "failed_output") is None


def test_node_output_must_include_declared_fields(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)

    def incomplete_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
        del context, inputs
        return {"other": "value"}

    registry = NodeRegistry(
        [
            NodeSpec(
                name="incomplete_node",
                description="Return incomplete output.",
                required_inputs=(),
                optional_inputs=(),
                outputs=("required_output",),
                handler=incomplete_handler,
            )
        ]
    )
    executor = NodeExecutor(database_path, registry)

    result = executor.execute_node(session_id="session-1", node_name="incomplete_node")

    assert result.status == "failed"
    assert result.error_message == "节点输出缺少字段: required_output"
    assert SessionStore(database_path).get_state("session-1", "other") is None


def test_failed_node_preserves_existing_successful_state(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    session_store.create_session("session-1")
    session_store.set_state("session-1", CANDIDATE_PROFILE, {"name": "Alice"})
    executor = NodeExecutor(database_path, build_registry())

    result = executor.execute_node(
        session_id="session-1",
        node_name="failing_node",
        inputs={"resume_text": "Alice"},
    )

    assert result.status == "failed"
    assert session_store.get_state("session-1", CANDIDATE_PROFILE) == {"name": "Alice"}
    assert session_store.get_state("session-1", "failed_output") is None


def test_session_store_set_state_creates_session_for_fresh_session_id(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    session_store.set_state("fresh-session", "key", {"v": 1})

    with sqlite3.connect(database_path) as connection:
        session_row = connection.execute(
            "SELECT session_id, status FROM sessions WHERE session_id = ?",
            ("fresh-session",),
        ).fetchone()
        state_row = connection.execute(
            "SELECT state_value FROM session_state WHERE session_id = ? AND state_key = ?",
            ("fresh-session", "key"),
        ).fetchone()

    assert session_row == ("fresh-session", "active")
    assert state_row == ('{"v":1}',)


@pytest.mark.parametrize("invalid_key", ["", "   "])
def test_session_store_set_state_rejects_empty_state_key(tmp_path: Path, invalid_key: str) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    with pytest.raises(ValueError, match="state key 必须是非空字符串"):
        session_store.set_state("session-1", invalid_key, {"v": 1})


def test_session_store_set_state_rejects_none_value(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    with pytest.raises(ValueError, match="state value 不能为 None"):
        session_store.set_state("session-1", "empty", None)


def test_session_store_set_state_rejects_non_json_serializable_value(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    with pytest.raises(ValueError, match="state value 必须可 JSON 编码"):
        session_store.set_state("session-1", "bad", {"payload": object()})


def test_session_store_set_state_accepts_json_serializable_value(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    value = {"items": ["a"], "meta": {"count": 1}}

    session_store.set_state("session-1", "good", value)

    assert session_store.get_state("session-1", "good") == value


def test_write_session_state_rejects_none_value_when_called_directly(tmp_path: Path) -> None:
    database_path = tmp_path / "executor.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    session_store.create_session("session-1")
    value = {"items": ["a"], "meta": {"count": 1}}

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(ValueError, match="state value 不能为 None"):
            write_session_state(connection, "session-1", {"bad": None})

    assert session_store.get_state("session-1", "bad") is None

    session_store.set_state("session-1", "good", value)

    with sqlite3.connect(database_path) as connection:
        state_row = connection.execute(
            "SELECT state_value FROM session_state WHERE session_id = ? AND state_key = ?",
            ("session-1", "good"),
        ).fetchone()

    assert state_row == (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),)
