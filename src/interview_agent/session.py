from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from interview_agent.state_contracts import validate_state_entry
from interview_agent.storage import get_connection, transaction


class SessionStore:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def create_session(self, session_id: str) -> None:
        current_timestamp = _current_timestamp()
        with get_connection(self.database_path) as connection:
            connection.execute(
                "INSERT INTO sessions (session_id, created_at, updated_at, status) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "updated_at = excluded.updated_at, status = excluded.status",
                (session_id, current_timestamp, current_timestamp, "active"),
            )

    def get_state(self, session_id: str, key: str) -> object | None:
        with get_connection(self.database_path) as connection:
            row = connection.execute(
                "SELECT state_value, value_type FROM session_state "
                "WHERE session_id = ? AND state_key = ?",
                (session_id, key),
            ).fetchone()

        if row is None:
            return None

        return _decode_value(state_value=row[0], value_type=row[1])

    def get_all_state(self, session_id: str) -> dict[str, object]:
        with get_connection(self.database_path) as connection:
            rows = connection.execute(
                "SELECT state_key, state_value, value_type FROM session_state "
                "WHERE session_id = ? ORDER BY state_key",
                (session_id,),
            ).fetchall()

        return {row[0]: _decode_value(state_value=row[1], value_type=row[2]) for row in rows}

    def set_state(self, session_id: str, key: str, value: object) -> None:
        validate_state_entry(key, value)
        with get_connection(self.database_path) as connection:
            with transaction(connection):
                ensure_session(connection, session_id)
                write_session_state(connection, session_id, {key: value})


def write_session_state(connection: sqlite3.Connection, session_id: str, values: dict[str, object]) -> None:
    current_timestamp = _current_timestamp()
    for state_key, state_value in values.items():
        validate_state_entry(state_key, state_value)
    for state_key, state_value in values.items():
        connection.execute(
            "INSERT INTO session_state "
            "(session_id, state_key, state_value, value_type, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id, state_key) DO UPDATE SET "
            "state_value = excluded.state_value, "
            "value_type = excluded.value_type, "
            "updated_at = excluded.updated_at",
            (session_id, state_key, encode_json_payload(state_value), "json", current_timestamp),
        )

    connection.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (current_timestamp, session_id))


def ensure_session(connection: sqlite3.Connection, session_id: str) -> None:
    current_timestamp = _current_timestamp()
    connection.execute(
        "INSERT INTO sessions (session_id, created_at, updated_at, status) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at",
        (session_id, current_timestamp, current_timestamp, "active"),
    )


def encode_json_payload(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode_value(state_value: str, value_type: str) -> Any:
    if value_type != "json":
        return state_value
    return json.loads(state_value)


def _current_timestamp() -> str:
    return datetime.now(UTC).isoformat()
