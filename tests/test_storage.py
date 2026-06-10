from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from interview_agent.storage import (
    clear_job_application_data,
    create_user,
    get_connection,
    get_knowledge_base_status,
    initialize_database,
    list_job_applications,
    list_users,
    record_collection_progress,
    save_job_application,
    save_platform_collection_task,
    set_knowledge_base_status,
    update_job_application_status,
    set_user_status,
    transaction,
    verify_login,
)


EXPECTED_TABLES = {
    "application_confirmations",
    "application_records",
    "collection_platform_progress",
    "collection_tasks",
    "job_application_evaluations",
    "job_applications",
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


def test_job_application_storage_supports_save_list_and_duplicate_detection(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    first_job = save_job_application(
        database_path,
        platform="boss",
        external_job_id="job-001",
        job_url="https://example.com/jobs/1",
        company_name="OpenAI",
        title="Research Engineer",
        location="Shanghai",
        employment_type="full_time",
        salary_range="40k-60k",
        posted_at="2026-06-10T09:00:00+00:00",
        normalized_payload='{"platform":"boss"}',
    )
    duplicate_job = save_job_application(
        database_path,
        platform="boss",
        external_job_id="job-001",
        job_url="https://example.com/jobs/1",
        company_name="OpenAI",
        title="Research Engineer",
        location="Shanghai",
        employment_type="full_time",
        salary_range="40k-60k",
        posted_at="2026-06-10T09:00:00+00:00",
        normalized_payload='{"platform":"boss"}',
    )
    jobs = list_job_applications(database_path)

    assert first_job["is_duplicate"] is False
    assert duplicate_job["is_duplicate"] is True
    assert duplicate_job["job_id"] == first_job["job_id"]
    assert len(jobs) == 1
    assert jobs[0]["platform"] == "boss"
    assert jobs[0]["status"] == "pending_review"


def test_job_application_status_updates_track_confirmation_batch(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    saved_job = save_job_application(
        database_path,
        platform="lagou",
        external_job_id="job-002",
        job_url="https://example.com/jobs/2",
        company_name="Example",
        title="Backend Engineer",
        location="Hangzhou",
        employment_type="full_time",
        salary_range="30k-45k",
        posted_at="2026-06-10T10:00:00+00:00",
        normalized_payload='{"platform":"lagou"}',
    )

    pending_record = update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="pending_review",
        confirmation_batch_id="batch-001",
    )
    submitted_record = update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="submitted",
        confirmation_batch_id="batch-001",
        submitted_at="2026-06-10T10:05:00+00:00",
        platform_message="submitted",
    )
    failed_record = update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="failed",
        confirmation_batch_id="batch-001",
        failure_reason="network",
    )
    skipped_record = update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="skipped",
        confirmation_batch_id="batch-001",
        failure_reason="stale",
    )
    duplicate_record = update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="duplicate",
        confirmation_batch_id="batch-001",
        duplicate_detected=True,
    )

    assert pending_record["status"] == "pending_review"
    assert submitted_record["status"] == "submitted"
    assert submitted_record["submitted_at"] == "2026-06-10T10:05:00+00:00"
    assert failed_record["failure_reason"] == "network"
    assert skipped_record["status"] == "skipped"
    assert duplicate_record["duplicate_detected"] is True


def test_collection_progress_and_clear_job_application_data_preserve_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    saved_job = save_job_application(
        database_path,
        platform="liepin",
        external_job_id="job-003",
        job_url="https://example.com/jobs/3",
        company_name="Another",
        title="ML Engineer",
        location="Beijing",
        employment_type="full_time",
        salary_range="35k-50k",
        posted_at="2026-06-10T11:00:00+00:00",
        normalized_payload='{"platform":"liepin"}',
    )
    save_platform_collection_task(
        database_path,
        collection_task_id="task-001",
        platform="liepin",
        search_keyword="ml",
        status="running",
    )
    record_collection_progress(
        database_path,
        collection_task_id="task-001",
        platform="liepin",
        current_page=3,
        last_job_offset=40,
        retry_count=2,
        failure_reason="captcha",
        manual_takeover_required=True,
        status="paused",
    )
    update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="submitted",
        confirmation_batch_id="batch-002",
        submitted_at="2026-06-10T11:05:00+00:00",
    )

    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO sessions (session_id, created_at, updated_at, status)
            VALUES (?, ?, ?, ?)
            """,
            ("session-keep", "2026-06-10T11:00:00+00:00", "2026-06-10T11:00:00+00:00", "active"),
        )
        connection.execute(
            """
            INSERT INTO session_state (session_id, state_key, state_value, value_type, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("session-keep", "plan", "{}", "json", "2026-06-10T11:00:00+00:00"),
        )

    clear_job_application_data(database_path)

    with get_connection(database_path) as connection:
        job_count = connection.execute("SELECT COUNT(*) FROM job_applications").fetchone()
        task_count = connection.execute("SELECT COUNT(*) FROM collection_tasks").fetchone()
        progress_count = connection.execute("SELECT COUNT(*) FROM collection_platform_progress").fetchone()
        record_count = connection.execute("SELECT COUNT(*) FROM application_records").fetchone()
        session_count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()
        state_count = connection.execute("SELECT COUNT(*) FROM session_state").fetchone()

    assert job_count is not None
    assert task_count is not None
    assert progress_count is not None
    assert record_count is not None
    assert session_count is not None
    assert state_count is not None
    assert job_count[0] == 0
    assert task_count[0] == 0
    assert progress_count[0] == 0
    assert record_count[0] == 0
    assert session_count[0] == 1
    assert state_count[0] == 1
