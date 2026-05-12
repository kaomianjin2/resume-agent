from __future__ import annotations

from pathlib import Path

from interview_agent.kb.file_policy import iter_source_files


def test_iter_source_files_includes_only_supported_documents_and_excludes_sensitive_paths(
    tmp_path: Path,
) -> None:
    included_markdown = tmp_path / "notes" / "system-design.md"
    included_pdf = tmp_path / "books" / "distributed-systems.pdf"
    included_docx = tmp_path / "archive" / "interview.docx"
    excluded_resume = tmp_path / "简历" / "candidate.md"
    excluded_offboarding = tmp_path / "docs" / "离职证明.pdf"
    excluded_process_dir = tmp_path / "lyjs一起写文档" / "process.md"
    excluded_java_pdf = tmp_path / "books" / "JVM tuning.pdf"
    excluded_java_markdown = tmp_path / "notes" / "spring boot.md"
    excluded_png = tmp_path / "images" / "cover.png"
    excluded_excel = tmp_path / "sheets" / "matrix.xlsx"

    for file_path in [
        included_markdown,
        included_pdf,
        included_docx,
        excluded_resume,
        excluded_offboarding,
        excluded_process_dir,
        excluded_java_pdf,
        excluded_java_markdown,
        excluded_png,
        excluded_excel,
    ]:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("fixture", encoding="utf-8")

    result = sorted(path.relative_to(tmp_path).as_posix() for path in iter_source_files(tmp_path))

    assert result == [
        "archive/interview.docx",
        "books/distributed-systems.pdf",
        "notes/system-design.md",
    ]
