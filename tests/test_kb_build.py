from __future__ import annotations

from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import zlib
import zipfile

from interview_agent.kb import build as kb_build
from interview_agent.kb.build import build_knowledge_base
from interview_agent.kb.embedding import FakeEmbedder
from interview_agent.kb.parser import MAX_PDF_BYTES, _extract_text_segments_from_pdf_stream
from interview_agent.storage import get_knowledge_base_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_knowledge_base_parses_supported_documents_and_marks_ready(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)

    markdown_path = source_dir / "notes.md"
    pdf_path = source_dir / "handbook.pdf"
    docx_path = source_dir / "guide.docx"
    ignored_resume = source_dir / "简历" / "resume.md"

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# Heading\nalpha beta gamma", encoding="utf-8")
    write_pdf_fixture(pdf_path, "PDF interview knowledge", compressed=True)
    write_docx_fixture(docx_path, "DOCX project history")
    ignored_resume.parent.mkdir(parents=True, exist_ok=True)
    ignored_resume.write_text("do not index", encoding="utf-8")

    build_with_fake_embedder(source_dir, config_path, database_path)

    assert get_knowledge_base_status(database_path) == "ready"

    with sqlite3.connect(database_path) as connection:
        documents = connection.execute(
            """
            SELECT source_path, content_hash, status
            FROM knowledge_documents
            ORDER BY source_path
            """
        ).fetchall()
        chunks = connection.execute(
            """
            SELECT document_id, chunk_index, content
            FROM knowledge_chunks
            ORDER BY document_id, chunk_index
            """
        ).fetchall()

    assert [row[0] for row in documents] == [
        "guide.docx",
        "handbook.pdf",
        "notes.md",
    ]
    assert all(row[1] for row in documents)
    assert {row[2] for row in documents} == {"ready"}
    chunk_texts = [row[2] for row in chunks]
    assert any("alpha beta gamma" in chunk_text for chunk_text in chunk_texts)
    assert any("PDF interview knowledge" in chunk_text for chunk_text in chunk_texts)
    assert any("DOCX project history" in chunk_text for chunk_text in chunk_texts)


def test_build_knowledge_base_skips_reinserting_chunks_when_document_is_unchanged(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=12, chunk_overlap=4)
    markdown_path = source_dir / "notes.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("abcdefghij klmnopqrst uvwxyz", encoding="utf-8")

    build_with_fake_embedder(source_dir, config_path, database_path)
    build_with_fake_embedder(source_dir, config_path, database_path)

    with sqlite3.connect(database_path) as connection:
        document_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_documents"
        ).fetchone()
        chunk_count = connection.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()
        distinct_chunk_count = connection.execute(
            "SELECT COUNT(DISTINCT chunk_id) FROM knowledge_chunks"
        ).fetchone()

    assert document_count is not None
    assert chunk_count is not None
    assert distinct_chunk_count is not None
    assert document_count[0] == 1
    assert chunk_count[0] > 1
    assert chunk_count[0] == distinct_chunk_count[0]


def test_build_knowledge_base_indexes_chunks_in_bounded_batches(tmp_path: Path) -> None:
    previous_batch_size = kb_build.CHUNK_INDEX_BATCH_SIZE
    kb_build.CHUNK_INDEX_BATCH_SIZE = 3
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=4, chunk_overlap=0)
    markdown_path = source_dir / "notes.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("abcdefghijklmnopqrst", encoding="utf-8")
    embedder = RecordingEmbedder()

    try:
        build_knowledge_base(
            source=source_dir,
            config_path=config_path,
            database_path=database_path,
            embedder=embedder,
        )
    finally:
        kb_build.CHUNK_INDEX_BATCH_SIZE = previous_batch_size

    assert embedder.batch_sizes == [3, 2]


def test_build_knowledge_base_removes_documents_excluded_by_current_policy(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    java_path = source_dir / "java guide.md"
    notes_path = source_dir / "notes.md"
    java_path.parent.mkdir(parents=True, exist_ok=True)
    java_path.write_text("old java content", encoding="utf-8")
    notes_path.write_text("stable ready content", encoding="utf-8")

    with sqlite3.connect(database_path) as connection:
        connection.executescript((PROJECT_ROOT / "src/interview_agent/schema.sql").read_text())
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
            VALUES ('legacy-java', 'java guide.md', 'old-hash', 'ready', 'now', 'now')
            """
        )

    build_with_fake_embedder(source_dir, config_path, database_path)

    with sqlite3.connect(database_path) as connection:
        documents = connection.execute(
            """
            SELECT source_path
            FROM knowledge_documents
            ORDER BY source_path
            """
        ).fetchall()

    assert documents == [("notes.md",)]


def test_build_knowledge_base_indexes_unreadable_pdf_with_fallback_content(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    markdown_path = source_dir / "notes.md"
    pdf_path = source_dir / "broken.pdf"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("stable ready content", encoding="utf-8")

    build_with_fake_embedder(source_dir, config_path, database_path)
    assert get_knowledge_base_status(database_path) == "ready"

    write_pdf_fixture(pdf_path, "broken content", compressed=True, truncate_stream=True)

    build_with_fake_embedder(source_dir, config_path, database_path)

    assert get_knowledge_base_status(database_path) == "ready"

    with sqlite3.connect(database_path) as connection:
        documents = connection.execute(
            """
            SELECT source_path, status
            FROM knowledge_documents
            ORDER BY source_path
            """
        ).fetchall()
        broken_chunk = connection.execute(
            """
            SELECT kc.content
            FROM knowledge_chunks AS kc
            JOIN knowledge_documents AS kd ON kd.document_id = kc.document_id
            WHERE kd.source_path = 'broken.pdf'
            """
        ).fetchone()

    assert documents == [("broken.pdf", "ready"), ("notes.md", "ready")]
    assert broken_chunk is not None
    assert "broken.pdf" in broken_chunk[0]


def test_build_knowledge_base_skips_broken_pdf_stream_when_other_streams_have_text(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    pdf_path = source_dir / "partially-broken.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    write_pdf_fixture(pdf_path, "usable content", compressed=True)
    pdf_path.write_bytes(
        pdf_path.read_bytes()
        + build_pdf_stream("broken content", compressed=True, truncate_stream=True)
    )

    build_with_fake_embedder(source_dir, config_path, database_path)

    assert get_knowledge_base_status(database_path) == "ready"

    with sqlite3.connect(database_path) as connection:
        chunk_row = connection.execute("SELECT content FROM knowledge_chunks").fetchone()

    assert chunk_row is not None
    assert "usable content" in chunk_row[0]


def test_build_knowledge_base_indexes_unreadable_document_with_fallback_content(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    markdown_path = source_dir / "notes.md"
    unreadable_pdf_path = source_dir / "unreadable.pdf"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("stable ready content", encoding="utf-8")
    write_pdf_fixture(unreadable_pdf_path, "broken content", compressed=True, truncate_stream=True)

    build_with_fake_embedder(source_dir, config_path, database_path)

    assert get_knowledge_base_status(database_path) == "ready"

    with sqlite3.connect(database_path) as connection:
        documents = connection.execute(
            """
            SELECT source_path, status
            FROM knowledge_documents
            ORDER BY source_path
            """
        ).fetchall()

        unreadable_chunk = connection.execute(
            """
            SELECT kc.content
            FROM knowledge_chunks AS kc
            JOIN knowledge_documents AS kd ON kd.document_id = kc.document_id
            WHERE kd.source_path = 'unreadable.pdf'
            """
        ).fetchone()

    assert documents == [("notes.md", "ready"), ("unreadable.pdf", "ready")]
    assert unreadable_chunk is not None
    assert "unreadable.pdf" in unreadable_chunk[0]


def test_build_knowledge_base_indexes_large_pdf_with_fallback_content(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    markdown_path = source_dir / "notes.md"
    large_pdf_path = source_dir / "large.pdf"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("stable ready content", encoding="utf-8")
    large_pdf_path.write_bytes(b"0" * (MAX_PDF_BYTES + 1))

    build_with_fake_embedder(source_dir, config_path, database_path)

    assert get_knowledge_base_status(database_path) == "ready"

    with sqlite3.connect(database_path) as connection:
        documents = connection.execute(
            """
            SELECT source_path, status
            FROM knowledge_documents
            ORDER BY source_path
            """
        ).fetchall()

        large_chunk = connection.execute(
            """
            SELECT kc.content
            FROM knowledge_chunks AS kc
            JOIN knowledge_documents AS kd ON kd.document_id = kc.document_id
            WHERE kd.source_path = 'large.pdf'
            """
        ).fetchone()

    assert documents == [("large.pdf", "ready"), ("notes.md", "ready")]
    assert large_chunk is not None
    assert "large.pdf" in large_chunk[0]


def test_build_knowledge_base_extracts_text_from_flate_pdf_tj_arrays(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    pdf_path = source_dir / "array.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    write_pdf_fixture(
        pdf_path,
        ["Alpha", " ", "Beta", " ", "Gamma"],
        compressed=True,
        use_tj_array=True,
    )

    build_with_fake_embedder(source_dir, config_path, database_path)

    with sqlite3.connect(database_path) as connection:
        chunk_row = connection.execute(
            """
            SELECT content
            FROM knowledge_chunks
            """
        ).fetchone()

    assert chunk_row is not None
    assert "Alpha Beta Gamma" in chunk_row[0]


def test_pdf_text_segment_extraction_ignores_large_non_text_arrays_quickly() -> None:
    def raise_timeout(*_: object) -> None:
        raise TimeoutError("PDF stream scan timed out")

    previous_handler = signal.signal(signal.SIGALRM, raise_timeout)
    signal.alarm(1)
    try:
        start_time = time.perf_counter()
        segments = _extract_text_segments_from_pdf_stream(b"[" * 200_000 + b" ET")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)

    assert segments == []
    assert time.perf_counter() - start_time < 1


def test_pdf_text_segment_extraction_skips_unclosed_non_text_literals() -> None:
    segments = _extract_text_segments_from_pdf_stream(b"BT q (unclosed graphics data\n(Useful text) Tj ET")

    assert segments == ["Useful text"]


def test_pdf_text_segment_extraction_skips_arrays_with_unclosed_literals() -> None:
    segments = _extract_text_segments_from_pdf_stream(b"BT q [(unclosed graphics data]\n(Useful text) Tj ET")

    assert segments == ["Useful text"]


def test_pdf_text_segment_extraction_only_scans_text_objects() -> None:
    segments = _extract_text_segments_from_pdf_stream(
        b"q (ignored graphics data) Tj Q\nBT (Useful text) Tj ET"
    )

    assert segments == ["Useful text"]


def test_build_module_help_does_not_emit_runtime_warning() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "interview_agent.kb.build", "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0
    assert "RuntimeWarning" not in result.stderr


def write_config(
    tmp_path: Path,
    source_dir: Path,
    database_path: Path,
    *,
    chunk_size: int = 16,
    chunk_overlap: int = 4,
) -> Path:
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
                'model_name = "unused"',
                'model_path = "./unused"',
                "",
                "[storage]",
                f'database_path = "{database_path.as_posix()}"',
                "",
                "[knowledge_base]",
                f'source = "{source_dir.as_posix()}"',
                f"chunk_size = {chunk_size}",
                f"chunk_overlap = {chunk_overlap}",
                "top_k = 8",
                'index_version = "v1"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def run_build_module(
    source_dir: Path,
    config_path: Path,
    database_path: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "interview_agent.kb.build",
            "--source",
            str(source_dir),
            "--config",
            str(config_path),
            "--db",
            str(database_path),
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )


def build_with_fake_embedder(
    source_dir: Path,
    config_path: Path,
    database_path: Path,
) -> None:
    build_knowledge_base(
        source=source_dir,
        config_path=config_path,
        database_path=database_path,
        embedder=FakeEmbedder(vocabulary=()),
    )


class RecordingEmbedder:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return [[] for _ in texts]


def write_pdf_fixture(
    path: Path,
    text: str | list[str],
    *,
    compressed: bool = False,
    use_tj_array: bool = False,
    truncate_stream: bool = False,
) -> None:
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R >> endobj\n"
        + b"4 0 obj "
        + build_pdf_stream(
            text,
            compressed=compressed,
            use_tj_array=use_tj_array,
            truncate_stream=truncate_stream,
        )
        + b" endobj\nxref\n0 5\n0000000000 65535 f \n"
        + b"trailer << /Root 1 0 R /Size 5 >>\nstartxref\n0\n%%EOF\n"
    )
    path.write_bytes(pdf_bytes)


def build_pdf_stream(
    text: str | list[str],
    *,
    compressed: bool,
    use_tj_array: bool = False,
    truncate_stream: bool = False,
) -> bytes:
    pdf_operation = build_pdf_text_operation(text, use_tj_array=use_tj_array)
    stream_bytes = f"BT {pdf_operation} ET".encode("latin-1")
    stream_dictionary = f"<< /Length {len(stream_bytes)}"
    if compressed:
        stream_bytes = zlib.compress(stream_bytes)
        if truncate_stream:
            stream_bytes = stream_bytes[:-4]
        stream_dictionary = f"<< /Length {len(stream_bytes)} /Filter /FlateDecode"
    stream_dictionary += " >>"
    return f"{stream_dictionary} stream\n".encode("latin-1") + stream_bytes + b"\nendstream"


def build_pdf_text_operation(text: str | list[str], *, use_tj_array: bool) -> str:
    if not use_tj_array:
        assert isinstance(text, str)
        return f"({escape_pdf_text(text)}) Tj"

    assert isinstance(text, list)
    encoded_items = " ".join(f"({escape_pdf_text(item)})" for item in text)
    return f"[{encoded_items}] TJ"


def escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_docx_fixture(path: Path, text: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>
""",
        )
