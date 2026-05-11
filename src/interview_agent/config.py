from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any


DEFAULT_CONFIG_PATH = Path("config/interview-agent.toml")


class ConfigError(ValueError):
    """Raised when project configuration is missing or invalid."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model_name: str
    model_path: str


@dataclass(frozen=True)
class StorageConfig:
    database_path: str


@dataclass(frozen=True)
class KnowledgeBaseConfig:
    source: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    index_version: str


@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig
    embedding: EmbeddingConfig
    storage: StorageConfig
    knowledge_base: KnowledgeBaseConfig


def load_config(config_path: Path | str | None = None) -> AppConfig:
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise ConfigError(f"配置文件不存在: {path}")

    try:
        with path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"TOML 解析失败: {path}") from error

    llm_config = _require_table(raw_config, "llm")
    embedding_config = _require_table(raw_config, "embedding")
    storage_config = _require_table(raw_config, "storage")
    knowledge_base_config = _require_table(raw_config, "knowledge_base")

    return AppConfig(
        llm=LLMConfig(
            base_url=_require_str(llm_config, "llm.base_url"),
            api_key=_require_str(llm_config, "llm.api_key"),
            model=_require_str(llm_config, "llm.model"),
        ),
        embedding=EmbeddingConfig(
            provider=_require_str(embedding_config, "embedding.provider"),
            model_name=_require_str(embedding_config, "embedding.model_name"),
            model_path=_require_str(embedding_config, "embedding.model_path"),
        ),
        storage=StorageConfig(
            database_path=_require_str(storage_config, "storage.database_path"),
        ),
        knowledge_base=KnowledgeBaseConfig(
            source=_require_str(knowledge_base_config, "knowledge_base.source"),
            chunk_size=_require_int(knowledge_base_config, "knowledge_base.chunk_size"),
            chunk_overlap=_require_int(knowledge_base_config, "knowledge_base.chunk_overlap"),
            top_k=_require_int(knowledge_base_config, "knowledge_base.top_k"),
            index_version=_require_str(knowledge_base_config, "knowledge_base.index_version"),
        ),
    )


def _require_table(raw_config: dict[str, Any], section_name: str) -> dict[str, Any]:
    if section_name not in raw_config:
        raise ConfigError(f"缺少必填字段: {section_name}")

    section_value = raw_config[section_name]
    if not isinstance(section_value, dict):
        raise ConfigError(f"字段类型错误: {section_name} 期望 table")

    return section_value


def _require_str(section: dict[str, Any], field_name: str) -> str:
    field_key = field_name.split(".")[-1]
    if field_key not in section:
        raise ConfigError(f"缺少必填字段: {field_name}")

    field_value = section[field_key]
    if not isinstance(field_value, str):
        raise ConfigError(f"字段类型错误: {field_name} 期望 str")

    return field_value


def _require_int(section: dict[str, Any], field_name: str) -> int:
    field_key = field_name.split(".")[-1]
    if field_key not in section:
        raise ConfigError(f"缺少必填字段: {field_name}")

    field_value = section[field_key]
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise ConfigError(f"字段类型错误: {field_name} 期望 int")

    return field_value
