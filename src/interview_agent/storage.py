from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from interview_agent.sensitive import assert_no_sensitive_payload


DEFAULT_KNOWLEDGE_BASE_STATUS = "not_ready"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
JOB_APPLICATION_STATUSES = {"pending_review", "approved", "submitted", "failed", "skipped", "duplicate"}
CONFIRMATION_BATCH_STATUSES = {"pending_review", "confirmed", "submitted", "failed", "skipped"}
def get_connection(database_path: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path | str) -> None:
    resolved_path = Path(database_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(resolved_path) as connection:
        connection.executescript(schema)
        connection.execute(
            """
            INSERT INTO knowledge_base_meta (singleton_id, status, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(singleton_id) DO NOTHING
            """,
            (DEFAULT_KNOWLEDGE_BASE_STATUS, _current_timestamp()),
        )


def get_knowledge_base_status(database_path: Path | str) -> str:
    resolved_path = Path(database_path)
    if not resolved_path.exists():
        return DEFAULT_KNOWLEDGE_BASE_STATUS

    try:
        with _get_readonly_connection(resolved_path) as connection:
            row = connection.execute(
                """
                SELECT status
                FROM knowledge_base_meta
                WHERE singleton_id = 1
                """
            ).fetchone()
    except sqlite3.OperationalError:
        return DEFAULT_KNOWLEDGE_BASE_STATUS

    if row is None:
        return DEFAULT_KNOWLEDGE_BASE_STATUS

    return str(row[0])


def set_knowledge_base_status(database_path: Path | str, status: str) -> None:
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO knowledge_base_meta (singleton_id, status, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(singleton_id) DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (status, _current_timestamp()),
        )


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    connection.execute("BEGIN")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _get_readonly_connection(database_path: Path) -> sqlite3.Connection:
    database_uri = database_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(database_uri, uri=True)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_user(
    database_path: Path | str,
    *,
    username: str,
    password: str,
    role: str,
    status: str = "enabled",
) -> dict[str, str]:
    normalized_username = username.strip()
    normalized_role = role.strip()
    normalized_status = status.strip()
    if not normalized_username:
        raise ValueError("用户名不能为空")
    if not password:
        raise ValueError("密码不能为空")
    if normalized_role not in {"admin", "member"}:
        raise ValueError("角色必须是 admin 或 member")
    if normalized_status not in {"enabled", "disabled"}:
        raise ValueError("状态必须是 enabled 或 disabled")

    timestamp = _current_timestamp()
    user_id = f"user-{uuid4()}"
    password_hash = _hash_password(password)
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (user_id, username, password_hash, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, normalized_username, password_hash, normalized_role, normalized_status, timestamp, timestamp),
        )
    return {"user_id": user_id, "username": normalized_username, "role": normalized_role, "status": normalized_status}


def list_users(database_path: Path | str) -> list[dict[str, str]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT user_id, username, role, status, created_at, updated_at
            FROM users
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [
        {
            "user_id": str(row[0]),
            "username": str(row[1]),
            "role": str(row[2]),
            "status": str(row[3]),
            "created_at": str(row[4]),
            "updated_at": str(row[5]),
        }
        for row in rows
    ]


def set_user_status(database_path: Path | str, *, username: str, status: str) -> bool:
    normalized_status = status.strip()
    if normalized_status not in {"enabled", "disabled"}:
        raise ValueError("状态必须是 enabled 或 disabled")
    with get_connection(database_path) as connection:
        result = connection.execute(
            """
            UPDATE users
            SET status = ?, updated_at = ?
            WHERE username = ?
            """,
            (normalized_status, _current_timestamp(), username.strip()),
        )
    return result.rowcount > 0


def verify_login(database_path: Path | str, *, username: str, password: str) -> dict[str, str] | None:
    normalized_username = username.strip()
    if normalized_username == DEFAULT_ADMIN_USERNAME and password == DEFAULT_ADMIN_PASSWORD:
        _ensure_default_admin(database_path)

    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT user_id, username, password_hash, role, status
            FROM users
            WHERE username = ?
            """,
            (normalized_username,),
        ).fetchone()
    if row is None:
        return None
    if str(row[4]) != "enabled":
        return None
    if _hash_password(password) != str(row[2]):
        return None
    return {"user_id": str(row[0]), "username": str(row[1]), "role": str(row[3]), "status": str(row[4])}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _ensure_default_admin(database_path: Path | str) -> None:
    initialize_database(database_path)
    timestamp = _current_timestamp()
    password_hash = _hash_password(DEFAULT_ADMIN_PASSWORD)
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (user_id, username, password_hash, role, status, created_at, updated_at)
            VALUES (?, ?, ?, 'admin', 'enabled', ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = 'admin',
                status = 'enabled',
                updated_at = excluded.updated_at
            """,
            (
                f"user-{uuid4()}",
                DEFAULT_ADMIN_USERNAME,
                password_hash,
                timestamp,
                timestamp,
            ),
        )


def save_job_application(
    database_path: Path | str,
    *,
    platform: str,
    platform_job_id: str,
    job_url: str,
    company_name: str,
    title: str,
    location: str,
    employment_type: str | None,
    salary_range: str | None,
    posted_at: str | None,
    remote_policy: str | None,
    level: str | None,
    experience_requirement: str | None,
    education_requirement: str | None,
    industry: str | None,
    company_size: str | None,
    funding_stage: str | None,
    tech_stack: str | None,
    benefits: str | None,
    published_at: str | None,
    detail_url: str,
    jd_text: str,
    collected_at: str,
    field_confidence: str,
    normalized_payload: str,
) -> dict[str, str | bool | None]:
    required_fields = _normalize_required_job_fields(
        platform=platform,
        platform_job_id=platform_job_id,
        job_url=job_url,
        company_name=company_name,
        title=title,
        location=location,
        detail_url=detail_url,
        jd_text=jd_text,
        collected_at=collected_at,
        field_confidence=field_confidence,
        normalized_payload=normalized_payload,
    )
    optional_fields = _normalize_optional_job_fields(
        employment_type=employment_type,
        salary_range=salary_range,
        posted_at=posted_at,
        remote_policy=remote_policy,
        level=level,
        experience_requirement=experience_requirement,
        education_requirement=education_requirement,
        industry=industry,
        company_size=company_size,
        funding_stage=funding_stage,
        tech_stack=tech_stack,
        benefits=benefits,
        published_at=published_at,
    )
    _assert_no_sensitive_content([*required_fields.values(), *optional_fields.values()])
    duplicate_key = _build_duplicate_key(
        required_fields["platform"],
        required_fields["company_name"],
        required_fields["title"],
        required_fields["location"],
        required_fields["detail_url"],
    )
    with get_connection(database_path) as connection:
        existing_row = connection.execute(
            """
            SELECT job_id, platform, platform_job_id, job_url, company_name, title, location,
                   employment_type, salary_range, posted_at, remote_policy, level,
                   experience_requirement, education_requirement, industry, company_size,
                   funding_stage, tech_stack, benefits, published_at, detail_url, jd_text,
                   collected_at, field_confidence, normalized_payload, status, created_at, updated_at
            FROM job_applications
            WHERE duplicate_key = ?
            """,
            (duplicate_key,),
        ).fetchone()
        if existing_row is not None:
            return {**_job_application_from_row(existing_row), "is_duplicate": True}

        timestamp = _current_timestamp()
        job_id = f"job-{uuid4()}"
        connection.execute(
            """
            INSERT INTO job_applications (
                job_id, platform, platform_job_id, job_url, company_name, title, location,
                employment_type, salary_range, posted_at, remote_policy, level,
                experience_requirement, education_requirement, industry, company_size,
                funding_stage, tech_stack, benefits, published_at, detail_url, jd_text,
                collected_at, field_confidence, normalized_payload, status, duplicate_key,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?)
            """,
            (
                job_id,
                required_fields["platform"],
                required_fields["platform_job_id"],
                required_fields["job_url"],
                required_fields["company_name"],
                required_fields["title"],
                required_fields["location"],
                optional_fields["employment_type"],
                optional_fields["salary_range"],
                optional_fields["posted_at"],
                optional_fields["remote_policy"],
                optional_fields["level"],
                optional_fields["experience_requirement"],
                optional_fields["education_requirement"],
                optional_fields["industry"],
                optional_fields["company_size"],
                optional_fields["funding_stage"],
                optional_fields["tech_stack"],
                optional_fields["benefits"],
                optional_fields["published_at"],
                required_fields["detail_url"],
                required_fields["jd_text"],
                required_fields["collected_at"],
                required_fields["field_confidence"],
                required_fields["normalized_payload"],
                duplicate_key,
                timestamp,
                timestamp,
            ),
        )
    return {
        "job_id": job_id,
        **required_fields,
        **optional_fields,
        "status": "pending_review",
        "created_at": timestamp,
        "updated_at": timestamp,
        "is_duplicate": False,
    }


def list_job_applications(database_path: Path | str) -> list[dict[str, str | None]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT job_id, platform, platform_job_id, job_url, company_name, title, location,
                   employment_type, salary_range, posted_at, remote_policy, level,
                   experience_requirement, education_requirement, industry, company_size,
                   funding_stage, tech_stack, benefits, published_at, detail_url, jd_text,
                   collected_at, field_confidence, normalized_payload, status, created_at, updated_at
            FROM job_applications
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [_job_application_from_row(row) for row in rows]


def get_job_application_by_id(database_path: Path | str, *, job_id: str) -> dict[str, str | None] | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT job_id, platform, platform_job_id, job_url, company_name, title, location,
                   employment_type, salary_range, posted_at, remote_policy, level,
                   experience_requirement, education_requirement, industry, company_size,
                   funding_stage, tech_stack, benefits, published_at, detail_url, jd_text,
                   collected_at, field_confidence, normalized_payload, status, created_at, updated_at
            FROM job_applications
            WHERE job_id = ?
            """,
            (job_id.strip(),),
        ).fetchone()
    if row is None:
        return None
    return _job_application_from_row(row)


def save_job_application_filters(
    database_path: Path | str,
    *,
    filter_id: str,
    hard_filters: str,
    ranking_preferences: str,
) -> dict[str, str]:
    normalized_filter_id = filter_id.strip()
    normalized_hard_filters = hard_filters.strip()
    normalized_ranking_preferences = ranking_preferences.strip()
    if not all([normalized_filter_id, normalized_hard_filters, normalized_ranking_preferences]):
        raise ValueError("筛选条件不能为空")
    _assert_no_sensitive_content([normalized_hard_filters, normalized_ranking_preferences])
    timestamp = _current_timestamp()
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO job_application_filters (filter_id, hard_filters, ranking_preferences, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(filter_id) DO UPDATE SET
                hard_filters = excluded.hard_filters,
                ranking_preferences = excluded.ranking_preferences,
                updated_at = excluded.updated_at
            """,
            (normalized_filter_id, normalized_hard_filters, normalized_ranking_preferences, timestamp, timestamp),
        )
    return {
        "filter_id": normalized_filter_id,
        "hard_filters": normalized_hard_filters,
        "ranking_preferences": normalized_ranking_preferences,
    }


def get_job_application_filters(database_path: Path | str, *, filter_id: str) -> dict[str, str] | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT filter_id, hard_filters, ranking_preferences, created_at, updated_at
            FROM job_application_filters
            WHERE filter_id = ?
            """,
            (filter_id.strip(),),
        ).fetchone()
    if row is None:
        return None
    return {
        "filter_id": str(row[0]),
        "hard_filters": str(row[1]),
        "ranking_preferences": str(row[2]),
        "created_at": str(row[3]),
        "updated_at": str(row[4]),
    }


def save_job_application_evaluation(
    database_path: Path | str,
    *,
    evaluation_id: str,
    job_id: str,
    score: float,
    hard_filter_status: str,
    strengths: str,
    risks: str,
    missing_information: str,
    resume_improvement_advice: str,
    application_message: str,
    recommended: bool,
    recommendation_reason: str,
) -> dict[str, str | float | bool]:
    normalized_values = [
        evaluation_id.strip(),
        job_id.strip(),
        hard_filter_status.strip(),
        strengths.strip(),
        risks.strip(),
        missing_information.strip(),
        resume_improvement_advice.strip(),
        application_message.strip(),
        recommendation_reason.strip(),
    ]
    if not all(normalized_values):
        raise ValueError("评估字段不能为空")
    _assert_no_sensitive_content(normalized_values)
    timestamp = _current_timestamp()
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO job_application_evaluations (
                evaluation_id, job_id, score, hard_filter_status, strengths, risks,
                missing_information, resume_improvement_advice, application_message,
                recommended, recommendation_reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                evaluation_id = excluded.evaluation_id,
                score = excluded.score,
                hard_filter_status = excluded.hard_filter_status,
                strengths = excluded.strengths,
                risks = excluded.risks,
                missing_information = excluded.missing_information,
                resume_improvement_advice = excluded.resume_improvement_advice,
                application_message = excluded.application_message,
                recommended = excluded.recommended,
                recommendation_reason = excluded.recommendation_reason,
                updated_at = excluded.updated_at
            """,
            (
                normalized_values[0],
                normalized_values[1],
                score,
                normalized_values[2],
                normalized_values[3],
                normalized_values[4],
                normalized_values[5],
                normalized_values[6],
                normalized_values[7],
                int(recommended),
                normalized_values[8],
                timestamp,
                timestamp,
            ),
        )
    return {"evaluation_id": normalized_values[0], "job_id": normalized_values[1], "score": score, "recommended": recommended}


def get_job_application_evaluation(database_path: Path | str, *, job_id: str) -> dict[str, str | float | bool] | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT evaluation_id, job_id, score, hard_filter_status, strengths, risks,
                   missing_information, resume_improvement_advice, application_message,
                   recommended, recommendation_reason, created_at, updated_at
            FROM job_application_evaluations
            WHERE job_id = ?
            """,
            (job_id.strip(),),
        ).fetchone()
    if row is None:
        return None
    return {
        "evaluation_id": str(row[0]),
        "job_id": str(row[1]),
        "score": float(row[2]),
        "hard_filter_status": str(row[3]),
        "strengths": str(row[4]),
        "risks": str(row[5]),
        "missing_information": str(row[6]),
        "resume_improvement_advice": str(row[7]),
        "application_message": str(row[8]),
        "recommended": bool(row[9]),
        "recommendation_reason": str(row[10]),
        "created_at": str(row[11]),
        "updated_at": str(row[12]),
    }


def update_job_application_status(
    database_path: Path | str,
    *,
    job_id: str,
    status: str,
    confirmation_batch_id: str,
    confirmation_status: str = "pending_review",
    confirmed_at: str | None = None,
    submitted_at: str | None = None,
    failure_reason: str | None = None,
    platform_message: str | None = None,
    duplicate_detected: bool = False,
) -> dict[str, str | bool | None]:
    normalized_status = status.strip()
    if normalized_status not in JOB_APPLICATION_STATUSES:
        raise ValueError("投递状态不合法")
    normalized_confirmation_status = confirmation_status.strip()
    if normalized_confirmation_status not in CONFIRMATION_BATCH_STATUSES:
        raise ValueError("确认批次状态不合法")
    normalized_job_id = job_id.strip()
    normalized_batch_id = confirmation_batch_id.strip()
    if not normalized_job_id or not normalized_batch_id:
        raise ValueError("岗位和确认批次不能为空")
    _assert_no_sensitive_content([_optional_input(confirmed_at), _optional_input(submitted_at), _optional_input(failure_reason), _optional_input(platform_message)])

    timestamp = _current_timestamp()
    record_id = f"record-{uuid4()}"
    with get_connection(database_path) as connection:
        job_row = connection.execute(
            """
            SELECT platform
            FROM job_applications
            WHERE job_id = ?
            """,
            (normalized_job_id,),
        ).fetchone()
        if job_row is None:
            raise ValueError("岗位不存在")

        connection.execute(
            """
            INSERT INTO application_confirmations (confirmation_batch_id, status, confirmed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(confirmation_batch_id) DO UPDATE SET
                status = excluded.status,
                confirmed_at = COALESCE(excluded.confirmed_at, application_confirmations.confirmed_at),
                updated_at = excluded.updated_at
            """,
            (normalized_batch_id, normalized_confirmation_status, _optional_input(confirmed_at), timestamp, timestamp),
        )
        connection.execute(
            """
            UPDATE job_applications
            SET status = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (normalized_status, timestamp, normalized_job_id),
        )
        connection.execute(
            """
            INSERT INTO application_records (
                record_id, job_id, platform, confirmation_batch_id, status, submitted_at,
                failure_reason, platform_message, duplicate_detected, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, confirmation_batch_id) DO UPDATE SET
                status = excluded.status,
                submitted_at = excluded.submitted_at,
                failure_reason = excluded.failure_reason,
                platform_message = excluded.platform_message,
                duplicate_detected = excluded.duplicate_detected,
                updated_at = excluded.updated_at
            """,
            (
                record_id,
                normalized_job_id,
                str(job_row[0]),
                normalized_batch_id,
                normalized_status,
                _optional_input(submitted_at),
                _optional_input(failure_reason),
                _optional_input(platform_message),
                int(duplicate_detected),
                timestamp,
                timestamp,
            ),
        )
        record_row = connection.execute(
            """
            SELECT platform, status, submitted_at, failure_reason, platform_message, duplicate_detected
            FROM application_records
            WHERE job_id = ? AND confirmation_batch_id = ?
            """,
            (normalized_job_id, normalized_batch_id),
        ).fetchone()

    assert record_row is not None
    return {
        "job_id": normalized_job_id,
        "platform": str(record_row[0]),
        "confirmation_batch_id": normalized_batch_id,
        "status": str(record_row[1]),
        "submitted_at": _optional_text(record_row[2]),
        "failure_reason": _optional_text(record_row[3]),
        "platform_message": _optional_text(record_row[4]),
        "duplicate_detected": bool(record_row[5]),
    }


def save_platform_collection_task(
    database_path: Path | str,
    *,
    collection_task_id: str,
    platform: str,
    search_keyword: str,
    status: str,
) -> dict[str, str]:
    normalized_task_id = collection_task_id.strip()
    normalized_platform = platform.strip()
    normalized_search_keyword = search_keyword.strip()
    normalized_status = status.strip()
    if not all([normalized_task_id, normalized_platform, normalized_search_keyword, normalized_status]):
        raise ValueError("采集任务字段不能为空")

    timestamp = _current_timestamp()
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO collection_tasks (
                collection_task_id, platform, search_keyword, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_task_id) DO UPDATE SET
                platform = excluded.platform,
                search_keyword = excluded.search_keyword,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (normalized_task_id, normalized_platform, normalized_search_keyword, normalized_status, timestamp, timestamp),
        )
    return {
        "collection_task_id": normalized_task_id,
        "platform": normalized_platform,
        "search_keyword": normalized_search_keyword,
        "status": normalized_status,
    }


def record_collection_progress(
    database_path: Path | str,
    *,
    collection_task_id: str,
    platform: str,
    current_page: int,
    last_job_offset: int,
    retry_count: int,
    failure_reason: str | None,
    manual_takeover_required: bool,
    status: str,
) -> dict[str, str | int | bool | None]:
    normalized_task_id = collection_task_id.strip()
    normalized_platform = platform.strip()
    normalized_status = status.strip()
    if not all([normalized_task_id, normalized_platform, normalized_status]):
        raise ValueError("采集进度字段不能为空")
    _assert_no_sensitive_content([_optional_input(failure_reason)])

    timestamp = _current_timestamp()
    progress_id = f"progress-{uuid4()}"
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO collection_platform_progress (
                progress_id, collection_task_id, platform, current_page, last_job_offset,
                retry_count, failure_reason, manual_takeover_required, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_task_id, platform) DO UPDATE SET
                current_page = excluded.current_page,
                last_job_offset = excluded.last_job_offset,
                retry_count = excluded.retry_count,
                failure_reason = excluded.failure_reason,
                manual_takeover_required = excluded.manual_takeover_required,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                progress_id,
                normalized_task_id,
                normalized_platform,
                current_page,
                last_job_offset,
                retry_count,
                _optional_input(failure_reason),
                int(manual_takeover_required),
                normalized_status,
                timestamp,
            ),
        )
        row = connection.execute(
            """
            SELECT current_page, last_job_offset, retry_count, failure_reason, manual_takeover_required, status
            FROM collection_platform_progress
            WHERE collection_task_id = ? AND platform = ?
            """,
            (normalized_task_id, normalized_platform),
        ).fetchone()

    assert row is not None
    return {
        "collection_task_id": normalized_task_id,
        "platform": normalized_platform,
        "current_page": int(row[0]),
        "last_job_offset": int(row[1]),
        "retry_count": int(row[2]),
        "failure_reason": _optional_text(row[3]),
        "manual_takeover_required": bool(row[4]),
        "status": str(row[5]),
    }


def get_collection_progress(
    database_path: Path | str,
    *,
    collection_task_id: str,
    platform: str,
) -> dict[str, str | int | bool | None] | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT current_page, last_job_offset, retry_count, failure_reason, manual_takeover_required, status
            FROM collection_platform_progress
            WHERE collection_task_id = ? AND platform = ?
            """,
            (collection_task_id.strip(), platform.strip()),
        ).fetchone()
    if row is None:
        return None
    return {
        "collection_task_id": collection_task_id.strip(),
        "platform": platform.strip(),
        "current_page": int(row[0]),
        "last_job_offset": int(row[1]),
        "retry_count": int(row[2]),
        "failure_reason": _optional_text(row[3]),
        "manual_takeover_required": bool(row[4]),
        "status": str(row[5]),
    }


def get_confirmation_batch(database_path: Path | str, *, confirmation_batch_id: str) -> dict[str, object] | None:
    normalized_batch_id = confirmation_batch_id.strip()
    with get_connection(database_path) as connection:
        batch_row = connection.execute(
            """
            SELECT confirmation_batch_id, status, confirmed_at, created_at, updated_at
            FROM application_confirmations
            WHERE confirmation_batch_id = ?
            """,
            (normalized_batch_id,),
        ).fetchone()
        if batch_row is None:
            return None
        record_rows = connection.execute(
            """
            SELECT job_id, platform, status, submitted_at, failure_reason, platform_message, duplicate_detected
            FROM application_records
            WHERE confirmation_batch_id = ?
            ORDER BY created_at ASC
            """,
            (normalized_batch_id,),
        ).fetchall()
    return {
        "confirmation_batch_id": str(batch_row[0]),
        "status": str(batch_row[1]),
        "confirmed_at": _optional_text(batch_row[2]),
        "created_at": str(batch_row[3]),
        "updated_at": str(batch_row[4]),
        "records": [
            {
                "job_id": str(row[0]),
                "platform": str(row[1]),
                "status": str(row[2]),
                "submitted_at": _optional_text(row[3]),
                "failure_reason": _optional_text(row[4]),
                "platform_message": _optional_text(row[5]),
                "duplicate_detected": bool(row[6]),
            }
            for row in record_rows
        ],
    }


def clear_job_application_data(database_path: Path | str) -> None:
    with get_connection(database_path) as connection:
        with transaction(connection):
            connection.execute("DELETE FROM application_records")
            connection.execute("DELETE FROM job_application_filters")
            connection.execute("DELETE FROM job_application_evaluations")
            connection.execute("DELETE FROM collection_platform_progress")
            connection.execute("DELETE FROM application_confirmations")
            connection.execute("DELETE FROM collection_tasks")
            connection.execute("DELETE FROM job_applications")


def _build_duplicate_key(platform: str, company_name: str, title: str, location: str, detail_url: str) -> str:
    normalized_detail_url = detail_url.split("?", 1)[0].rstrip("/")
    return hashlib.sha256(
        f"{platform.lower()}\n{company_name.lower()}\n{title.lower()}\n{location.lower()}\n{normalized_detail_url.lower()}".encode("utf-8")
    ).hexdigest()


def _normalize_required_job_fields(**fields: str) -> dict[str, str]:
    normalized_fields = {key: value.strip() for key, value in fields.items()}
    if not all(normalized_fields.values()):
        raise ValueError("岗位字段不能为空")
    return normalized_fields


def _normalize_optional_job_fields(**fields: str | None) -> dict[str, str | None]:
    return {key: _optional_input(value) for key, value in fields.items()}


def _job_application_from_row(row: tuple[object, ...]) -> dict[str, str | None]:
    return {
        "job_id": str(row[0]),
        "platform": str(row[1]),
        "platform_job_id": str(row[2]),
        "job_url": str(row[3]),
        "company_name": str(row[4]),
        "title": str(row[5]),
        "location": str(row[6]),
        "employment_type": _optional_text(row[7]),
        "salary_range": _optional_text(row[8]),
        "posted_at": _optional_text(row[9]),
        "remote_policy": _optional_text(row[10]),
        "level": _optional_text(row[11]),
        "experience_requirement": _optional_text(row[12]),
        "education_requirement": _optional_text(row[13]),
        "industry": _optional_text(row[14]),
        "company_size": _optional_text(row[15]),
        "funding_stage": _optional_text(row[16]),
        "tech_stack": _optional_text(row[17]),
        "benefits": _optional_text(row[18]),
        "published_at": _optional_text(row[19]),
        "detail_url": str(row[20]),
        "jd_text": str(row[21]),
        "collected_at": str(row[22]),
        "field_confidence": str(row[23]),
        "normalized_payload": str(row[24]),
        "status": str(row[25]),
        "created_at": str(row[26]),
        "updated_at": str(row[27]),
    }


def _assert_no_sensitive_content(values: list[str | None]) -> None:
    assert_no_sensitive_payload(values, error_message="包含敏感字段，禁止落库")


def _optional_input(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
