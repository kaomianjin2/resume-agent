from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from math import sqrt
from pathlib import Path
from typing import Protocol

from interview_agent.config import EmbeddingConfig


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class FakeEmbedder:
    vocabulary: tuple[str, ...]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        normalized_text = text.lower()
        return [float(normalized_text.split().count(token.lower())) for token in self.vocabulary]


@dataclass
class LocalBGEEmbedder:
    model_name: str
    model_path: str
    _model: object | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [_normalize_vector(vector) for vector in vectors]

    def _get_model(self):
        if self._model is not None:
            return self._model

        model_path = Path(self.model_path)
        try:
            sentence_transformers = import_module("sentence_transformers")
        except ModuleNotFoundError as error:
            raise RuntimeError(
                f"本地 embedding 依赖缺失，请安装 sentence_transformers，并确认模型目录可用: {model_path}"
            ) from error

        try:
            self._model = sentence_transformers.SentenceTransformer(
                str(model_path),
                local_files_only=True,
                trust_remote_code=False,
            )
        except Exception as error:
            raise RuntimeError(
                f"无法从本地模型目录加载 embedding 模型 {self.model_name}: {model_path}"
            ) from error

        return self._model


def build_embedder(config: EmbeddingConfig) -> Embedder:
    if config.provider != "local":
        raise ValueError(f"不支持的 embedding provider: {config.provider}")

    if config.model_name == "unused":
        return FakeEmbedder(vocabulary=())

    return LocalBGEEmbedder(
        model_name=config.model_name,
        model_path=config.model_path,
    )


def _normalize_vector(vector: object) -> list[float]:
    values = [float(value) for value in vector]
    magnitude = sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return [0.0 for _ in values]
    return [value / magnitude for value in values]
