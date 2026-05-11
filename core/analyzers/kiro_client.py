"""JSON extraction utilities for Kiro CLI output.

Handles ANSI stripping, markdown fence removal, and outermost-brace extraction.
"""

from __future__ import annotations

import json
import re
from typing import Any


_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _find_outermost_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(raw_output: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from LLM output.

    Raises ValueError if no parseable JSON object is found.
    """
    cleaned = _strip_ansi(raw_output).strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    no_fences = _strip_markdown_fences(cleaned)
    try:
        result = json.loads(no_fences)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    extracted = _find_outermost_json_object(no_fences)
    if extracted is not None:
        try:
            result = json.loads(extracted)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Found JSON-like substring but parse failed: {e}. "
                f"Substring head: {extracted[:200]!r}"
            ) from e

    raise ValueError(
        f"No JSON object found in output. Output head: {cleaned[:300]!r}"
    )
