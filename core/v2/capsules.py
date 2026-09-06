import csv
import io
import json

from .contracts import StrictModel, canonical_json, digest
from .graph import build_graph


REPRESENTATIONS = ("raw", "legacy_pipe", "pipe", "typed_json", "typed_edges", "hybrid")
PIPE_FIELDS = ("event_id", "raw_content_hash", "session", "actor", "occurred_at", "event_type", "tcode", "table",
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
    elif representation == "legacy_pipe":
        from datetime import datetime
        from core.contracts import LogEvent
        from core.formatting.pipe_formatter import format_events
        legacy=[LogEvent(event_id=e.event_id,request_access_key=e.request,session_id=e.session,
            timestamp_utc=datetime.fromisoformat(e.occurred_at),actor=e.actor,operation=e.tcode,
            entity_accessed=e.table,action_type="UPDATE" if e.event_type=="BANK_CHANGE" else "EXECUTE",
            deviation_flagged=e.tcode not in e.approved_operations,
            attributes={"log_type":"SM20 LOG","field":e.field,"old_val":e.old_value,"new_val":e.new_value,
                        "raw_details":e.text if not defenses else ""}) for e in events]
        data={"format":"original-core-formatting-pipe_formatter","table":format_events(legacy)}
    elif representation == "pipe":
        out = io.StringIO()
        writer = csv.writer(out, delimiter="|", lineterminator="\n")
        writer.writerow(PIPE_FIELDS)
        for row in rows:
            writer.writerow(canonical_json(row.get(k, "")) for k in PIPE_FIELDS)
        data = {"format":"quoted-pipe-json-cells-2.0", "table":out.getvalue()}
    elif representation == "typed_json": data = rows
    elif representation == "typed_edges":
        # Compact source-linked edge tuples; hybrid retains fully typed graph objects.
        nodes = {n.node_id:n for n in graph.nodes}
        data = {"events":rows, "edge_columns":["edge_id","relation","source_event","target_kind","target_value","evidence_ids"],
                "edges":[[e.edge_id,e.kind,nodes[e.source].value,nodes[e.target].kind,
                          nodes[e.target].value,list(e.source_events)] for e in graph.edges]}
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
    if capsule.representation == "legacy_pipe":
        # Preserve actual legacy information loss. No hidden identity/object backfill.
        return list(csv.DictReader(io.StringIO(data["table"]),delimiter="|"))
    if capsule.representation == "pipe":
        return [{k:json.loads(v) for k,v in row.items()}
                for row in csv.DictReader(io.StringIO(data["table"]), delimiter="|")]
    if capsule.representation in ("typed_edges", "hybrid"): return data["events"]
    return data
