from __future__ import annotations

from html import unescape
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zlib
import zipfile


PDF_STREAM_PATTERN = re.compile(
    rb"<<(?P<dictionary>.*?)>>\s*stream\r?\n(?P<stream>.*?)\r?\nendstream",
    re.DOTALL,
)
PDF_TJ_PATTERN = re.compile(rb"(?P<operand>\[(?:.|\s)*?\]|\((?:\\.|[^\\)])*\))\s*(?P<operator>TJ|Tj)")


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
    extracted_segments: list[str] = []

    for stream_match in PDF_STREAM_PATTERN.finditer(path.read_bytes()):
        stream_dictionary = stream_match.group("dictionary")
        stream_bytes = stream_match.group("stream")
        decoded_stream = _decode_pdf_stream(stream_dictionary, stream_bytes)
        extracted_segments.extend(_extract_text_segments_from_pdf_stream(decoded_stream))

    return "\n".join(segment for segment in extracted_segments if segment).strip()


def _decode_pdf_stream(stream_dictionary: bytes, stream_bytes: bytes) -> bytes:
    if b"/FlateDecode" not in stream_dictionary:
        return stream_bytes

    try:
        return zlib.decompress(stream_bytes)
    except zlib.error as error:
        raise ValueError("PDF FlateDecode 解压失败") from error


def _extract_text_segments_from_pdf_stream(stream_bytes: bytes) -> list[str]:
    segments: list[str] = []

    for match in PDF_TJ_PATTERN.finditer(stream_bytes):
        operator = match.group("operator")
        operand = match.group("operand")
        if operator == b"Tj":
            if not operand.startswith(b"("):
                continue
            segments.append(_decode_pdf_literal_text(operand[1:-1]))
            continue

        segments.append(_decode_pdf_text_array(operand))

    return [segment.strip() for segment in segments if segment.strip()]


def _decode_pdf_text_array(array_bytes: bytes) -> str:
    literal_strings = _extract_pdf_literal_strings(array_bytes[1:-1])
    return "".join(_decode_pdf_literal_text(item) for item in literal_strings).strip()


def _extract_pdf_literal_strings(raw_bytes: bytes) -> list[bytes]:
    extracted_strings: list[bytes] = []
    current_index = 0

    while current_index < len(raw_bytes):
        if raw_bytes[current_index] != ord("("):
            current_index += 1
            continue

        literal_end_index = _find_pdf_literal_end(raw_bytes, current_index)
        extracted_strings.append(raw_bytes[current_index + 1 : literal_end_index])
        current_index = literal_end_index + 1

    return extracted_strings


def _find_pdf_literal_end(raw_bytes: bytes, start_index: int) -> int:
    current_index = start_index + 1
    nesting_depth = 1
    is_escaped = False

    while current_index < len(raw_bytes):
        current_byte = raw_bytes[current_index]
        if is_escaped:
            is_escaped = False
        elif current_byte == ord("\\"):
            is_escaped = True
        elif current_byte == ord("("):
            nesting_depth += 1
        elif current_byte == ord(")"):
            nesting_depth -= 1
            if nesting_depth == 0:
                return current_index
        current_index += 1

    raise ValueError("PDF 文本字符串未闭合")


def _decode_pdf_literal_text(raw_bytes: bytes) -> str:
    decoded_characters: list[str] = []
    current_index = 0

    while current_index < len(raw_bytes):
        current_byte = raw_bytes[current_index]
        if current_byte != ord("\\"):
            decoded_characters.append(chr(current_byte))
            current_index += 1
            continue

        current_index += 1
        if current_index >= len(raw_bytes):
            decoded_characters.append("\\")
            break

        escape_byte = raw_bytes[current_index]
        if escape_byte in b"nrtbf":
            decoded_characters.append(
                {
                    ord("n"): "\n",
                    ord("r"): "\r",
                    ord("t"): "\t",
                    ord("b"): "\b",
                    ord("f"): "\f",
                }[escape_byte]
            )
            current_index += 1
            continue
        if escape_byte in (ord("("), ord(")"), ord("\\")):
            decoded_characters.append(chr(escape_byte))
            current_index += 1
            continue
        if escape_byte in (ord("\n"), ord("\r")):
            current_index += 1
            if escape_byte == ord("\r") and current_index < len(raw_bytes) and raw_bytes[current_index] == ord("\n"):
                current_index += 1
            continue
        if chr(escape_byte).isdigit():
            octal_digits = [escape_byte]
            current_index += 1
            while current_index < len(raw_bytes) and len(octal_digits) < 3 and chr(raw_bytes[current_index]).isdigit():
                octal_digits.append(raw_bytes[current_index])
                current_index += 1
            decoded_characters.append(chr(int(bytes(octal_digits), 8)))
            continue

        decoded_characters.append(chr(escape_byte))
        current_index += 1

    return "".join(decoded_characters)


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ET.fromstring(document_xml)
    text_nodes = [unescape(node.text or "") for node in root.iter() if node.tag.endswith("}t")]
    return "\n".join(text for text in text_nodes if text).strip()
