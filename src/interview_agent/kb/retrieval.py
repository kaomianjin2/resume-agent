from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
import sqlite3

from interview_agent.config import EmbeddingConfig
from interview_agent.storage import get_connection

from .embedding import Embedder, build_embedder


class SQLiteHybridRetriever:
    def __init__(
        self,
        database_path: Path | str,
        embedding_config: EmbeddingConfig,
    ) -> None:
        self.database_path = Path(database_path)
        self.embedding_config = embedding_config
        self._embedder: Embedder | None = None

    def search(self, query: str, limit: int) -> list[dict[str, str | float]]:
        with get_connection(self.database_path) as connection:
            return hybrid_search(
                connection,
                query=query,
                embedder=self._get_embedder(),
                limit=limit,
            )

    def _get_embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = build_embedder(self.embedding_config)
        return self._embedder


def ensure_retrieval_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunk_embeddings (
            chunk_id TEXT PRIMARY KEY,
            embedding_json TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (chunk_id) REFERENCES knowledge_chunks(chunk_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
            chunk_id UNINDEXED,
            source_path UNINDEXED,
            content
        )
        """
    )


def index_chunks(
    connection: sqlite3.Connection,
    *,
    embedder: Embedder,
    chunk_ids: list[str],
) -> None:
    if not chunk_ids:
        return

    ensure_retrieval_schema(connection)
    placeholders = ", ".join("?" for _ in chunk_ids)
    rows = connection.execute(
        f"""
        SELECT kc.chunk_id, kd.source_path, kc.content
        FROM knowledge_chunks AS kc
        JOIN knowledge_documents AS kd ON kd.document_id = kc.document_id
        WHERE kc.chunk_id IN ({placeholders})
        ORDER BY kc.chunk_id
        """,
        chunk_ids,
    ).fetchall()
    if not rows:
        return

    vectors = embedder.embed_texts([str(row[2]) for row in rows])
    for row, vector in zip(rows, vectors, strict=True):
        chunk_id = str(row[0])
        source_path = str(row[1])
        content = str(row[2])
        connection.execute("DELETE FROM knowledge_chunks_fts WHERE chunk_id = ?", (chunk_id,))
        connection.execute(
            """
            INSERT INTO knowledge_chunks_fts (chunk_id, source_path, content)
            VALUES (?, ?, ?)
            """,
            (chunk_id, source_path, content),
        )
        connection.execute(
            """
            INSERT INTO knowledge_chunk_embeddings (chunk_id, embedding_json, dimension, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chunk_id) DO UPDATE SET
                embedding_json = excluded.embedding_json,
                dimension = excluded.dimension,
                updated_at = excluded.updated_at
            """,
            (chunk_id, json.dumps(vector, separators=(",", ":")), len(vector)),
        )


def get_chunk_embedding(connection: sqlite3.Connection, chunk_id: str) -> list[float] | None:
    ensure_retrieval_schema(connection)
    row = connection.execute(
        """
        SELECT embedding_json
        FROM knowledge_chunk_embeddings
        WHERE chunk_id = ?
        """,
        (chunk_id,),
    ).fetchone()
    if row is None:
        return None

    return [float(value) for value in json.loads(str(row[0]))]


def clear_document_retrieval_entries(connection: sqlite3.Connection, *, document_id: str) -> None:
    ensure_retrieval_schema(connection)
    chunk_rows = connection.execute(
        """
        SELECT chunk_id
        FROM knowledge_chunks
        WHERE document_id = ?
        """,
        (document_id,),
    ).fetchall()
    if not chunk_rows:
        return

    chunk_ids = [str(row[0]) for row in chunk_rows]
    placeholders = ", ".join("?" for _ in chunk_ids)
    connection.execute(
        f"DELETE FROM knowledge_chunk_embeddings WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    )
    connection.execute(
        f"DELETE FROM knowledge_chunks_fts WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    )


def keyword_search(
    connection: sqlite3.Connection,
    *,
    query: str,
    limit: int,
) -> list[dict[str, str | float]]:
    ensure_retrieval_schema(connection)
    normalized_query = _build_fts_query(query)
    if not normalized_query:
        return []

    rows = connection.execute(
        """
        SELECT chunk_id, source_path, content
        FROM knowledge_chunks_fts
        WHERE knowledge_chunks_fts MATCH ?
        ORDER BY bm25(knowledge_chunks_fts), chunk_id
        LIMIT ?
        """,
        (normalized_query, limit),
    ).fetchall()
    return _rows_to_ranked_results(rows)


def vector_search(
    connection: sqlite3.Connection,
    *,
    query: str,
    embedder: Embedder,
    limit: int,
) -> list[dict[str, str | float]]:
    ensure_retrieval_schema(connection)
    query_vectors = embedder.embed_texts([query])
    if not query_vectors:
        return []

    query_vector = query_vectors[0]
    rows = connection.execute(
        """
        SELECT kce.chunk_id, kd.source_path, kc.content, kce.embedding_json
        FROM knowledge_chunk_embeddings AS kce
        JOIN knowledge_chunks AS kc ON kc.chunk_id = kce.chunk_id
        JOIN knowledge_documents AS kd ON kd.document_id = kc.document_id
        """
    ).fetchall()
    scored_rows = []
    for row in rows:
        embedding = [float(value) for value in json.loads(str(row[3]))]
        scored_rows.append(
            {
                "chunk_id": str(row[0]),
                "source_path": str(row[1]),
                "content": str(row[2]),
                "score": _cosine_similarity(query_vector, embedding),
            }
        )

    scored_rows.sort(key=lambda item: (-float(item["score"]), str(item["chunk_id"])))
    return scored_rows[:limit]


def hybrid_search(
    connection: sqlite3.Connection,
    *,
    query: str,
    embedder: Embedder,
    limit: int,
) -> list[dict[str, str | float]]:
    keyword_matches = keyword_search(connection, query=query, limit=limit)
    vector_matches = vector_search(connection, query=query, embedder=embedder, limit=limit)

    combined: dict[str, dict[str, str | float]] = {}
    for rank, match in enumerate(keyword_matches, start=1):
        _merge_rank_score(combined, match, 1.0 / rank)
    for rank, match in enumerate(vector_matches, start=1):
        _merge_rank_score(combined, match, 1.0 / rank)

    results = list(combined.values())
    results.sort(key=lambda item: (-float(item["score"]), str(item["chunk_id"])))
    return results[:limit]


def _build_fts_query(query: str) -> str:
    tokens = [token.strip() for token in query.split() if token.strip()]
    escaped_tokens = [token.replace('"', '""') for token in tokens]
    return " AND ".join(f'"{token}"' for token in escaped_tokens)


def _rows_to_ranked_results(rows: list[tuple[object, ...]]) -> list[dict[str, str | float]]:
    results = []
    for rank, row in enumerate(rows, start=1):
        results.append(
            {
                "chunk_id": str(row[0]),
                "source_path": str(row[1]),
                "content": str(row[2]),
                "score": 1.0 / rank,
            }
        )
    return results


def _merge_rank_score(
    combined: dict[str, dict[str, str | float]],
    match: dict[str, str | float],
    score_increment: float,
) -> None:
    chunk_id = str(match["chunk_id"])
    existing = combined.get(chunk_id)
    if existing is None:
        combined[chunk_id] = {
            "chunk_id": chunk_id,
            "source_path": str(match["source_path"]),
            "content": str(match["content"]),
            "score": float(score_increment),
        }
        return

    existing["score"] = float(existing["score"]) + score_increment


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding 维度不一致")

    numerator = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_magnitude = sqrt(sum(value * value for value in left))
    right_magnitude = sqrt(sum(value * value for value in right))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0

    return numerator / (left_magnitude * right_magnitude)
