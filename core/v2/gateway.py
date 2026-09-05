"""Capability-bound read-only retrieval. Model arguments never contain a scope."""
from __future__ import annotations

import secrets
import time
from typing import Literal

from pydantic import Field, model_validator

from .contracts import StrictModel, Scope, CanonicalEvent, canonical_json, digest, utcnow


TEMPLATES = ("seed_events", "events_by_object", "contradictions_by_object", "events_by_ids",
             "events_by_tcode", "events_by_session", "events_in_time_window")


class Query(StrictModel):
    template: Literal["seed_events", "events_by_object", "contradictions_by_object", "events_by_ids",
                      "events_by_tcode", "events_by_session", "events_in_time_window"]
    value: str | None = Field(default=None, max_length=160)
    event_ids: tuple[str, ...] = Field(default=(), max_length=32)
    start: str | None = None
    end: str | None = None
    cursor: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def argument_shape(self):
        from datetime import datetime
        needs_value = self.template in {"events_by_object", "contradictions_by_object", "events_by_tcode", "events_by_session"}
        if needs_value != bool(self.value):
            raise ValueError("template value mismatch")
        if (self.template == "events_by_ids") != bool(self.event_ids):
            raise ValueError("template event_ids mismatch")
        if self.template == "events_in_time_window":
            if not self.start or not self.end:
                raise ValueError("time range required")
            a, b = datetime.fromisoformat(self.start), datetime.fromisoformat(self.end)
            if a.tzinfo is None or b.tzinfo is None or a > b:
                raise ValueError("invalid time range")
        elif self.start is not None or self.end is not None:
            raise ValueError("unexpected time arguments")
        return self


class Capability(StrictModel):
    scope: Scope
    snapshot: str
    allowed_templates: tuple[str, ...] = TEMPLATES
    allowed_sources: tuple[str, ...] = ("synthetic_audit", "synthetic_policy")
    row_limit: int = Field(default=32, gt=0, le=1000)
    byte_limit: int = Field(default=65536, gt=0, le=1000000)
    expires_monotonic: float
    run_id: str


def matches(event, query):
    if query.template == "seed_events": return event.event_type == "BANK_CHANGE"
    if query.template == "events_by_object": return event.object_id == query.value
    if query.template == "contradictions_by_object":
        return event.object_id == query.value and (event.event_type in {"APPROVAL", "REVERSAL", "BANK_CHANGE"} or event.status in {"REVERSED", "PENDING"})
    if query.template == "events_by_ids": return event.event_id in query.event_ids
    if query.template == "events_by_tcode": return event.tcode == query.value
    if query.template == "events_by_session": return event.session == query.value
    if query.template == "events_in_time_window":
        from datetime import datetime
        return datetime.fromisoformat(query.start) <= datetime.fromisoformat(event.occurred_at) <= datetime.fromisoformat(query.end)
    raise ValueError("unknown template")


class MemoryBackend:
    def __init__(self, events): self.events = tuple(events)

    def fetch(self, cap, query, after, size):
        rows = sorted((e for e in self.events if (e.tenant, e.request, e.source_snapshot_id) ==
            (cap.scope.tenant, cap.scope.request, cap.snapshot) and e.source in cap.allowed_sources
            and matches(e, query)), key=lambda e: (e.occurred_at, e.event_id))
        remaining = [e for e in rows if after is None or (e.occurred_at, e.event_id) > tuple(after)]
        return remaining[:size], len(rows)


class Gateway:
    def __init__(self, snapshot, cap: Capability, backend=None):
        if cap.scope != snapshot.scope or cap.snapshot != snapshot.id:
            raise PermissionError("capability snapshot mismatch")
        self.snapshot, self.cap = snapshot, cap
        self.backend = backend or MemoryBackend(snapshot.events)
        self._cursors = {}
        self.trace = []

    def query(self, raw: dict):
        started = time.monotonic()
        qid = f"q-{len(self.trace)+1:05d}"
        entry = {"query_id": qid, "request": raw, "executed_at": utcnow()}
        try:
            if started >= self.cap.expires_monotonic:
                raise TimeoutError("capability expired")
            query = Query.model_validate(raw)
            if query.template not in self.cap.allowed_templates:
                raise PermissionError("template outside capability")
            signature = digest(query.model_dump(exclude={"cursor"}))
            after, offset = None, 0
            if query.cursor:
                saved = self._cursors.get(query.cursor)
                if not saved or saved[0] != signature:
                    raise PermissionError("cursor outside query/run capability")
                _, after, offset = saved
            rows, total = self.backend.fetch(self.cap, query, after, self.cap.row_limit)
            if type(total) is not int or total < offset + len(rows) or len(rows) > self.cap.row_limit:
                raise ValueError("invalid backend counts")
            selected, used = [], 0
            last_key = tuple(after) if after else None
            for event in rows:
                CanonicalEvent.model_validate_json(event.model_dump_json())
                expected = self.snapshot.by_id.get(event.event_id)
                key = (event.occurred_at, event.event_id)
                if event != expected or event.source not in self.cap.allowed_sources or not matches(event, query):
                    raise PermissionError("backend scope/integrity violation")
                if last_key is not None and key <= last_key:
                    raise ValueError("backend ordering violation")
                last_key = key
                size = len(canonical_json(event.visible()).encode())
                if used + size > self.cap.byte_limit: break
                selected.append(event.visible())
                used += size
            consumed = offset + len(selected)
            truncated = consumed < total
            cursor = None
            if truncated and selected:
                cursor = secrets.token_urlsafe(18)
                last = selected[-1]
                self._cursors[cursor] = (signature, (last["occurred_at"], last["event_id"]), consumed)
            if time.monotonic() >= self.cap.expires_monotonic:
                raise TimeoutError("query exceeded capability deadline")
            result = dict(query_id=qid, template=query.template, scope=self.cap.scope.model_dump(),
                rows=selected, returned_count=len(selected), total_known_count=total, truncated=truncated,
                next_cursor=cursor, source_snapshot=self.cap.snapshot, executed_at=entry["executed_at"],
                duration_ms=(time.monotonic()-started)*1000, returned_bytes=used,
                completeness="BYTE_LIMIT_NO_PROGRESS" if truncated and not selected else "PAGE")
            entry["response"] = result
            return result
        except Exception as exc:
            entry["error"] = type(exc).__name__ + ": " + str(exc)
            raise
        finally:
            entry["duration_ms"] = (time.monotonic()-started)*1000
            self.trace.append(entry)

    def batch(self, requests: list[dict]):
        if not 1 <= len(requests) <= 8:
            raise ValueError("batch requires 1..8 queries")
        return {"results": [self.query(query) for query in requests]}
