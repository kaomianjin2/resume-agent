from __future__ import annotations

from html import unescape
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


PDF_TEXT_PATTERN = re.compile(rb"\((?P<text>(?:\\.|[^\\)])*)\)\s*Tj")


def extract_text(file_path: Path | str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".md":
        return path.read_text(encoding="utf-8").strip()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)

    raise ValueError(f"不支持的文件类型: {path.suffix}")


def _extract_pdf_text(path: Path) -> str:
    matches = PDF_TEXT_PATTERN.findall(path.read_bytes())
    decoded_segments = [_decode_pdf_literal_text(match) for match in matches]
    return "\n".join(segment for segment in decoded_segments if segment).strip()


def _decode_pdf_literal_text(raw_bytes: bytes) -> str:
    decoded_text = raw_bytes.decode("latin-1")
    replacements = {
        r"\(": "(",
        r"\)": ")",
        r"\\": "\\",
        r"\n": "\n",
        r"\r": "\r",
        r"\t": "\t",
    }
    for source_text, target_text in replacements.items():
        decoded_text = decoded_text.replace(source_text, target_text)
    return decoded_text.strip()


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ET.fromstring(document_xml)
    text_nodes = [unescape(node.text or "") for node in root.iter() if node.tag.endswith("}t")]
    return "\n".join(text for text in text_nodes if text).strip()
