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
MAX_PDF_BYTES = 8_000_000


def extract_text(file_path: Path | str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".md":
        return path.read_text(encoding="utf-8").strip()
    if suffix == ".pdf":
        if path.stat().st_size > MAX_PDF_BYTES:
            raise ValueError("PDF 文件过大，跳过本地解析")
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)

    raise ValueError(f"不支持的文件类型: {path.suffix}")


def _extract_pdf_text(path: Path) -> str:
    extracted_segments: list[str] = []
    failed_stream_count = 0

    for stream_match in PDF_STREAM_PATTERN.finditer(path.read_bytes()):
        stream_dictionary = stream_match.group("dictionary")
        stream_bytes = stream_match.group("stream")
        try:
            decoded_stream = _decode_pdf_stream(stream_dictionary, stream_bytes)
        except ValueError:
            failed_stream_count += 1
            continue
        extracted_segments.extend(_extract_text_segments_from_pdf_stream(decoded_stream))

    extracted_text = "\n".join(segment for segment in extracted_segments if segment).strip()
    if not extracted_text and failed_stream_count:
        raise ValueError("PDF FlateDecode 解压失败")

    return extracted_text


def _decode_pdf_stream(stream_dictionary: bytes, stream_bytes: bytes) -> bytes:
    if b"/FlateDecode" not in stream_dictionary:
        return stream_bytes

    try:
        return zlib.decompress(stream_bytes)
    except zlib.error as error:
        raise ValueError("PDF FlateDecode 解压失败") from error


def _extract_text_segments_from_pdf_stream(stream_bytes: bytes) -> list[str]:
    segments: list[str] = []

    for text_object in _iter_pdf_text_objects(stream_bytes):
        for operand, operator in _iter_pdf_text_operations(text_object):
            if operator == b"Tj":
                segments.append(_decode_pdf_literal_text(operand[1:-1]))
                continue

            segments.append(_decode_pdf_text_array(operand))

    return [segment.strip() for segment in segments if segment.strip()]


def _iter_pdf_text_objects(stream_bytes: bytes) -> list[bytes]:
    text_objects: list[bytes] = []
    current_index = 0

    while current_index < len(stream_bytes):
        begin_index = stream_bytes.find(b"BT", current_index)
        if begin_index == -1:
            break
        end_index = stream_bytes.find(b"ET", begin_index + 2)
        if end_index == -1:
            break
        text_objects.append(stream_bytes[begin_index + 2 : end_index])
        current_index = end_index + 2

    return text_objects


def _iter_pdf_text_operations(stream_bytes: bytes) -> list[tuple[bytes, bytes]]:
    operations: list[tuple[bytes, bytes]] = []
    current_index = 0
    stream_length = len(stream_bytes)

    while current_index < stream_length:
        current_byte = stream_bytes[current_index]
        if current_byte == ord("("):
            literal_end_index = _find_pdf_literal_end_or_none(stream_bytes, current_index)
            if literal_end_index is None:
                current_index += 1
                continue
            next_index = _skip_pdf_whitespace(stream_bytes, literal_end_index + 1)
            if stream_bytes[next_index : next_index + 2] == b"Tj":
                operations.append((stream_bytes[current_index : literal_end_index + 1], b"Tj"))
                current_index = next_index + 2
                continue
            current_index = literal_end_index + 1
            continue
        if current_byte == ord("["):
            array_end_index = _find_pdf_array_end_or_none(stream_bytes, current_index)
            if array_end_index is None:
                current_index += 1
                continue
            next_index = _skip_pdf_whitespace(stream_bytes, array_end_index + 1)
            if stream_bytes[next_index : next_index + 2] == b"TJ":
                operations.append((stream_bytes[current_index : array_end_index + 1], b"TJ"))
                current_index = next_index + 2
                continue
            current_index = array_end_index + 1
            continue

        current_index += 1

    return operations


def _find_pdf_array_end_or_none(raw_bytes: bytes, start_index: int) -> int | None:
    try:
        return _find_pdf_array_end(raw_bytes, start_index)
    except ValueError:
        return None


def _find_pdf_literal_end_or_none(raw_bytes: bytes, start_index: int) -> int | None:
    try:
        return _find_pdf_literal_end(raw_bytes, start_index)
    except ValueError:
        return None


def _find_pdf_array_end(raw_bytes: bytes, start_index: int) -> int:
    current_index = start_index + 1
    nesting_depth = 1

    while current_index < len(raw_bytes):
        current_byte = raw_bytes[current_index]
        if current_byte == ord("("):
            literal_end_index = _find_pdf_literal_end_or_none(raw_bytes, current_index)
            if literal_end_index is None:
                raise ValueError("PDF 数组中的文本字符串未闭合")
            current_index = literal_end_index + 1
            continue
        if current_byte == ord("["):
            nesting_depth += 1
        elif current_byte == ord("]"):
            nesting_depth -= 1
            if nesting_depth == 0:
                return current_index
        current_index += 1

    return len(raw_bytes) - 1


def _skip_pdf_whitespace(raw_bytes: bytes, start_index: int) -> int:
    current_index = start_index
    while current_index < len(raw_bytes) and raw_bytes[current_index] in b"\x00\t\n\f\r ":
        current_index += 1
    return current_index


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
