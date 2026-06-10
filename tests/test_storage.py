from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from interview_agent.storage import (
    clear_job_application_data,
    create_user,
    get_collection_progress,
    get_confirmation_batch,
    get_job_application_evaluation,
    get_job_application_filters,
    get_connection,
    get_knowledge_base_status,
    initialize_database,
    list_job_applications,
    list_users,
    record_collection_progress,
    save_job_application_evaluation,
    save_job_application_filters,
    save_job_application,
    save_platform_collection_task,
    set_knowledge_base_status,
    update_job_application_status,
    set_user_status,
    transaction,
    verify_login,
)
from interview_agent.session import SessionStore


EXPECTED_TABLES = {
    "application_confirmations",
    "application_records",
    "collection_platform_progress",
    "collection_tasks",
    "job_application_filters",
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


def test_job_application_storage_uses_platform_job_id_contract_and_duplicate_detection(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    first_job = save_job_application(
        database_path,
        platform="boss",
        platform_job_id="job-001",
        job_url="https://example.com/jobs/1",
        company_name="OpenAI",
        title="Research Engineer",
        location="Shanghai",
        employment_type="full_time",
        salary_range="40k-60k",
        posted_at="2026-06-10T09:00:00+00:00",
        remote_policy="hybrid",
        level="senior",
        experience_requirement="5 years",
        education_requirement="bachelor",
        industry="ai",
        company_size="100-499",
        funding_stage="series_c",
        tech_stack="python, llm",
        benefits="meal, stock",
        published_at="2026-06-09T09:00:00+00:00",
        detail_url="https://example.com/jobs/1?track=abc",
        jd_text="build agents",
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence='{"salary_range":"high"}',
        normalized_payload='{"platform":"boss"}',
    )
    duplicate_job = save_job_application(
        database_path,
        platform="boss",
        platform_job_id="job-001-reposted",
        job_url="https://example.com/jobs/1?track=xyz",
        company_name="OpenAI",
        title="Research Engineer",
        location="Shanghai",
        employment_type="full_time",
        salary_range="40k-60k",
        posted_at="2026-06-10T09:00:00+00:00",
        remote_policy="hybrid",
        level="senior",
        experience_requirement="5 years",
        education_requirement="bachelor",
        industry="ai",
        company_size="100-499",
        funding_stage="series_c",
        tech_stack="python, llm",
        benefits="meal, stock",
        published_at="2026-06-09T09:00:00+00:00",
        detail_url="https://example.com/jobs/1?track=xyz",
        jd_text="build agents",
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence='{"salary_range":"high"}',
        normalized_payload='{"platform":"boss"}',
    )
    cross_platform_job = save_job_application(
        database_path,
        platform="lagou",
        platform_job_id="job-001-reposted",
        job_url="https://example.com/jobs/1?track=lagou",
        company_name="OpenAI",
        title="Research Engineer",
        location="Shanghai",
        employment_type="full_time",
        salary_range="40k-60k",
        posted_at="2026-06-10T09:00:00+00:00",
        remote_policy="hybrid",
        level="senior",
        experience_requirement="5 years",
        education_requirement="bachelor",
        industry="ai",
        company_size="100-499",
        funding_stage="series_c",
        tech_stack="python, llm",
        benefits="meal, stock",
        published_at="2026-06-09T09:00:00+00:00",
        detail_url="https://example.com/jobs/1?track=lagou",
        jd_text="build agents",
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence='{"salary_range":"high"}',
        normalized_payload='{"platform":"lagou"}',
    )
    jobs = list_job_applications(database_path)

    assert first_job["is_duplicate"] is False
    assert duplicate_job["is_duplicate"] is True
    assert duplicate_job["job_id"] == first_job["job_id"]
    assert cross_platform_job["is_duplicate"] is False
    assert "platform_job_id" in first_job
    assert "external_job_id" not in first_job
    assert len(jobs) == 2
    assert jobs[0]["platform"] == "boss"
    assert jobs[0]["platform_job_id"] == "job-001"
    assert "external_job_id" not in jobs[0]
    assert jobs[0]["status"] == "pending_review"
    assert jobs[0]["remote_policy"] == "hybrid"
    assert jobs[0]["level"] == "senior"
    assert jobs[0]["experience_requirement"] == "5 years"
    assert jobs[0]["education_requirement"] == "bachelor"
    assert jobs[0]["industry"] == "ai"
    assert jobs[0]["company_size"] == "100-499"
    assert jobs[0]["funding_stage"] == "series_c"
    assert jobs[0]["tech_stack"] == "python, llm"
    assert jobs[0]["benefits"] == "meal, stock"
    assert jobs[0]["published_at"] == "2026-06-09T09:00:00+00:00"
    assert jobs[0]["detail_url"] == "https://example.com/jobs/1?track=abc"
    assert jobs[0]["jd_text"] == "build agents"
    assert jobs[0]["collected_at"] == "2026-06-10T09:05:00+00:00"
    assert jobs[0]["field_confidence"] == '{"salary_range":"high"}'


def test_job_application_filters_and_evaluation_are_queryable_after_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    saved_job = save_job_application(
        database_path,
        platform="lagou",
        platform_job_id="job-002",
        job_url="https://example.com/jobs/2",
        company_name="Example",
        title="Backend Engineer",
        location="Hangzhou",
        employment_type="full_time",
        salary_range="30k-45k",
        posted_at="2026-06-10T10:00:00+00:00",
        remote_policy="onsite",
        level="mid",
        experience_requirement="3 years",
        education_requirement="bachelor",
        industry="saas",
        company_size="500-999",
        funding_stage="public",
        tech_stack="python, postgres",
        benefits="bonus",
        published_at="2026-06-10T08:00:00+00:00",
        detail_url="https://example.com/jobs/2",
        jd_text="build apis",
        collected_at="2026-06-10T10:05:00+00:00",
        field_confidence='{"title":"high"}',
        normalized_payload='{"platform":"lagou"}',
    )
    save_job_application_filters(
        database_path,
        filter_id="filter-001",
        hard_filters='{"city":["Hangzhou"],"salary_min":30000}',
        ranking_preferences='{"skills":["python"],"prefer_remote":false}',
    )
    save_job_application_evaluation(
        database_path,
        evaluation_id="eval-001",
        job_id=saved_job["job_id"],
        score=91.5,
        hard_filter_status="passed",
        strengths='["python"]',
        risks='["none"]',
        missing_information='[]',
        resume_improvement_advice='["quantify impact"]',
        application_message="hello",
        recommended=True,
        recommendation_reason="strong fit",
    )

    filters = get_job_application_filters(database_path, filter_id="filter-001")
    evaluation = get_job_application_evaluation(database_path, job_id=saved_job["job_id"])

    assert filters is not None
    assert filters["hard_filters"] == '{"city":["Hangzhou"],"salary_min":30000}'
    assert filters["ranking_preferences"] == '{"skills":["python"],"prefer_remote":false}'
    assert evaluation is not None
    assert evaluation["score"] == 91.5
    assert evaluation["recommended"] is True
    assert evaluation["recommendation_reason"] == "strong fit"


def test_confirmation_batch_keeps_batch_metadata_and_job_results_separate(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    first_job = save_job_application(
        database_path,
        platform="lagou",
        platform_job_id="job-002",
        job_url="https://example.com/jobs/2",
        company_name="Example",
        title="Backend Engineer",
        location="Hangzhou",
        employment_type="full_time",
        salary_range="30k-45k",
        posted_at="2026-06-10T10:00:00+00:00",
        remote_policy="onsite",
        level="mid",
        experience_requirement="3 years",
        education_requirement="bachelor",
        industry="saas",
        company_size="500-999",
        funding_stage="public",
        tech_stack="python, postgres",
        benefits="bonus",
        published_at="2026-06-10T08:00:00+00:00",
        detail_url="https://example.com/jobs/2",
        jd_text="build apis",
        collected_at="2026-06-10T10:05:00+00:00",
        field_confidence='{"title":"high"}',
        normalized_payload='{"platform":"lagou"}',
    )
    second_job = save_job_application(
        database_path,
        platform="lagou",
        platform_job_id="job-003",
        job_url="https://example.com/jobs/3",
        company_name="Example",
        title="Platform Engineer",
        location="Hangzhou",
        employment_type="full_time",
        salary_range="30k-45k",
        posted_at="2026-06-10T10:00:00+00:00",
        remote_policy="onsite",
        level="mid",
        experience_requirement="3 years",
        education_requirement="bachelor",
        industry="saas",
        company_size="500-999",
        funding_stage="public",
        tech_stack="python, postgres",
        benefits="bonus",
        published_at="2026-06-10T08:00:00+00:00",
        detail_url="https://example.com/jobs/3",
        jd_text="build platforms",
        collected_at="2026-06-10T10:06:00+00:00",
        field_confidence='{"title":"high"}',
        normalized_payload='{"platform":"lagou"}',
    )
    update_job_application_status(
        database_path,
        job_id=first_job["job_id"],
        status="submitted",
        confirmation_batch_id="batch-001",
        confirmation_status="confirmed",
        confirmed_at="2026-06-10T10:08:00+00:00",
        submitted_at="2026-06-10T10:09:00+00:00",
        platform_message="submitted",
    )
    update_job_application_status(
        database_path,
        job_id=second_job["job_id"],
        status="failed",
        confirmation_batch_id="batch-001",
        confirmation_status="confirmed",
        confirmed_at="2026-06-10T10:08:00+00:00",
        failure_reason="network",
    )
    batch = get_confirmation_batch(database_path, confirmation_batch_id="batch-001")

    assert batch is not None
    assert batch["status"] == "confirmed"
    assert batch["confirmed_at"] == "2026-06-10T10:08:00+00:00"
    assert len(batch["records"]) == 2
    assert batch["records"][0]["status"] == "submitted"
    assert batch["records"][1]["status"] == "failed"
    assert batch["records"][1]["failure_reason"] == "network"


def test_collection_progress_is_queryable_and_clear_job_application_data_preserve_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    saved_job = save_job_application(
        database_path,
        platform="liepin",
        platform_job_id="job-003",
        job_url="https://example.com/jobs/3",
        company_name="Another",
        title="ML Engineer",
        location="Beijing",
        employment_type="full_time",
        salary_range="35k-50k",
        posted_at="2026-06-10T11:00:00+00:00",
        remote_policy="remote",
        level="staff",
        experience_requirement="6 years",
        education_requirement="master",
        industry="ai",
        company_size="1000+",
        funding_stage="public",
        tech_stack="python, ml",
        benefits="stock",
        published_at="2026-06-10T10:30:00+00:00",
        detail_url="https://example.com/jobs/3",
        jd_text="train models",
        collected_at="2026-06-10T11:01:00+00:00",
        field_confidence='{"jd_text":"medium"}',
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
    progress = get_collection_progress(database_path, collection_task_id="task-001", platform="liepin")
    update_job_application_status(
        database_path,
        job_id=saved_job["job_id"],
        status="submitted",
        confirmation_batch_id="batch-002",
        confirmation_status="confirmed",
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

    assert progress is not None
    assert progress["current_page"] == 3
    assert progress["retry_count"] == 2
    assert progress["manual_takeover_required"] is True
    assert progress["failure_reason"] == "captcha"

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


def test_job_application_storage_rejects_sensitive_content_across_all_text_inputs(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)

    with pytest.raises(ValueError, match="敏感"):
        save_job_application(
            database_path,
            platform="boss",
            platform_job_id="job-sensitive",
            job_url="https://example.com/jobs/sensitive",
            company_name="OpenAI",
            title="Research Engineer",
            location="Shanghai",
            employment_type="full_time",
            salary_range="40k-60k",
            posted_at="2026-06-10T09:00:00+00:00",
            remote_policy="hybrid",
            level="senior",
            experience_requirement="5 years",
            education_requirement="bachelor",
            industry="ai",
            company_size="100-499",
            funding_stage="series_c",
            tech_stack="python, llm, credential",
            benefits="联系邮箱 hr@example.com",
            published_at="2026-06-09T09:00:00+00:00",
            detail_url="https://example.com/jobs/sensitive",
            jd_text="auth flow with account_id=abc",
            collected_at="2026-06-10T09:05:00+00:00",
            field_confidence='{"token":"secret","phone":"13800000000"}',
            normalized_payload='{"contact":"13800000000","note":"password=abc","verify":"验证码 123456"}',
        )

    saved_job = save_job_application(
        database_path,
        platform="lagou",
        platform_job_id="safe-job",
        job_url="https://example.com/jobs/safe",
        company_name="OpenAI",
        title="Platform Engineer",
        location="Shanghai",
        employment_type="full_time",
        salary_range="40k-60k",
        posted_at="2026-06-10T09:00:00+00:00",
        remote_policy="hybrid",
        level="senior",
        experience_requirement="5 years",
        education_requirement="bachelor",
        industry="ai",
        company_size="100-499",
        funding_stage="series_c",
        tech_stack="python, llm",
        benefits="meal, stock",
        published_at="2026-06-09T09:00:00+00:00",
        detail_url="https://example.com/jobs/safe",
        jd_text="build agents",
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence='{"salary_range":"high"}',
        normalized_payload='{"platform":"lagou"}',
    )

    with pytest.raises(ValueError, match="敏感"):
        save_job_application_filters(
            database_path,
            filter_id="filter-sensitive",
            hard_filters='{"contact":"hr@example.com"}',
            ranking_preferences='{"auth":"required"}',
        )

    with pytest.raises(ValueError, match="敏感"):
        save_job_application_evaluation(
            database_path,
            evaluation_id="eval-sensitive",
            job_id=saved_job["job_id"],
            score=88.0,
            hard_filter_status="passed",
            strengths='["account_id"]',
            risks='["电话 13800000000"]',
            missing_information='["credential"]',
            resume_improvement_advice='["补充密码"]',
            application_message="cookie token session",
            recommended=True,
            recommendation_reason="auth strong",
        )

    with pytest.raises(ValueError, match="敏感"):
        update_job_application_status(
            database_path,
            job_id=saved_job["job_id"],
            status="failed",
            confirmation_batch_id="batch-sensitive",
            confirmation_status="confirmed",
            failure_reason="account_id blocked",
            platform_message="需要验证码",
        )

    save_platform_collection_task(
        database_path,
        collection_task_id="task-sensitive",
        platform="lagou",
        search_keyword="python",
        status="running",
    )
    with pytest.raises(ValueError, match="敏感"):
        record_collection_progress(
            database_path,
            collection_task_id="task-sensitive",
            platform="lagou",
            current_page=1,
            last_job_offset=0,
            retry_count=1,
            failure_reason="auth credential account_id=123",
            manual_takeover_required=True,
            status="paused",
        )


def test_session_state_rejects_browser_session_and_contact_payload(tmp_path: Path) -> None:
    database_path = tmp_path / "storage.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    with pytest.raises(ValueError, match="敏感"):
        session_store.set_state(
            "session-sensitive",
            "job_search_profile",
            {
                "target_roles": ["后端工程师"],
                "browser_session": {"cookie": "sid=secret"},
                "phone": "13800000000",
            },
        )

    with sqlite3.connect(database_path) as connection:
        state_count = connection.execute("SELECT COUNT(*) FROM session_state").fetchone()

    assert state_count == (0,)
