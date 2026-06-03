from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from interview_agent.storage import (
    create_user,
    get_connection,
    get_knowledge_base_status,
    initialize_database,
    list_users,
    set_knowledge_base_status,
    set_user_status,
    transaction,
    verify_login,
)


EXPECTED_TABLES = {
    "knowledge_base_meta",
    "knowledge_chunks",
    "knowledge_documents",
    "node_runs",
    "session_state",
    "sessions",
    "users",
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


def test_user_create_list_and_login(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    created_user = create_user(
        database_path,
        username="admin1",
        password="pass123",
        role="admin",
    )
    users = list_users(database_path)
    login_result = verify_login(database_path, username="admin1", password="pass123")

    assert created_user["username"] == "admin1"
    assert created_user["role"] == "admin"
    assert created_user["status"] == "enabled"
    assert len(users) == 1
    assert users[0]["username"] == "admin1"
    assert users[0]["role"] == "admin"
    assert login_result is not None
    assert login_result["username"] == "admin1"
    assert login_result["role"] == "admin"


def test_disabled_user_cannot_login(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    create_user(
        database_path,
        username="member1",
        password="pass123",
        role="member",
    )

    assert set_user_status(database_path, username="member1", status="disabled") is True
    assert verify_login(database_path, username="member1", password="pass123") is None


def test_default_admin_login_repairs_existing_admin_password(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    create_user(database_path, username="admin", password="broken-password", role="member", status="disabled")

    login_result = verify_login(database_path, username="admin", password="admin")
    users = list_users(database_path)

    assert login_result is not None
    assert login_result["username"] == "admin"
    assert login_result["role"] == "admin"
    assert login_result["status"] == "enabled"
    assert len(users) == 1
    assert users[0]["role"] == "admin"
    assert users[0]["status"] == "enabled"
