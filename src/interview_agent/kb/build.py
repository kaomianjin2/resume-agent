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
from .embedding import Embedder, build_embedder
from .file_policy import iter_source_files
from .parser import extract_text
from .retrieval import clear_document_retrieval_entries, index_chunks


CHUNK_INDEX_BATCH_SIZE = 64


def build_knowledge_base(
    *,
    source: Path | str,
    config_path: Path | str,
    database_path: Path | str,
    embedder: Embedder | None = None,
) -> None:
    config = load_config(config_path)
    resolved_embedder = _resolve_embedder(config.embedding, embedder)
    source_root = Path(source)
    resolved_database_path = Path(database_path)
    initialize_database(resolved_database_path)
    set_knowledge_base_status(resolved_database_path, "building")

    try:
        with get_connection(resolved_database_path) as connection:
            with transaction(connection):
                source_files = iter_source_files(source_root)
                current_source_paths = {
                    file_path.relative_to(source_root).as_posix() for file_path in source_files
                }
                _remove_stale_documents(connection, current_source_paths)
                for file_path in source_files:
                    _upsert_document(
                        connection=connection,
                        source_root=source_root,
                        file_path=file_path,
                        chunk_size=config.knowledge_base.chunk_size,
                        chunk_overlap=config.knowledge_base.chunk_overlap,
                        embedder=resolved_embedder,
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
    embedder: Embedder,
) -> None:
    relative_path = file_path.relative_to(source_root).as_posix()
    try:
        document_content = extract_text(file_path)
    except ValueError as error:
        document_content = _fallback_document_content(relative_path, error)
    if not document_content.strip():
        document_content = _fallback_document_content(relative_path, None)

    document_hash = content_hash(document_content)
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

    clear_document_retrieval_entries(connection, document_id=document_id)
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

    chunk_ids: list[str] = []
    for chunk_index, chunk_content in enumerate(chunks):
        chunk_id = _chunk_id(document_id, chunk_index, chunk_content)
        chunk_ids.append(chunk_id)
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
            (chunk_id, document_id, chunk_index, chunk_content, timestamp),
        )

    for chunk_id_batch in _batched(chunk_ids, CHUNK_INDEX_BATCH_SIZE):
        index_chunks(connection, embedder=embedder, chunk_ids=chunk_id_batch)


def _document_id(relative_path: str) -> str:
    return content_hash(relative_path)


def _remove_stale_documents(connection, current_source_paths: set[str]) -> None:
    rows = connection.execute(
        """
        SELECT document_id, source_path
        FROM knowledge_documents
        """
    ).fetchall()
    for row in rows:
        document_id = str(row[0])
        source_path = str(row[1])
        if source_path in current_source_paths:
            continue
        clear_document_retrieval_entries(connection, document_id=document_id)
        connection.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM knowledge_documents WHERE document_id = ?", (document_id,))


def _chunk_id(document_id: str, chunk_index: int, chunk_content: str) -> str:
    return content_hash(f"{document_id}:{chunk_index}:{chunk_content}")


def _current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _fallback_document_content(relative_path: str, error: ValueError | None) -> str:
    lines = [
        f"文件路径: {relative_path}",
        f"文件名: {Path(relative_path).name}",
        "正文抽取状态: 未能从原文件抽取正文，已保留文件索引用于检索定位。",
    ]
    if error is not None:
        lines.append(f"抽取失败原因: {error}")
    return "\n".join(lines)


def _batched(items: list[str], batch_size: int) -> list[list[str]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _resolve_embedder(
    embedding_config,
    embedder: Embedder | None,
) -> Embedder:
    if embedder is not None:
        return embedder

    return build_embedder(embedding_config)


if __name__ == "__main__":
    raise SystemExit(main())
