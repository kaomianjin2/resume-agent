from __future__ import annotations

__all__ = ["build_knowledge_base"]


def build_knowledge_base(*args, **kwargs):
    from .build import build_knowledge_base as _build_knowledge_base

    return _build_knowledge_base(*args, **kwargs)
