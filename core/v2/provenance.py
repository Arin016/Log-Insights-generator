from __future__ import annotations

from types import MappingProxyType

from .contracts import CanonicalEvent, SourceRecord, Scope, canonical_json, digest


class Snapshot:
    """Immutable content-addressed synthetic snapshot; reject conflicting duplicates."""
    def __init__(self, records: list[SourceRecord], scope: Scope, missing_sources=()):
        unique = {}
        for record in records:
            if (record.tenant, record.request) != (scope.tenant, scope.request):
                raise ValueError("cross-scope source")
            key = (record.source, record.locator)
            if key in unique and unique[key] != record:
                raise ValueError("conflicting duplicate locator")
            unique[key] = record
        rows = sorted(unique.values(), key=lambda r: (r.source, r.locator))
        self.scope = scope
        self.missing_sources = tuple(sorted(missing_sources))
        self.id = "snap-" + digest({"scope": scope.model_dump(),
            "records": [r.model_dump(mode="json") for r in rows], "missing_sources": self.missing_sources})
        self.duplicate_count = len(records) - len(rows)
        events = [CanonicalEvent(**r.model_dump(),
            event_id="evt-" + digest([r.tenant, r.request, r.source, r.locator])[:24],
            source_snapshot_id=self.id, source_record_locator=r.locator,
            raw_content_hash=digest(r), raw_json=canonical_json(r)) for r in rows]
        self.events = tuple(sorted(events, key=lambda e: (e.occurred_at, e.event_id)))
        self.by_id = MappingProxyType({e.event_id: e for e in self.events})
        self._sealed = True

    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            raise TypeError("snapshot is immutable")
        object.__setattr__(self, name, value)

    def verify(self):
        for event in self.events:
            CanonicalEvent.model_validate_json(event.model_dump_json())
        reconstructed = Snapshot([SourceRecord.model_validate_json(e.raw_json) for e in self.events],
                                 self.scope, self.missing_sources)
        if reconstructed.id != self.id:
            raise ValueError("snapshot content mismatch")


def reference(event, fields, query_id="initial", relation="supports"):
    from .contracts import EvidenceReference
    return EvidenceReference(event_id=event.event_id, source_snapshot=event.source_snapshot_id,
        content_hash=event.raw_content_hash, fields=tuple(fields),
        value_hashes=tuple(digest(getattr(event, field)) for field in fields),
        relation=relation, retrieved_by_query=query_id)
