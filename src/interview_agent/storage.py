from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4


DEFAULT_KNOWLEDGE_BASE_STATUS = "not_ready"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


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
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT user_id, username, password_hash, role, status
            FROM users
            WHERE username = ?
            """,
            (username.strip(),),
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
