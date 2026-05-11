"""Generic tool registry for Pass 2 ReAct.

Tools are registered by name with a JSON schema and a callable. The ReAct
runner only sees the registry — it doesn't know if tools query OpenSearch
or in-memory fixtures. This lets us swap the backend per environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., Any]


_REGISTRY: dict[str, Tool] = {}


def register_tool(tool: Tool) -> None:
    if tool.name in _REGISTRY:
        raise ValueError(f"Tool already registered: {tool.name}")
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> Tool:
    if name not in _REGISTRY:
        raise KeyError(f"Tool not registered: {name}")
    return _REGISTRY[name]


def list_tools() -> list[Tool]:
    return list(_REGISTRY.values())


def reset_registry() -> None:
    """Test helper."""
    _REGISTRY.clear()


def render_for_bedrock() -> list[dict[str, Any]]:
    """Render the registry as Bedrock tool definitions."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in _REGISTRY.values()
    ]
