from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class NodeContext:
    session_id: str | None = None
    services: Mapping[str, object] = field(default_factory=dict)


NodeHandler = Callable[[NodeContext, dict[str, object]], dict[str, object]]


@dataclass(frozen=True)
class NodeSpec:
    name: str
    description: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    handler: NodeHandler


def validate_required_inputs(spec: NodeSpec, inputs: Mapping[str, object]) -> list[str]:
    return [input_name for input_name in spec.required_inputs if input_name not in inputs]
