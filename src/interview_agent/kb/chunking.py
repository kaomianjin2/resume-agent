from __future__ import annotations

from hashlib import sha256


def content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def chunk_text(content: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized_content = content.strip()
    if not normalized_content:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须满足 0 <= overlap < chunk_size")

    chunks: list[str] = []
    start_index = 0
    content_length = len(normalized_content)
    step_size = chunk_size - chunk_overlap

    while start_index < content_length:
        chunk = normalized_content[start_index : start_index + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start_index += step_size

    return chunks
