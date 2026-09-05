"""Application-agnostic scope filter engine.

Reads a use case config (dict from YAML) and applies filter rules to
generic LogEvents. Knows nothing about SAP — operates only on generic
LogEvent fields and the abstract attributes the parser populated.

Supported filter rules under `scope_filter.match_any`:
  - operation_category_in: [list of categories]
  - operation_matches: [list of fnmatch patterns]
  - entity_classification_in: [list of classifications]
  - entity_matches: [list of fnmatch patterns]
  - action_type_in: [list of action types]
  - attributes_audit_class_in: [list of audit class names]
  - attributes_log_type_in: [list of log types]
  - deviation_flagged: bool

An event matches if ANY of the rules match (`match_any` semantics).
"""

from __future__ import annotations

import fnmatch
from typing import Any

from core.contracts import LogEvent


def _event_matches_rule(event: LogEvent, rule: dict[str, Any]) -> bool:
    """A rule is a single dict with one or more conditions; ALL must hold."""
    for key, expected in rule.items():
        if key == "operation_category_in":
            if event.operation_category not in expected:
                return False
        elif key == "operation_matches":
            if not event.operation:
                return False
            if not any(fnmatch.fnmatch(event.operation, p) for p in expected):
                return False
        elif key == "entity_classification_in":
            if event.entity_classification not in expected:
                return False
        elif key == "entity_matches":
            if not event.entity_accessed:
                return False
            if not any(fnmatch.fnmatch(event.entity_accessed, p) for p in expected):
                return False
        elif key == "action_type_in":
            if event.action_type not in expected:
                return False
        elif key == "attributes_audit_class_in":
            if event.attributes.get("audit_class") not in expected:
                return False
        elif key == "attributes_log_type_in":
            if event.attributes.get("log_type") not in expected:
                return False
        elif key == "deviation_flagged":
            if event.deviation_flagged != expected:
                return False
        else:
            # Unknown rule type — be strict, log loudly
            raise ValueError(f"Unknown filter rule key: {key!r}")
    return True


def apply_use_case_filter(
    events: list[LogEvent], use_case_config: dict[str, Any]
) -> list[LogEvent]:
    """Return events scoped to this use case using match_any semantics."""
    scope = use_case_config.get("scope_filter") or {}
    rules: list[dict[str, Any]] = scope.get("match_any") or []
    if not rules:
        # No rules = everything in scope. Probably not what you want; flag.
        raise ValueError(
            f"Use case {use_case_config.get('use_case')!r} has empty scope_filter.match_any"
        )

    # Validate the whole configuration before matching; short-circuiting must not
    # hide an unknown or empty rule, including when no input events exist.
    keys = {"operation_category_in", "operation_matches", "entity_classification_in",
            "entity_matches", "action_type_in", "attributes_audit_class_in",
            "attributes_log_type_in", "deviation_flagged"}
    for rule in rules:
        if not isinstance(rule, dict) or not rule or set(rule) - keys:
            raise ValueError("Unknown or empty scope filter rule")
        for key, value in rule.items():
            if key == "deviation_flagged":
                if type(value) is not bool:
                    raise ValueError("deviation_flagged requires a boolean")
            elif not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
                raise ValueError("scope filter requires a nonempty string list")

    return [e for e in events if any(_event_matches_rule(e, r) for r in rules)]
