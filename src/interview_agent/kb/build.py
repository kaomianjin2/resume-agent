from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from interview_agent.config import load_config
from interview_agent.storage import (
    get_connection,
    initialize_database,
    set_knowledge_base_status,
    transaction,
)

from .chunking import chunk_text, content_hash
from .file_policy import iter_source_files
from .parser import extract_text


def build_knowledge_base(
    *,
    source: Path | str,
    config_path: Path | str,
    database_path: Path | str,
) -> None:
    config = load_config(config_path)
    source_root = Path(source)
    resolved_database_path = Path(database_path)
    initialize_database(resolved_database_path)
    set_knowledge_base_status(resolved_database_path, "building")

    try:
        with get_connection(resolved_database_path) as connection:
            with transaction(connection):
                for file_path in iter_source_files(source_root):
                    _upsert_document(
                        connection=connection,
                        source_root=source_root,
                        file_path=file_path,
                        chunk_size=config.knowledge_base.chunk_size,
                        chunk_overlap=config.knowledge_base.chunk_overlap,
                    )
    except Exception:
        set_knowledge_base_status(resolved_database_path, "failed")
        raise

    set_knowledge_base_status(resolved_database_path, "ready")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m interview_agent.kb.build",
        description="Build offline knowledge documents into SQLite storage.",
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--db", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    build_knowledge_base(
        source=args.source,
        config_path=args.config,
        database_path=args.db,
    )
    return 0


def _upsert_document(
    *,
    connection,
    source_root: Path,
    file_path: Path,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    document_content = extract_text(file_path)
    document_hash = content_hash(document_content)
    relative_path = file_path.relative_to(source_root).as_posix()
    existing_row = connection.execute(
        """
        SELECT document_id, content_hash
        FROM knowledge_documents
        WHERE source_path = ?
        """,
        (relative_path,),
    ).fetchone()

    if existing_row is not None and str(existing_row[1]) == document_hash:
        return

    document_id = _document_id(relative_path)
    timestamp = _current_timestamp()
    chunks = chunk_text(document_content, chunk_size, chunk_overlap)

    connection.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))
    connection.execute(
        """
        INSERT INTO knowledge_documents (
            document_id,
            source_path,
            content_hash,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_id) DO UPDATE SET
            source_path = excluded.source_path,
            content_hash = excluded.content_hash,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (document_id, relative_path, document_hash, "ready", timestamp, timestamp),
    )

    for chunk_index, chunk_content in enumerate(chunks):
        connection.execute(
            """
            INSERT INTO knowledge_chunks (
                chunk_id,
                document_id,
                chunk_index,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (_chunk_id(document_id, chunk_index, chunk_content), document_id, chunk_index, chunk_content, timestamp),
        )


def _document_id(relative_path: str) -> str:
    return content_hash(relative_path)


def _chunk_id(document_id: str, chunk_index: int, chunk_content: str) -> str:
    return content_hash(f"{document_id}:{chunk_index}:{chunk_content}")


def _current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
