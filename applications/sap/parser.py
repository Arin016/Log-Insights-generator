"""SAP log parser.

Converts pipe-delimited SAP log lines into generic LogEvent objects.
This is the only file in the system that knows about SAP's raw log format.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from core.contracts import LogEvent, ActionType
from applications.sap.catalogs import load_tcode_catalog, load_table_catalog


# Order must match SAP log format (pipe-delimited)
PIPE_FIELDS = [
    "log_id",
    "request_id",
    "session_id",
    "ff_id",
    "log_type",
    "start_time_utc",
    "end_time_utc",
    "user_name",
    "end_point",
    "end_point_key",
    "account_key",
    "ff_owner",
    "ff_controller",
    "requested_tcode",
    "host_name",
    "severity",
    "audit_class",
    "time_zone",
    "tcode_deviation",
    "transaction_code",
    "instance",
    "report_creation_dt",
    "log_creation_dt",
    "terminal",
    "program_name",
    "client",
    "details",
]

CHANGE_INDICATOR_TO_ACTION: dict[str, ActionType] = {
    "I": "CREATE",
    "U": "UPDATE",
    "D": "DELETE",
}


def _parse_timestamp(s: str) -> datetime:
    """SAP timestamps come as YYYYMMDDHHMMSS."""
    s = s.strip()
    return datetime.strptime(s, "%Y%m%d%H%M%S")


def _parse_change_log_details(details: str) -> dict:
    """CHANGE LOG details field is JSON. Returns {} on parse failure."""
    try:
        return json.loads(details)
    except (json.JSONDecodeError, TypeError):
        return {}


def _strip_or_none(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s if s else None


def parse_log_line(line: str) -> LogEvent | None:
    """Parse one pipe-delimited SAP log line to a LogEvent.

    Returns None on lines that can't be parsed (e.g. empty or malformed).
    """
    line = line.rstrip("\n").rstrip("\r")
    if not line.strip() or line.startswith("LOGID|"):
        return None  # skip header / blanks

    parts = line.split("|")
    # Pad if too few fields
    while len(parts) < len(PIPE_FIELDS):
        parts.append("")
    raw = dict(zip(PIPE_FIELDS, parts))

    log_type = (raw.get("log_type") or "").strip()
    transaction_code = _strip_or_none(raw.get("transaction_code"))
    requested_tcode = _strip_or_none(raw.get("requested_tcode"))

    # Parse details
    details_raw = raw.get("details") or ""
    table_accessed: str | None = None
    change_indicator: str | None = None
    parsed_details: dict = {}
    if log_type == "CHANGE LOG":
        parsed_details = _parse_change_log_details(details_raw)
        table_accessed = parsed_details.get("Table")
        change_indicator = parsed_details.get("Cha.Ind.")

    # Determine action type
    action_type: ActionType = "OTHER"
    if change_indicator and change_indicator in CHANGE_INDICATOR_TO_ACTION:
        action_type = CHANGE_INDICATOR_TO_ACTION[change_indicator]
    elif log_type in ("SM20 LOG", "TCODE LOG"):
        action_type = "EXECUTE"
    elif log_type == "SM21 LOG":
        action_type = "OTHER"

    # Catalog lookups
    tcode_catalog = load_tcode_catalog()
    table_catalog = load_table_catalog()
    operation_category = tcode_catalog.category_for(transaction_code)
    entity_classification = table_catalog.classification_for(table_accessed)

    # Timestamp
    try:
        ts = _parse_timestamp(raw["start_time_utc"])
    except ValueError:
        return None

    # Tcode deviation flag
    deviation = (raw.get("tcode_deviation") or "").strip().upper() == "YES"

    return LogEvent(
        event_id=raw["log_id"].strip(),
        request_access_key=raw["request_id"].strip(),
        session_id=raw["session_id"].strip(),
        timestamp_utc=ts,
        actor=raw["ff_id"].strip(),
        action_type=action_type,
        entity_accessed=table_accessed,
        entity_classification=entity_classification,
        operation=transaction_code,
        operation_category=operation_category,
        requested_operation=requested_tcode,
        deviation_flagged=deviation,
        application="sap",
        attributes={
            "log_type": log_type,
            "audit_class": _strip_or_none(raw.get("audit_class")),
            "severity": _strip_or_none(raw.get("severity")),
            "program_name": _strip_or_none(raw.get("program_name")),
            "host_name": _strip_or_none(raw.get("host_name")),
            "terminal": _strip_or_none(raw.get("terminal")),
            "client": _strip_or_none(raw.get("client")),
            "time_zone": _strip_or_none(raw.get("time_zone")),
            "change_indicator": change_indicator,
            # CHANGE LOG details fields broken out
            "table_key": parsed_details.get("Table Key"),
            "field": parsed_details.get("Field"),
            "old_val": parsed_details.get("Old val"),
            "new_val": parsed_details.get("New val"),
            "object": parsed_details.get("Obj."),
            "doc": parsed_details.get("Doc."),
            "raw_details": details_raw,
        },
    )


def parse_lines(lines: Iterable[str]) -> list[LogEvent]:
    """Parse many lines, dropping any that fail."""
    out: list[LogEvent] = []
    for line in lines:
        ev = parse_log_line(line)
        if ev is not None:
            out.append(ev)
    return out


def parse_file(path: str | Path) -> list[LogEvent]:
    """Parse a SAP log file (pipe-delimited)."""
    with open(path) as f:
        return parse_lines(f)
