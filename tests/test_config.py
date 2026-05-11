from __future__ import annotations

from pathlib import Path

import pytest

from interview_agent.config import AppConfig, ConfigError, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "interview-agent.toml.example"


def write_config(config_path: Path, content: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def test_load_config_reads_default_project_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_config(
        tmp_path / "config" / "interview-agent.toml",
        """
[llm]
base_url = "https://example.com/v1"
api_key = "file-key"
model = "file-model"

[embedding]
provider = "local"
model_name = "BAAI/bge-m3"
model_path = "./models/bge-m3"

[storage]
database_path = "./data/interview_agent.sqlite"

[knowledge_base]
source = "/Users/cynicism/Desktop/面试"
chunk_size = 900
chunk_overlap = 120
top_k = 8
index_version = "v1"
""".strip(),
    )

    config = load_config()

    assert isinstance(config, AppConfig)
    assert config.llm.base_url == "https://example.com/v1"
    assert config.llm.api_key == "file-key"
    assert config.llm.model == "file-model"
    assert config.embedding.model_path == "./models/bge-m3"
    assert config.storage.database_path == "./data/interview_agent.sqlite"
    assert config.knowledge_base.top_k == 8


def test_load_config_raises_clear_error_when_default_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError, match="配置文件不存在: config/interview-agent.toml"):
        load_config()


def test_load_config_raises_clear_error_when_required_field_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "interview-agent.toml"
    write_config(
        config_path,
        """
[llm]
base_url = "https://example.com/v1"
api_key = "file-key"

[embedding]
provider = "local"
model_name = "BAAI/bge-m3"
model_path = "./models/bge-m3"

[storage]
database_path = "./data/interview_agent.sqlite"

[knowledge_base]
source = "/Users/cynicism/Desktop/面试"
chunk_size = 900
chunk_overlap = 120
top_k = 8
index_version = "v1"
""".strip(),
    )

    with pytest.raises(ConfigError, match="缺少必填字段: llm.model"):
        load_config(config_path)


def test_load_config_raises_clear_error_when_field_type_is_invalid(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "interview-agent.toml"
    write_config(
        config_path,
        """
[llm]
base_url = "https://example.com/v1"
api_key = "file-key"
model = "file-model"

[embedding]
provider = "local"
model_name = "BAAI/bge-m3"
model_path = "./models/bge-m3"

[storage]
database_path = "./data/interview_agent.sqlite"

[knowledge_base]
source = "/Users/cynicism/Desktop/面试"
chunk_size = "900"
chunk_overlap = 120
top_k = 8
index_version = "v1"
""".strip(),
    )

    with pytest.raises(ConfigError, match="字段类型错误: knowledge_base.chunk_size 期望 int"):
        load_config(config_path)


def test_load_config_does_not_read_environment_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config" / "interview-agent.toml"
    write_config(
        config_path,
        """
[llm]
base_url = "https://from-file.example/v1"
api_key = "file-key"
model = "file-model"

[embedding]
provider = "local"
model_name = "BAAI/bge-m3"
model_path = "./models/bge-m3"

[storage]
database_path = "./data/interview_agent.sqlite"

[knowledge_base]
source = "/Users/cynicism/Desktop/面试"
chunk_size = 900
chunk_overlap = 120
top_k = 8
index_version = "v1"
""".strip(),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://from-env.example/v1")
    monkeypatch.setenv("INTERVIEW_AGENT_MODEL", "env-model")

    config = load_config(config_path)

    assert config.llm.base_url == "https://from-file.example/v1"
    assert config.llm.api_key == "file-key"
    assert config.llm.model == "file-model"


def test_example_config_contains_placeholder_values_only() -> None:
    content = EXAMPLE_CONFIG.read_text(encoding="utf-8")

    assert 'base_url = "https://your-openai-compatible-endpoint/v1"' in content
    assert 'api_key = "your-key"' in content
    assert 'model = "your-model"' in content
    assert "sk-" not in content
    assert "实际" not in content
