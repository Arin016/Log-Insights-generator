"""Load + render prompt templates from applications/sap/prompts/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import SAP_CONFIG_DIR


PROMPTS_DIR: Path = SAP_CONFIG_DIR / "prompts"


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    """Load a versioned prompt template by name (e.g. 'data_exfiltration_v1')."""
    path = PROMPTS_DIR / f"{name}.md"
    with open(path) as f:
        return f.read()


def _format_overrides(custom_rules: list[dict[str, Any]]) -> str:
    if not custom_rules:
        return "(none)"
    lines = []
    for rule in custom_rules:
        match = rule.get("matches")
        category = rule.get("category") or rule.get("classification")
        risk = rule.get("risk_level") or rule.get("sensitivity")
        lines.append(f"- {match}: {category} ({risk})")
    return "\n".join(lines)


def render_pass1_prompt(
    *,
    template_name: str,
    rak_metadata,
    custom_overrides: list[dict[str, Any]],
    events_table: str,
    event_count: int,
) -> str:
    template = load_prompt(template_name)
    return template.format(
        rak_id=rak_metadata.request_access_key,
        actor=rak_metadata.actor,
        requested_operations=", ".join(rak_metadata.requested_operations) or "(none)",
        session_ids=", ".join(rak_metadata.session_ids),
        rak_start=rak_metadata.rak_start.isoformat(),
        rak_end=rak_metadata.rak_end.isoformat(),
        custom_overrides=_format_overrides(custom_overrides),
        events_table=events_table,
        event_count=event_count,
    )


def render_pass2_prompt(
    *,
    rak_metadata,
    anchored_findings: list[Any],
    uncertain_findings: list[Any],
    original_events_table: str,
) -> str:
    template = load_prompt("pass2_react_v1")
    return template.format(
        rak_id=rak_metadata.request_access_key,
        actor=rak_metadata.actor,
        requested_operations=", ".join(rak_metadata.requested_operations) or "(none)",
        session_ids=", ".join(rak_metadata.session_ids),
        anchored_findings_json=json.dumps(
            [f.model_dump(mode="json") for f in anchored_findings], indent=2
        ),
        uncertain_findings_json=json.dumps(
            [f.model_dump(mode="json") for f in uncertain_findings], indent=2
        ),
        original_events_table=original_events_table,
    )
