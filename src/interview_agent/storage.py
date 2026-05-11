from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Iterator


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
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT status
            FROM knowledge_base_meta
            WHERE singleton_id = 1
            """
        ).fetchone()

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
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _current_timestamp() -> str:
    return datetime.now(UTC).isoformat()
