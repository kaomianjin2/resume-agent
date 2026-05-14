from __future__ import annotations

import json
import http.client
import urllib.request

import pytest

from interview_agent.config import LLMConfig
from interview_agent.llm import (
    FakeLLMClient,
    JSONParseError,
    OpenAICompatibleClient,
    _default_transport,
    request_structured_output,
)
from interview_agent.prompts import (
    PROMPT_OUTPUT_KEYS,
    PROMPT_OUTPUT_SCHEMA_HINTS,
    PROMPT_TEMPLATES,
    get_prompt_template,
    render_prompt,
)


def test_fake_llm_fixed_json_response_is_parsed() -> None:
    client = FakeLLMClient(response_text='{"result":"ok","score": 9}')

    result = request_structured_output(client, prompt="请返回 JSON")

    assert result == {"result": "ok", "score": 9}


def test_openai_compatible_client_uses_config_values_not_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://from-env.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("INTERVIEW_AGENT_MODEL", "env-model")
    captured_request: dict[str, object] = {}

    def fake_transport(request: urllib.request.Request) -> str:
        captured_request["url"] = request.full_url
        captured_request["authorization"] = request.get_header("Authorization")
        captured_request["content_type"] = request.get_header("Content-type")
        captured_request["body"] = json.loads(request.data.decode("utf-8"))
        return '{"choices":[{"message":{"content":"{\\"status\\": \\"ok\\"}"}}]}'

    client = OpenAICompatibleClient(
        config=LLMConfig(
            base_url="https://from-file.example/v1",
            api_key="file-key",
            model="file-model",
        ),
        transport=fake_transport,
    )

    result = request_structured_output(client, prompt="输出 JSON")

    assert result == {"status": "ok"}
    assert captured_request == {
        "url": "https://from-file.example/v1/chat/completions",
        "authorization": "Bearer file-key",
        "content_type": "application/json",
        "body": {
            "model": "file-model",
            "messages": [{"role": "user", "content": "输出 JSON"}],
        },
    }


def test_default_transport_retries_incomplete_read() -> None:
    calls = 0
    original_urlopen = urllib.request.urlopen

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

    def flaky_urlopen(request: urllib.request.Request, timeout: int) -> Response:
        del request
        assert timeout == 60
        nonlocal calls
        calls += 1
        if calls == 1:
            raise http.client.IncompleteRead(b"partial")
        return Response()

    urllib.request.urlopen = flaky_urlopen
    try:
        body = _default_transport(urllib.request.Request("https://example.test/v1/chat/completions"))
    finally:
        urllib.request.urlopen = original_urlopen

    assert calls == 2
    assert json.loads(body)["choices"]


def test_default_transport_retries_timeout() -> None:
    calls = 0
    original_urlopen = urllib.request.urlopen

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

    def flaky_urlopen(request: urllib.request.Request, timeout: int) -> Response:
        del request, timeout
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("read timed out")
        return Response()

    urllib.request.urlopen = flaky_urlopen
    try:
        body = _default_transport(urllib.request.Request("https://example.test/v1/chat/completions"))
    finally:
        urllib.request.urlopen = original_urlopen

    assert calls == 2
    assert json.loads(body)["choices"]


def test_request_structured_output_rejects_non_json_response() -> None:
    client = FakeLLMClient(response_text="not json")

    with pytest.raises(JSONParseError, match="LLM 返回非 JSON"):
        request_structured_output(client, prompt="输出 JSON")


def test_request_structured_output_rejects_empty_response() -> None:
    client = FakeLLMClient(response_text="   ")

    with pytest.raises(JSONParseError, match="LLM 返回空响应"):
        request_structured_output(client, prompt="输出 JSON")


def test_request_structured_output_retries_empty_response() -> None:
    calls = 0

    class FlakyClient:
        def complete(self, prompt: str, system_prompt: str | None = None) -> str:
            del prompt, system_prompt
            nonlocal calls
            calls += 1
            if calls == 1:
                return ""
            return '{"ok": true}'

    result = request_structured_output(FlakyClient(), prompt="输出 JSON")

    assert calls == 2
    assert result == {"ok": True}


def test_request_structured_output_rejects_json_that_is_not_object() -> None:
    client = FakeLLMClient(response_text='["not", "object"]')

    with pytest.raises(JSONParseError, match="LLM 返回的 JSON 顶层必须是对象"):
        request_structured_output(client, prompt="输出 JSON")


def test_prompt_templates_cover_all_runtime_nodes() -> None:
    expected_prompt_names = {
        "algorithm_practice",
        "practice_answer_review",
        "knowledge_search",
        "resume_parse",
        "project_extract",
        "jd_parse",
        "jd_match",
        "question_generate",
        "mock_followup",
        "answer_score",
        "weakness_train",
        "resume_optimize",
        "session_summary",
    }

    assert set(PROMPT_TEMPLATES) == expected_prompt_names
    for prompt_name in expected_prompt_names:
        prompt_template = get_prompt_template(prompt_name)
        assert prompt_template == PROMPT_TEMPLATES[prompt_name]
        assert prompt_template.strip()


def test_render_prompt_formats_runtime_template() -> None:
    rendered_prompt = render_prompt(
        "knowledge_search",
        question="请总结项目背景",
        context="项目文档片段",
    )

    assert "请总结项目背景" in rendered_prompt
    assert "项目文档片段" in rendered_prompt


def test_render_prompt_requires_contract_output_keys() -> None:
    rendered_prompt = render_prompt(
        "resume_parse",
        resume_text="Alice built Python services.",
    )

    assert "只返回 JSON 对象" in rendered_prompt
    assert "resume_profile" in rendered_prompt
    assert set(PROMPT_OUTPUT_KEYS) == set(PROMPT_TEMPLATES)
    assert set(PROMPT_OUTPUT_SCHEMA_HINTS) == set(PROMPT_TEMPLATES)


def test_render_prompt_describes_required_nested_output_fields() -> None:
    score_prompt = render_prompt(
        "answer_score",
        question="如何保障 SLA？",
        answer="建立告警。",
        rubric="按完整度评分。",
    )
    training_prompt = render_prompt(
        "weakness_train",
        weaknesses='["指标量化"]',
        goal="补强回答。",
    )
    optimize_prompt = render_prompt(
        "resume_optimize",
        resume_text="Alice built services.",
        target_role="Backend",
    )

    assert "JSON 顶层必须只包含字段: score_report" in score_prompt
    assert "score、gaps、suggestions、reference_answer" in score_prompt
    assert "focus、steps、drills、schedule" in training_prompt
    assert "summary、bullets、risks、rewrite_examples" in optimize_prompt


def test_get_prompt_template_rejects_unknown_name() -> None:
    with pytest.raises(KeyError, match="未知 prompt 模板: unknown_prompt"):
        get_prompt_template("unknown_prompt")
