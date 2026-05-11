"""Elasticsearch-backed event store.

Replaces the in-memory store. Same interface (so tools don't change), but
queries hit a local Elasticsearch instance via the official client.

Index shape (one doc per LogEvent), keyed by event_id, with a `request_access_key`
field on every doc so we can scope all queries to one RAK.
"""

from __future__ import annotations

import fnmatch
from datetime import datetime
from typing import Any

from elasticsearch import Elasticsearch

from config import (
    ELASTICSEARCH_INDEX,
    ELASTICSEARCH_PASSWORD,
    ELASTICSEARCH_URL,
    ELASTICSEARCH_USERNAME,
)
from core.contracts import LogEvent
from core.logging_setup import log


_DEFAULT_FETCH_SIZE = 200


def _es_client() -> Elasticsearch:
    if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
        return Elasticsearch(
            ELASTICSEARCH_URL,
            basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD),
        )
    return Elasticsearch(ELASTICSEARCH_URL)


def _doc_to_log_event(doc: dict[str, Any]) -> LogEvent:
    """Convert an Elasticsearch _source dict back to a LogEvent."""
    src = dict(doc)
    # ES stores datetime as ISO string
    ts_raw = src.get("timestamp_utc")
    if isinstance(ts_raw, str):
        src["timestamp_utc"] = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    return LogEvent.model_validate(src)


def _doc_to_compact_dict(doc: dict[str, Any]) -> dict[str, Any]:
    """Compact dict for tool output — what the LLM sees."""
    attrs = doc.get("attributes") or {}
    return {
        "event_id": doc.get("event_id"),
        "session_id": doc.get("session_id"),
        "timestamp": doc.get("timestamp_utc"),
        "tcode": doc.get("operation"),
        "table": doc.get("entity_accessed"),
        "action": doc.get("action_type"),
        "deviation": doc.get("deviation_flagged"),
        "audit_class": attrs.get("audit_class"),
        "log_type": attrs.get("log_type"),
        "field": attrs.get("field"),
        "old_val": attrs.get("old_val"),
        "new_val": attrs.get("new_val"),
    }


class ElasticsearchEventStore:
    """Per-RAK event store backed by Elasticsearch.

    All queries are scoped by request_access_key, ensuring tools can never
    leak data from other RAKs.
    """

    def __init__(self, rak_id: str, index: str | None = None):
        self.rak_id = rak_id
        self.index = index or ELASTICSEARCH_INDEX
        self.client = _es_client()

    # ─── Helpers ────────────────────────────────────────────────────────

    def _search(
        self,
        must: list[dict[str, Any]] | None = None,
        size: int = _DEFAULT_FETCH_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        """Run an ES search scoped to this RAK.

        Returns: (hits_source_list, total_count)
        """
        body = {
            "query": {
                "bool": {
                    "must": [{"term": {"request_access_key": self.rak_id}}]
                    + (must or [])
                }
            },
            "size": size,
            "sort": [{"timestamp_utc": {"order": "asc"}}],
            "track_total_hits": True,
        }
        try:
            res = self.client.search(index=self.index, body=body)
        except Exception as e:  # noqa: BLE001
            log.error("es.search_error", error=str(e), rak_id=self.rak_id)
            raise
        hits = [h["_source"] for h in res["hits"]["hits"]]
        total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else len(hits)
        return hits, total

    # ─── Bulk fetch (used at pipeline start) ────────────────────────────

    def fetch_all_events(self, page_size: int = 1000) -> list[LogEvent]:
        """Fetch every event for this RAK, paginated via search_after."""
        results: list[LogEvent] = []
        body = {
            "query": {
                "bool": {
                    "must": [{"term": {"request_access_key": self.rak_id}}]
                }
            },
            "size": page_size,
            "sort": [
                {"timestamp_utc": "asc"},
                {"event_id": "asc"},
            ],
            "track_total_hits": True,
        }

        search_after: list[Any] | None = None
        while True:
            paged_body = dict(body)
            if search_after is not None:
                paged_body["search_after"] = search_after
            res = self.client.search(index=self.index, body=paged_body)
            hits = res["hits"]["hits"]
            if not hits:
                break
            for h in hits:
                results.append(_doc_to_log_event(h["_source"]))
            search_after = hits[-1]["sort"]
            if len(hits) < page_size:
                break
        return results

    # ─── Tool-facing query methods (compact dicts) ──────────────────────

    def by_session(self, session_id: str, size: int = _DEFAULT_FETCH_SIZE) -> dict[str, Any]:
        hits, total = self._search(
            [{"term": {"session_id": session_id}}], size=size
        )
        return {
            "session_id": session_id,
            "events": [_doc_to_compact_dict(h) for h in hits],
            "total_count": total,
            "truncated": total > len(hits),
        }

    def by_tcode(self, tcode: str, size: int = _DEFAULT_FETCH_SIZE) -> dict[str, Any]:
        hits, total = self._search(
            [{"term": {"operation.keyword": tcode}}], size=size
        )
        return {
            "tcode": tcode,
            "events": [_doc_to_compact_dict(h) for h in hits],
            "total_count": total,
            "truncated": total > len(hits),
        }

    def by_table(self, table: str, size: int = _DEFAULT_FETCH_SIZE) -> dict[str, Any]:
        hits, total = self._search(
            [{"term": {"entity_accessed.keyword": table}}], size=size
        )
        return {
            "table": table,
            "events": [_doc_to_compact_dict(h) for h in hits],
            "total_count": total,
            "truncated": total > len(hits),
        }

    def by_change_indicator(self, indicator: str, size: int = _DEFAULT_FETCH_SIZE) -> dict[str, Any]:
        hits, total = self._search(
            [{"term": {"attributes.change_indicator.keyword": indicator}}], size=size
        )
        return {
            "indicator": indicator,
            "events": [_doc_to_compact_dict(h) for h in hits],
            "total_count": total,
            "truncated": total > len(hits),
        }

    def in_time_window(self, start: datetime, end: datetime, size: int = _DEFAULT_FETCH_SIZE) -> dict[str, Any]:
        hits, total = self._search(
            [
                {
                    "range": {
                        "timestamp_utc": {
                            "gte": start.isoformat(),
                            "lte": end.isoformat(),
                        }
                    }
                }
            ],
            size=size,
        )
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "events": [_doc_to_compact_dict(h) for h in hits],
            "total_count": total,
            "truncated": total > len(hits),
        }

    def matching_tcode_pattern(self, pattern: str, size: int = _DEFAULT_FETCH_SIZE) -> dict[str, Any]:
        # ES wildcard expects '*' / '?'; fnmatch uses same syntax for these
        hits, total = self._search(
            [{"wildcard": {"operation.keyword": {"value": pattern}}}], size=size
        )
        return {
            "pattern": pattern,
            "events": [_doc_to_compact_dict(h) for h in hits],
            "total_count": total,
            "truncated": total > len(hits),
        }

    def list_sessions(self) -> dict[str, Any]:
        # Aggregation-based session summary
        body = {
            "size": 0,
            "query": {"term": {"request_access_key": self.rak_id}},
            "aggs": {
                "by_session": {
                    "terms": {"field": "session_id.keyword", "size": 1000},
                    "aggs": {
                        "min_ts": {"min": {"field": "timestamp_utc"}},
                        "max_ts": {"max": {"field": "timestamp_utc"}},
                        "tcodes": {"terms": {"field": "operation.keyword", "size": 100}},
                    },
                }
            },
        }
        res = self.client.search(index=self.index, body=body)
        buckets = res["aggregations"]["by_session"]["buckets"]
        sessions = []
        for b in buckets:
            sessions.append({
                "session_id": b["key"],
                "event_count": b["doc_count"],
                "start": b["min_ts"]["value_as_string"],
                "end": b["max_ts"]["value_as_string"],
                "tcodes": [t["key"] for t in b["tcodes"]["buckets"]],
            })
        sessions.sort(key=lambda x: x["start"] or "")
        return {"sessions": sessions}
