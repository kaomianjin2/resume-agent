from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from interview_agent.storage import (
    get_connection,
    get_knowledge_base_status,
    initialize_database,
    set_knowledge_base_status,
    transaction,
)


EXPECTED_TABLES = {
    "knowledge_base_meta",
    "knowledge_chunks",
    "knowledge_documents",
    "node_runs",
    "session_state",
    "sessions",
}


def fetch_table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

    return {row[0] for row in rows}


def test_initialize_database_creates_only_stable_storage_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"

    initialize_database(database_path)

    table_names = fetch_table_names(database_path)

    assert table_names == EXPECTED_TABLES


def test_get_knowledge_base_status_returns_not_ready_without_creating_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "missing.sqlite3"

    assert get_knowledge_base_status(database_path) == "not_ready"
    assert not database_path.exists()


def test_get_knowledge_base_status_returns_not_ready_for_uninitialized_database_file(tmp_path: Path) -> None:
    database_path = tmp_path / "empty.sqlite3"
    database_path.touch()

    assert get_knowledge_base_status(database_path) == "not_ready"
    assert database_path.exists()


def test_knowledge_base_status_defaults_to_not_ready_and_can_be_marked_ready(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    assert get_knowledge_base_status(database_path) == "not_ready"

    set_knowledge_base_status(database_path, "ready")

    assert get_knowledge_base_status(database_path) == "ready"


def test_transaction_rolls_back_partial_records_when_write_fails(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    connection = get_connection(database_path)

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(connection):
            connection.execute(
                """
                INSERT INTO sessions (session_id, created_at, updated_at, status)
                VALUES (?, ?, ?, ?)
                """,
                ("session-1", "2026-05-11T00:00:00", "2026-05-11T00:00:00", "active"),
            )
            connection.execute(
                """
                INSERT INTO session_state (
                    session_id,
                    state_key,
                    state_value,
                    value_type,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("missing-session", "plan", "{}", "json", "2026-05-11T00:00:00"),
            )

    session_rows = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()
    assert session_rows is not None
    assert session_rows[0] == 0

    connection.close()


def test_transaction_rolls_back_when_commit_fails(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    connection = get_connection(database_path)
    connection.execute("PRAGMA defer_foreign_keys = ON")

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(connection):
            connection.execute(
                """
                INSERT INTO session_state (
                    session_id,
                    state_key,
                    state_value,
                    value_type,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("missing-session", "plan", "{}", "json", "2026-05-11T00:00:00"),
            )

    assert connection.in_transaction is False

    session_state_rows = connection.execute("SELECT COUNT(*) FROM session_state").fetchone()
    assert session_state_rows is not None
    assert session_state_rows[0] == 0

    connection.close()
