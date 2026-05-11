from __future__ import annotations

from pathlib import Path


INCLUDED_SUFFIXES = {".md", ".pdf", ".docx"}
EXCLUDED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".xlsx"}
EXCLUDED_DIRECTORY_NAMES = {"简历", "lyjs一起写文档"}
EXCLUDED_BASENAME_PREFIXES = {"离职证明"}


def iter_source_files(source_root: Path | str) -> list[Path]:
    root_path = Path(source_root)
    included_paths: list[Path] = []

    for file_path in root_path.rglob("*"):
        if not file_path.is_file():
            continue
        if should_include_file(root_path, file_path):
            included_paths.append(file_path)

    return included_paths


def should_include_file(source_root: Path | str, file_path: Path | str) -> bool:
    root_path = Path(source_root)
    candidate_path = Path(file_path)
    relative_parts = candidate_path.relative_to(root_path).parts
    lowercase_suffix = candidate_path.suffix.lower()

    if lowercase_suffix not in INCLUDED_SUFFIXES:
        return False
    if lowercase_suffix in EXCLUDED_SUFFIXES:
        return False
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_parts[:-1]):
        return False
    if any(candidate_path.name.startswith(prefix) for prefix in EXCLUDED_BASENAME_PREFIXES):
        return False

    return True
