"""SAP Pass 2 tools, backed by ElasticsearchEventStore.

Tool function bodies do NOT change between in-memory and ES backings —
the store interface is the same. Only the binding type changed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.pass2.event_store import ElasticsearchEventStore
from core.pass2.tool_registry import Tool, register_tool, reset_registry


def _batch_query_tcodes(store: ElasticsearchEventStore, tcodes: list[str]) -> dict[str, Any]:
    """Query multiple tcodes in one call, return results grouped."""
    results = {}
    for tcode in tcodes:
        data = store.by_tcode(tcode)
        results[tcode] = {"total_count": data["total_count"], "events": data["events"]}
    return {"tcodes_queried": tcodes, "results": results}


def _batch_query_tables(store: ElasticsearchEventStore, tables: list[str]) -> dict[str, Any]:
    """Query multiple tables in one call, return results grouped."""
    results = {}
    for table in tables:
        data = store.by_table(table)
        results[table] = {"total_count": data["total_count"], "events": data["events"]}
    return {"tables_queried": tables, "results": results}


def register_sap_pass2_tools(store: ElasticsearchEventStore) -> None:
    """Register all SAP Pass 2 tools, bound to the given event store."""
    reset_registry()

    register_tool(Tool(
        name="query_events_by_tcode",
        description=(
            "Find all events in this RAK matching a specific SAP tcode. "
            "Use to check if a particular tcode (e.g., FB60, XK02) was "
            "executed somewhere in the RAK."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tcode": {"type": "string", "description": "Exact tcode like 'FB60'."},
            },
            "required": ["tcode"],
        },
        fn=lambda tcode: store.by_tcode(tcode),
    ))

    register_tool(Tool(
        name="query_events_by_table",
        description=(
            "Find all events in this RAK that touched a specific SAP table. "
            "Use to check whether bank details (LFBK), sensitive auth tables, "
            "etc. were modified anywhere in the RAK."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Exact table name like 'LFBK'."},
            },
            "required": ["table"],
        },
        fn=lambda table: store.by_table(table),
    ))

    register_tool(Tool(
        name="query_session_events",
        description=(
            "Get all events from a specific session within this RAK. "
            "Use to understand the full sequence of activity in a session."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
            },
            "required": ["session_id"],
        },
        fn=lambda session_id: store.by_session(session_id),
    ))

    register_tool(Tool(
        name="query_events_by_change_indicator",
        description=(
            "Find Insert (I), Update (U), or Delete (D) events across the RAK. "
            "Use to find writes of a particular type."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "indicator": {"type": "string", "enum": ["I", "U", "D"]},
            },
            "required": ["indicator"],
        },
        fn=lambda indicator: store.by_change_indicator(indicator),
    ))

    register_tool(Tool(
        name="query_events_in_time_window",
        description=(
            "Find events between two ISO timestamps within this RAK. "
            "Use for narrow temporal investigations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start_iso": {"type": "string"},
                "end_iso": {"type": "string"},
            },
            "required": ["start_iso", "end_iso"],
        },
        fn=lambda start_iso, end_iso: store.in_time_window(
            datetime.fromisoformat(start_iso),
            datetime.fromisoformat(end_iso),
        ),
    ))

    register_tool(Tool(
        name="list_sessions_in_rak",
        description=(
            "List all sessions in this RAK with start/end times, tcodes used, "
            "and event counts. Use for an overview of the RAK structure."
        ),
        input_schema={"type": "object", "properties": {}},
        fn=lambda: store.list_sessions(),
    ))

    register_tool(Tool(
        name="query_events_by_tcode_pattern",
        description=(
            "Find events with a tcode matching a wildcard pattern "
            "(e.g., 'Z_*' for all custom Z tcodes, 'F*' for financial tcodes)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Wildcard pattern (* and ?)."},
            },
            "required": ["pattern"],
        },
        fn=lambda pattern: store.matching_tcode_pattern(pattern),
    ))

    register_tool(Tool(
        name="batch_query_tcodes",
        description=(
            "Query MULTIPLE tcodes in one call. Returns all events per tcode "
            "plus total counts. Use this instead of calling query_events_by_tcode "
            "repeatedly."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tcodes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tcodes to query, e.g. ['FB60', 'XK02', 'MIRO']",
                },
            },
            "required": ["tcodes"],
        },
        fn=lambda tcodes: _batch_query_tcodes(store, tcodes),
    ))

    register_tool(Tool(
        name="batch_query_tables",
        description=(
            "Query MULTIPLE tables in one call. Returns all events per table "
            "plus total counts. Use this instead of calling query_events_by_table "
            "repeatedly."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tables to query, e.g. ['LFBK', 'USR02', 'T001B']",
                },
            },
            "required": ["tables"],
        },
        fn=lambda tables: _batch_query_tables(store, tables),
    ))
