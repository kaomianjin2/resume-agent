from __future__ import annotations

import json
import urllib.request

import pytest

from interview_agent.config import LLMConfig
from interview_agent.llm import (
    FakeLLMClient,
    JSONParseError,
    OpenAICompatibleClient,
    request_structured_output,
)
from interview_agent.prompts import PROMPT_TEMPLATES, get_prompt_template, render_prompt


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


def test_request_structured_output_rejects_non_json_response() -> None:
    client = FakeLLMClient(response_text="not json")

    with pytest.raises(JSONParseError, match="LLM 返回非 JSON"):
        request_structured_output(client, prompt="输出 JSON")


def test_request_structured_output_rejects_empty_response() -> None:
    client = FakeLLMClient(response_text="   ")

    with pytest.raises(JSONParseError, match="LLM 返回空响应"):
        request_structured_output(client, prompt="输出 JSON")


def test_request_structured_output_rejects_json_that_is_not_object() -> None:
    client = FakeLLMClient(response_text='["not", "object"]')

    with pytest.raises(JSONParseError, match="LLM 返回的 JSON 顶层必须是对象"):
        request_structured_output(client, prompt="输出 JSON")


def test_prompt_templates_cover_all_runtime_nodes() -> None:
    expected_prompt_names = {
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


def test_get_prompt_template_rejects_unknown_name() -> None:
    with pytest.raises(KeyError, match="未知 prompt 模板: unknown_prompt"):
        get_prompt_template("unknown_prompt")
