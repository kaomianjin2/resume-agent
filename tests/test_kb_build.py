from __future__ import annotations

from pathlib import Path
import sqlite3
import subprocess
import sys
import zlib
import zipfile

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

    result = run_build_module(source_dir, config_path, database_path)

    assert result.returncode == 0, result.stderr
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

    first_result = run_build_module(source_dir, config_path, database_path)
    second_result = run_build_module(source_dir, config_path, database_path)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr

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


def test_build_knowledge_base_records_failed_status_and_preserves_previous_ready_result(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "knowledge.sqlite3"
    config_path = write_config(tmp_path, source_dir, database_path, chunk_size=128, chunk_overlap=16)
    markdown_path = source_dir / "notes.md"
    pdf_path = source_dir / "broken.pdf"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("stable ready content", encoding="utf-8")

    first_result = run_build_module(source_dir, config_path, database_path)
    assert first_result.returncode == 0, first_result.stderr
    assert get_knowledge_base_status(database_path) == "ready"

    write_pdf_fixture(pdf_path, "broken content", compressed=True, truncate_stream=True)

    second_result = run_build_module(source_dir, config_path, database_path)

    assert second_result.returncode != 0
    assert get_knowledge_base_status(database_path) == "failed"

    with sqlite3.connect(database_path) as connection:
        meta_row = connection.execute(
            """
            SELECT status
            FROM knowledge_base_meta
            WHERE singleton_id = 1
            """
        ).fetchone()
        documents = connection.execute(
            """
            SELECT source_path, status
            FROM knowledge_documents
            ORDER BY source_path
            """
        ).fetchall()

    assert meta_row == ("failed",)
    assert documents == [("notes.md", "ready")]


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

    result = run_build_module(source_dir, config_path, database_path)

    assert result.returncode == 0, result.stderr

    with sqlite3.connect(database_path) as connection:
        chunk_row = connection.execute(
            """
            SELECT content
            FROM knowledge_chunks
            """
        ).fetchone()

    assert chunk_row is not None
    assert "Alpha Beta Gamma" in chunk_row[0]


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


def write_pdf_fixture(
    path: Path,
    text: str | list[str],
    *,
    compressed: bool = False,
    use_tj_array: bool = False,
    truncate_stream: bool = False,
) -> None:
    pdf_operation = build_pdf_text_operation(text, use_tj_array=use_tj_array)
    stream_bytes = f"BT {pdf_operation} ET".encode("latin-1")
    stream_dictionary = f"<< /Length {len(stream_bytes)}"
    if compressed:
        stream_bytes = zlib.compress(stream_bytes)
        if truncate_stream:
            stream_bytes = stream_bytes[:-4]
        stream_dictionary = f"<< /Length {len(stream_bytes)} /Filter /FlateDecode"
    stream_dictionary += " >>"

    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R >> endobj\n"
        + f"4 0 obj {stream_dictionary} stream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream endobj\nxref\n0 5\n0000000000 65535 f \n"
        + b"trailer << /Root 1 0 R /Size 5 >>\nstartxref\n0\n%%EOF\n"
    )
    path.write_bytes(pdf_bytes)


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
