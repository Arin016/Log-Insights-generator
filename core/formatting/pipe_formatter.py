"""Format scoped events as pipe-delimited rows with a schema header.

We send pipe-delimited (not JSON) to the LLM because:
  - JSON would repeat field names per row, wasting tokens
  - Sonnet handles tabular input cleanly when given a schema header
  - Roughly 3x more compact for the same information

We drop boilerplate columns (account_key, ff_owner, instance, etc.) that
add no analytical value.
"""

from __future__ import annotations

from core.contracts import LogEvent

# Columns kept for analyzer input. Order matters — header order = data order.
ANALYZER_COLUMNS = [
    "event_id",
    "session_id",
    "ts",            # short timestamp
    "tcode",
    "table",
    "action",        # CREATE/UPDATE/DELETE/EXECUTE/READ/OTHER
    "deviation",     # YES/NO
    "audit_class",
    "log_type",
    "field",         # for CHANGE LOG
    "old_val",
    "new_val",
    "detail",        # SM20/SM21 detail text (extracted)
    "program",
    "terminal",
]


def _short_ts(event: LogEvent) -> str:
    """Compact timestamp: HHMM:SS within day. Date stays in metadata."""
    return event.timestamp_utc.strftime("%H%M:%S")


def _safe(v) -> str:
    """Render a value safely for pipe-delimited output."""
    if v is None:
        return ""
    s = str(v)
    # Replace pipes within fields to keep rows parseable
    s = s.replace("|", "/")
    # Strip newlines
    s = s.replace("\n", " ").replace("\r", " ")
    return s


def _extract_detail(event: LogEvent) -> str:
    """Extract meaningful detail text for SM20/SM21 events.

    For CHANGE LOG events, field/old_val/new_val are already separate columns.
    For SM20/SM21, the raw_details field contains the signal (debugger jumps,
    RFC_READ_TABLE, ROWCOUNT, field changes, etc.).
    """
    attrs = event.attributes or {}
    log_type = attrs.get("log_type") or ""
    if log_type in ("SM20 LOG", "SM21 LOG"):
        raw = attrs.get("raw_details") or ""
        # Truncate to keep rows manageable but preserve the signal
        return raw[:150].strip()
    return ""


def event_to_row(event: LogEvent) -> str:
    attrs = event.attributes or {}
    values = [
        event.event_id,
        event.session_id,
        _short_ts(event),
        event.operation or "",
        event.entity_accessed or "",
        event.action_type,
        "YES" if event.deviation_flagged else "NO",
        attrs.get("audit_class") or "",
        attrs.get("log_type") or "",
        attrs.get("field") or "",
        attrs.get("old_val") or "",
        attrs.get("new_val") or "",
        _extract_detail(event),
        attrs.get("program_name") or "",
        attrs.get("terminal") or "",
    ]
    return "|".join(_safe(v) for v in values)


def format_events(events: list[LogEvent]) -> str:
    """Header + one row per event."""
    header = "|".join(ANALYZER_COLUMNS)
    rows = [event_to_row(e) for e in events]
    return "\n".join([header, *rows])


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/code-like text."""
    return max(1, len(text) // 4)
