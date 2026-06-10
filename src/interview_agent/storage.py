from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4


DEFAULT_KNOWLEDGE_BASE_STATUS = "not_ready"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
JOB_APPLICATION_STATUSES = {"pending_review", "approved", "submitted", "failed", "skipped", "duplicate"}


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
    external_job_id: str,
    job_url: str,
    company_name: str,
    title: str,
    location: str,
    employment_type: str | None,
    salary_range: str | None,
    posted_at: str | None,
    normalized_payload: str,
) -> dict[str, str | bool | None]:
    normalized_platform = platform.strip()
    normalized_external_job_id = external_job_id.strip()
    normalized_job_url = job_url.strip()
    normalized_company_name = company_name.strip()
    normalized_title = title.strip()
    normalized_location = location.strip()
    normalized_payload = normalized_payload.strip()
    if not all(
        [
            normalized_platform,
            normalized_external_job_id,
            normalized_job_url,
            normalized_company_name,
            normalized_title,
            normalized_location,
            normalized_payload,
        ]
    ):
        raise ValueError("岗位字段不能为空")

    duplicate_key = _build_duplicate_key(normalized_platform, normalized_external_job_id, normalized_job_url)
    with get_connection(database_path) as connection:
        existing_row = connection.execute(
            """
            SELECT job_id, platform, external_job_id, job_url, company_name, title, location,
                   employment_type, salary_range, posted_at, normalized_payload, status, created_at, updated_at
            FROM job_applications
            WHERE duplicate_key = ?
            """,
            (duplicate_key,),
        ).fetchone()
        if existing_row is not None:
            return {
                "job_id": str(existing_row[0]),
                "platform": str(existing_row[1]),
                "external_job_id": str(existing_row[2]),
                "job_url": str(existing_row[3]),
                "company_name": str(existing_row[4]),
                "title": str(existing_row[5]),
                "location": str(existing_row[6]),
                "employment_type": _optional_text(existing_row[7]),
                "salary_range": _optional_text(existing_row[8]),
                "posted_at": _optional_text(existing_row[9]),
                "normalized_payload": str(existing_row[10]),
                "status": str(existing_row[11]),
                "created_at": str(existing_row[12]),
                "updated_at": str(existing_row[13]),
                "is_duplicate": True,
            }

        timestamp = _current_timestamp()
        job_id = f"job-{uuid4()}"
        connection.execute(
            """
            INSERT INTO job_applications (
                job_id, platform, external_job_id, job_url, company_name, title, location,
                employment_type, salary_range, posted_at, normalized_payload, status,
                duplicate_key, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?)
            """,
            (
                job_id,
                normalized_platform,
                normalized_external_job_id,
                normalized_job_url,
                normalized_company_name,
                normalized_title,
                normalized_location,
                _optional_input(employment_type),
                _optional_input(salary_range),
                _optional_input(posted_at),
                normalized_payload,
                duplicate_key,
                timestamp,
                timestamp,
            ),
        )
    return {
        "job_id": job_id,
        "platform": normalized_platform,
        "external_job_id": normalized_external_job_id,
        "job_url": normalized_job_url,
        "company_name": normalized_company_name,
        "title": normalized_title,
        "location": normalized_location,
        "employment_type": _optional_input(employment_type),
        "salary_range": _optional_input(salary_range),
        "posted_at": _optional_input(posted_at),
        "normalized_payload": normalized_payload,
        "status": "pending_review",
        "created_at": timestamp,
        "updated_at": timestamp,
        "is_duplicate": False,
    }


def list_job_applications(database_path: Path | str) -> list[dict[str, str | None]]:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT job_id, platform, external_job_id, job_url, company_name, title, location,
                   employment_type, salary_range, posted_at, normalized_payload, status, created_at, updated_at
            FROM job_applications
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [
        {
            "job_id": str(row[0]),
            "platform": str(row[1]),
            "external_job_id": str(row[2]),
            "job_url": str(row[3]),
            "company_name": str(row[4]),
            "title": str(row[5]),
            "location": str(row[6]),
            "employment_type": _optional_text(row[7]),
            "salary_range": _optional_text(row[8]),
            "posted_at": _optional_text(row[9]),
            "normalized_payload": str(row[10]),
            "status": str(row[11]),
            "created_at": str(row[12]),
            "updated_at": str(row[13]),
        }
        for row in rows
    ]


def update_job_application_status(
    database_path: Path | str,
    *,
    job_id: str,
    status: str,
    confirmation_batch_id: str,
    submitted_at: str | None = None,
    failure_reason: str | None = None,
    platform_message: str | None = None,
    duplicate_detected: bool = False,
) -> dict[str, str | bool | None]:
    normalized_status = status.strip()
    if normalized_status not in JOB_APPLICATION_STATUSES:
        raise ValueError("投递状态不合法")
    normalized_job_id = job_id.strip()
    normalized_batch_id = confirmation_batch_id.strip()
    if not normalized_job_id or not normalized_batch_id:
        raise ValueError("岗位和确认批次不能为空")

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
            (normalized_batch_id, normalized_status, submitted_at, timestamp, timestamp),
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


def clear_job_application_data(database_path: Path | str) -> None:
    with get_connection(database_path) as connection:
        with transaction(connection):
            connection.execute("DELETE FROM application_records")
            connection.execute("DELETE FROM job_application_evaluations")
            connection.execute("DELETE FROM collection_platform_progress")
            connection.execute("DELETE FROM application_confirmations")
            connection.execute("DELETE FROM collection_tasks")
            connection.execute("DELETE FROM job_applications")


def _build_duplicate_key(platform: str, external_job_id: str, job_url: str) -> str:
    return hashlib.sha256(f"{platform}\n{external_job_id}\n{job_url}".encode("utf-8")).hexdigest()


def _optional_input(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
