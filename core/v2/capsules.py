import csv
import io
import json

from .contracts import StrictModel, canonical_json, digest
from .graph import build_graph


REPRESENTATIONS = ("raw", "pipe", "typed_json", "typed_edges", "hybrid")
PIPE_FIELDS = ("event_id", "session", "actor", "occurred_at", "event_type", "tcode", "table",
               "object_id", "field", "old_value", "new_value", "approved_operations", "status", "text")


class Capsule(StrictModel):
    version: str = "2.0.0"
    scope_json: str
    source_snapshot: str
    contract_hash: str
    contract_version: str
    representation: str
    serialized_evidence: str
    event_ids: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    missing_sources: tuple[str, ...]
    query_metadata_json: str
    truncated: bool
    row_budget: int
    byte_budget: int
    token_budget: int
    token_upper_bound: int
    content_hash: str


def serialize(events, graph, representation, defenses=True):
    if representation not in REPRESENTATIONS: raise ValueError("unknown representation")
    rows = [event.visible(include_text=not defenses) for event in events]
    if representation == "raw":
        # Raw source remains untrusted and contains all original source fields.
        data = [json.loads(event.raw_json) | {"event_id":event.event_id} for event in events]
    elif representation == "pipe":
        out = io.StringIO()
        writer = csv.writer(out, delimiter="|", lineterminator="\n")
        writer.writerow(PIPE_FIELDS)
        for row in rows:
            writer.writerow(canonical_json(row.get(k, "")) for k in PIPE_FIELDS)
        data = {"format":"quoted-pipe-json-cells-2.0", "table":out.getvalue()}
    elif representation == "typed_json": data = rows
    else:
        data = {"events":rows, "graph":graph.model_dump(mode="json")}
    return canonical_json({"trust_label":"UNTRUSTED_LOG_DATA", "representation":representation, "data":data})


def build_capsule(snapshot, hypothesis, events, *, representation="hybrid", row_budget=32,
                  byte_budget=65536, token_budget=65536, query_metadata=(), defenses=True, graph_enabled=True):
    if min(row_budget, byte_budget, token_budget) < 1: raise ValueError("positive budgets required")
    unique = {e.event_id:e for e in events}
    ordered = sorted(unique.values(), key=lambda e:(e.occurred_at,e.event_id))
    selected = []
    serialized = ""
    for event in ordered[:row_budget]:
        candidate = selected + [event]
        graph = build_graph(snapshot, candidate if graph_enabled else [])
        candidate_text = serialize(candidate, graph, representation, defenses)
        if len(candidate_text.encode()) > min(byte_budget, token_budget): break
        selected = candidate
        serialized = candidate_text
    if not serialized:
        serialized = serialize([], build_graph(snapshot, []), representation, defenses)
        if len(serialized.encode()) > min(byte_budget, token_budget):
            raise ValueError("capsule budget smaller than empty envelope")
    return Capsule(scope_json=canonical_json(snapshot.scope), source_snapshot=snapshot.id,
        contract_hash=digest(hypothesis), contract_version=hypothesis.version,
        representation=representation, serialized_evidence=serialized,
        event_ids=tuple(e.event_id for e in selected), evidence_hashes=tuple(e.raw_content_hash for e in selected),
        missing_sources=snapshot.missing_sources, query_metadata_json=canonical_json(query_metadata),
        truncated=len(selected)<len(ordered), row_budget=row_budget, byte_budget=byte_budget,
        token_budget=token_budget, token_upper_bound=len(serialized.encode()), content_hash=digest(serialized))


def decode_capsule(capsule):
    """Scripted investigator parses the actual selected representation, never labels."""
    envelope = json.loads(capsule.serialized_evidence)
    data = envelope["data"]
    if capsule.representation == "pipe":
        return [{k:json.loads(v) for k,v in row.items()}
                for row in csv.DictReader(io.StringIO(data["table"]), delimiter="|")]
    if capsule.representation in ("typed_edges", "hybrid"): return data["events"]
    return data
