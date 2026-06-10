from __future__ import annotations

from dataclasses import is_dataclass, asdict
from enum import Enum
import re
from urllib.parse import urlsplit, urlunsplit


SENSITIVE_MARKERS = ("密码", "手机号", "验证码")
SENSITIVE_TOKEN_PATTERN = re.compile(
    r"(?i)(^|[^a-z0-9_])"
    r"(cookie|token|sessionid|browser_session|chrome_session|password|credential|auth|account_id|mobile)"
    r"([^a-z0-9_]|$)"
)
SESSION_ASSIGNMENT_PATTERN = re.compile(r"(?i)\bsession_id\s*[=:]\s*\S+")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:1\d{10}|\d{3,4}-?\d{7,8})(?!\d)")


def assert_no_sensitive_payload(value: object, *, error_message: str) -> None:
    flattened_payload = flatten_payload(value)
    lowered_payload = flattened_payload.lower()
    if any(marker in lowered_payload for marker in SENSITIVE_MARKERS):
        raise ValueError(error_message)
    if SENSITIVE_TOKEN_PATTERN.search(flattened_payload):
        raise ValueError(error_message)
    if SESSION_ASSIGNMENT_PATTERN.search(flattened_payload):
        raise ValueError(error_message)
    if EMAIL_PATTERN.search(flattened_payload) or PHONE_PATTERN.search(flattened_payload):
        raise ValueError(error_message)


def contains_sensitive_payload(value: object) -> bool:
    try:
        assert_no_sensitive_payload(value, error_message="敏感信息")
    except ValueError:
        return True
    return False


def flatten_payload(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return flatten_payload(asdict(value))
    if isinstance(value, dict):
        return " ".join(flatten_payload(item) for pair in value.items() for item in pair)
    if isinstance(value, list | tuple | set):
        return " ".join(flatten_payload(item) for item in value)
    return str(value)


def summarize_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = value.strip()
    if not normalized_value:
        return None
    parsed_url = urlsplit(normalized_value)
    if parsed_url.scheme and parsed_url.netloc:
        return urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip("/") or "/", "", ""))
    return normalized_value.split("?", 1)[0].split("#", 1)[0].rstrip("/") or normalized_value
