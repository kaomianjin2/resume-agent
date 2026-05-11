from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
import urllib.error
import urllib.request

from interview_agent.config import LLMConfig


class LLMError(RuntimeError):
    """Raised when the LLM client cannot produce a valid result."""


class JSONParseError(LLMError):
    """Raised when model output cannot be parsed into a JSON object."""


class OpenAICompatibleResponseError(LLMError):
    """Raised when the upstream response shape is invalid."""


Transport = Callable[[urllib.request.Request], str]


def _default_transport(request: urllib.request.Request) -> str:
    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read()
    except urllib.error.URLError as error:
        raise LLMError(f"OpenAI-compatible 请求失败: {error.reason}") from error

    return response_body.decode("utf-8")


@dataclass(frozen=True)
class FakeLLMClient:
    response_text: str

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        del prompt, system_prompt
        return self.response_text


@dataclass(frozen=True)
class OpenAICompatibleClient:
    config: LLMConfig
    transport: Transport = _default_transport

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        request = _build_chat_completions_request(self.config, prompt, system_prompt)
        raw_response = self.transport(request)
        return _extract_message_content(raw_response)


def request_structured_output(
    client: FakeLLMClient | OpenAICompatibleClient,
    prompt: str,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    response_text = client.complete(prompt=prompt, system_prompt=system_prompt)
    return parse_json_object(response_text)


def parse_json_object(response_text: str) -> dict[str, Any]:
    stripped_response = response_text.strip()
    if not stripped_response:
        raise JSONParseError("LLM 返回空响应")

    try:
        parsed_response = json.loads(stripped_response)
    except json.JSONDecodeError as error:
        raise JSONParseError("LLM 返回非 JSON") from error

    if not isinstance(parsed_response, dict):
        raise JSONParseError("LLM 返回的 JSON 顶层必须是对象")

    return parsed_response


def _build_chat_completions_request(
    config: LLMConfig,
    prompt: str,
    system_prompt: str | None,
) -> urllib.request.Request:
    request_body = {
        "model": config.model,
        "messages": _build_messages(prompt=prompt, system_prompt=system_prompt),
    }
    request_data = json.dumps(request_body).encode("utf-8")
    request_url = f"{config.base_url.rstrip('/')}/chat/completions"

    return urllib.request.Request(
        url=request_url,
        data=request_data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _build_messages(prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
    if not system_prompt:
        return [{"role": "user", "content": prompt}]

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]


def _extract_message_content(raw_response: str) -> str:
    response_payload = parse_json_object(raw_response)
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenAICompatibleResponseError("OpenAI-compatible 响应缺少 choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise OpenAICompatibleResponseError("OpenAI-compatible 响应中的 choice 必须是对象")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise OpenAICompatibleResponseError("OpenAI-compatible 响应缺少 message")

    content = message.get("content")
    if not isinstance(content, str):
        raise OpenAICompatibleResponseError("OpenAI-compatible 响应缺少文本 content")

    return content
