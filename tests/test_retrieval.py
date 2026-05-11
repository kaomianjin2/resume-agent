from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from interview_agent.config import EmbeddingConfig
from interview_agent.kb.build import build_knowledge_base
from interview_agent.kb.embedding import FakeEmbedder, build_embedder
from interview_agent.kb.retrieval import (
    get_chunk_embedding,
    hybrid_search,
    index_chunks,
    keyword_search,
    vector_search,
)
from interview_agent.storage import get_connection, initialize_database


def test_fake_embedder_returns_deterministic_vectors_without_model_download() -> None:
    embedder = FakeEmbedder(vocabulary=("python", "api", "java"))

    first_vectors = embedder.embed_texts(["python api", "java"])
    second_vectors = embedder.embed_texts(["python api", "java"])

    assert first_vectors == second_vectors
    assert first_vectors == [[1.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def test_local_bge_embedder_raises_clear_error_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "models" / "bge-m3"
    model_path.mkdir(parents=True)

    def fake_import_module(module_name: str):
        if module_name == "sentence_transformers":
            raise ModuleNotFoundError("No module named 'sentence_transformers'")
        raise AssertionError(f"unexpected module import: {module_name}")

    monkeypatch.setattr("interview_agent.kb.embedding.import_module", fake_import_module)
    embedder = build_embedder(
        EmbeddingConfig(
            provider="local",
            model_name="BAAI/bge-m3",
            model_path=str(model_path),
        )
    )

    with pytest.raises(RuntimeError) as exc_info:
        embedder.embed_texts(["python"])

    assert str(model_path) in str(exc_info.value)
    assert "sentence_transformers" in str(exc_info.value)


def test_keyword_search_returns_matching_chunk_from_fts(tmp_path: Path) -> None:
    database_path = tmp_path / "knowledge.sqlite3"
    initialize_database(database_path)

    with get_connection(database_path) as connection:
        insert_chunk(
            connection,
            document_id="doc-1",
            chunk_id="chunk-1",
            source_path="notes/backend.md",
            content="Python orchestrator handles retry planning.",
        )
        insert_chunk(
            connection,
            document_id="doc-2",
            chunk_id="chunk-2",
            source_path="notes/frontend.md",
            content="CSS layout notes only.",
        )

        index_chunks(
            connection,
            embedder=FakeEmbedder(vocabulary=("python", "orchestrator", "css")),
            chunk_ids=["chunk-1", "chunk-2"],
        )

        matches = keyword_search(connection, query="orchestrator", limit=2)

    assert [match["chunk_id"] for match in matches] == ["chunk-1"]
    assert matches[0]["source_path"] == "notes/backend.md"


def test_chunk_embedding_can_be_written_and_loaded(tmp_path: Path) -> None:
    database_path = tmp_path / "knowledge.sqlite3"
    initialize_database(database_path)

    with get_connection(database_path) as connection:
        insert_chunk(
            connection,
            document_id="doc-1",
            chunk_id="chunk-1",
            source_path="notes/backend.md",
            content="Python api design system",
        )
        embedder = FakeEmbedder(vocabulary=("python", "api", "design"))

        index_chunks(connection, embedder=embedder, chunk_ids=["chunk-1"])

        stored_vector = get_chunk_embedding(connection, "chunk-1")

    assert stored_vector == embedder.embed_texts(["Python api design system"])[0]


def test_vector_search_returns_stable_order_for_fake_embeddings(tmp_path: Path) -> None:
    database_path = tmp_path / "knowledge.sqlite3"
    initialize_database(database_path)

    with get_connection(database_path) as connection:
        insert_chunk(
            connection,
            document_id="doc-1",
            chunk_id="chunk-1",
            source_path="notes/python-api.md",
            content="python api patterns",
        )
        insert_chunk(
            connection,
            document_id="doc-2",
            chunk_id="chunk-2",
            source_path="notes/python-core.md",
            content="python internals",
        )
        insert_chunk(
            connection,
            document_id="doc-3",
            chunk_id="chunk-3",
            source_path="notes/java.md",
            content="java spring service",
        )
        embedder = FakeEmbedder(vocabulary=("python", "api", "internals", "java", "spring"))

        index_chunks(connection, embedder=embedder, chunk_ids=["chunk-1", "chunk-2", "chunk-3"])

        matches = vector_search(
            connection,
            query="python api",
            embedder=embedder,
            limit=3,
        )

    assert [match["chunk_id"] for match in matches] == ["chunk-1", "chunk-2", "chunk-3"]


def test_hybrid_search_returns_required_fields_with_ranked_results(tmp_path: Path) -> None:
    database_path = tmp_path / "knowledge.sqlite3"
    initialize_database(database_path)

    with get_connection(database_path) as connection:
        insert_chunk(
            connection,
            document_id="doc-1",
            chunk_id="chunk-1",
            source_path="notes/python-api.md",
            content="python api retry strategy",
        )
        insert_chunk(
            connection,
            document_id="doc-2",
            chunk_id="chunk-2",
            source_path="notes/retry.md",
            content="retry checklist for interviews",
        )
        insert_chunk(
            connection,
            document_id="doc-3",
            chunk_id="chunk-3",
            source_path="notes/java.md",
            content="java service layer",
        )
        embedder = FakeEmbedder(vocabulary=("python", "api", "retry", "java", "service"))

        index_chunks(connection, embedder=embedder, chunk_ids=["chunk-1", "chunk-2", "chunk-3"])

        matches = hybrid_search(
            connection,
            query="python retry",
            embedder=embedder,
            limit=3,
        )

    assert [match["chunk_id"] for match in matches] == ["chunk-1", "chunk-2", "chunk-3"]
    assert matches[0]["content"] == "python api retry strategy"
    assert matches[0]["source_path"] == "notes/python-api.md"
    assert isinstance(matches[0]["score"], float)


def test_build_knowledge_base_populates_retrieval_indexes_with_fake_embedder(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path)
    markdown_path = source_dir / "notes.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("python retry patterns for agent planning", encoding="utf-8")

    build_knowledge_base(
        source=source_dir,
        config_path=config_path,
        database_path=database_path,
        embedder=FakeEmbedder(vocabulary=("python", "retry", "planning")),
    )

    with sqlite3.connect(database_path) as connection:
        embedding_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_chunk_embeddings"
        ).fetchone()
        matches = keyword_search(connection, query="planning", limit=2)

    assert embedding_count == (1,)
    assert [match["chunk_id"] for match in matches] == [matches[0]["chunk_id"]]
    assert matches[0]["source_path"] == "notes.md"


def insert_chunk(
    connection: sqlite3.Connection,
    document_id: str,
    chunk_id: str,
    source_path: str,
    content: str,
) -> None:
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
        """,
        (document_id, source_path, f"hash-{document_id}", "ready", "2026-05-11T00:00:00", "2026-05-11T00:00:00"),
    )
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
        (chunk_id, document_id, 0, content, "2026-05-11T00:00:00"),
    )


def write_config(tmp_path: Path, source_dir: Path, database_path: Path) -> Path:
    config_path = tmp_path / "interview-agent.toml"
    config_path.write_text(
        "\n".join(
            [
                "[llm]",
                'base_url = "https://example.test/v1"',
                'api_key = "test-key"',
                'model = "fake-model"',
                "",
                "[embedding]",
                'provider = "local"',
                'model_name = "BAAI/bge-m3"',
                'model_path = "./models/bge-m3"',
                "",
                "[storage]",
                f'database_path = "{database_path.as_posix()}"',
                "",
                "[knowledge_base]",
                f'source = "{source_dir.as_posix()}"',
                "chunk_size = 128",
                "chunk_overlap = 16",
                "top_k = 8",
                'index_version = "v1"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path
