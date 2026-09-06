"""Proof obligations use pinned evidence, never investigator confidence."""
from datetime import datetime

from .contracts import StrictModel, AtomicClaim, digest, SemanticVerdict


class Validation(StrictModel):
    valid: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


def verify_claim(claim: AtomicClaim, snapshot, graph, hypothesis, retrieved, *, graph_enabled=True):
    checks, failures, support = [], [], []
    try:
        AtomicClaim.model_validate_json(claim.model_dump_json())
        checks.append("schema")
    except ValueError:
        return Validation(valid=False, checks=(), failures=("schema",))
    for ref in claim.supporting_evidence + claim.contradicting_evidence:
        event = snapshot.by_id.get(ref.event_id)
        if not event:
            failures.append("event_existence"); continue
        if (event.tenant, event.request) != (snapshot.scope.tenant, snapshot.scope.request):
            failures.append("scope")
        if event.source not in hypothesis.allowed_sources:
            failures.append("source")
        if ref.source_snapshot != snapshot.id or ref.content_hash != event.raw_content_hash:
            failures.append("integrity")
        if ref.retrieved_by_query not in retrieved.get(ref.event_id, set()):
            failures.append("unobserved_evidence")
        for field, value_hash in zip(ref.fields, ref.value_hashes):
            if field not in type(event).model_fields or field == "raw_json" or digest(getattr(event, field)) != value_hash:
                failures.append("field_integrity")
        if ref in claim.supporting_evidence:
            if ref.relation != "supports": failures.append("evidence_relation")
            support.append(event)
        elif ref.relation != "contradicts": failures.append("evidence_relation")
    if not failures: checks.extend(("event_existence", "scope", "integrity"))
    banks = [e for e in support if e.event_type == "BANK_CHANGE"]
    payments = [e for e in support if e.event_type == "PAYMENT"]
    if len(banks) != 1 or len(payments) != 1:
        failures.append("minimum_evidence")
    else:
        bank, payment = banks[0], payments[0]
        if (set(claim.actor_ids) != {bank.actor} or set(claim.session_ids) != {bank.session} or
            set(claim.object_ids) != {bank.object_id} or any((e.actor,e.session,e.object_id) !=
            (bank.actor,bank.session,bank.object_id) for e in support)):
            failures.append("identity")
        else: checks.append("identity")
        elapsed = (datetime.fromisoformat(payment.occurred_at)-datetime.fromisoformat(bank.occurred_at)).total_seconds()
        if not 0 < elapsed <= hypothesis.window_seconds or claim.start != bank.occurred_at or claim.end != payment.occurred_at:
            failures.append("temporal")
        else: checks.append("temporal")
        if bank.tcode in bank.approved_operations:
            failures.append("approved_scope")
        else: checks.append("approved_scope")
        if (bank.table not in hypothesis.bank_tables or bank.field not in hypothesis.bank_fields or
            bank.old_value == bank.new_value or not bank.old_value or not bank.new_value or
            payment.tcode not in hypothesis.payment_tcodes or payment.status != "POSTED"):
            failures.append("domain")
        else: checks.append("domain")
        required_fields = {"event_type","actor","session","object_id","occurred_at"}
        for ref in claim.supporting_evidence:
            event = snapshot.by_id.get(ref.event_id)
            if event is None: continue
            extra = {"field","old_value","new_value","table","tcode","approved_operations"} if event.event_type == "BANK_CHANGE" else {"status","tcode"}
            if not required_fields | extra <= set(ref.fields): failures.append("missing_evidence_fields")
        if graph_enabled and not graph.verified_path(claim.relationship_path, bank.event_id, payment.event_id):
            failures.append("relationship_path")
        elif graph_enabled:
            edge_lookup={e.edge_id:e for e in graph.edges}
            if any(eid not in retrieved for edge_id in claim.relationship_path for eid in edge_lookup[edge_id].source_events):
                failures.append("unobserved_path_evidence")
            else: checks.append("relationship_path")
        if claim.severity != "HIGH": failures.append("severity_policy")
    return Validation(valid=not failures, checks=tuple(sorted(set(checks))), failures=tuple(sorted(set(failures))))


def contradiction_ids(claim, events):
    """Only related synthetic policy/rollback records count as disconfirmation."""
    related = [e for e in events if e.object_id in claim.object_ids and e.actor in claim.actor_ids
               and e.session in claim.session_ids]
    banks = [e for e in related if e.event_type == "BANK_CHANGE" and e.occurred_at == claim.start]
    bank = banks[0] if banks else None
    return tuple(e.event_id for e in related if
        (e.event_type == "APPROVAL" and e.occurred_at <= claim.start and bank is not None and bank.tcode in e.approved_operations)
        or (e.event_type == "REVERSAL" and e.occurred_at >= claim.end)
        or (bank is not None and e.event_type == "BANK_CHANGE" and e.occurred_at < claim.end and e.event_id != bank.event_id
            and e.new_value == bank.old_value and e.old_value == bank.new_value))


def semantic_payload(claim, snapshot):
    """One atomic statement and exact cited fields only; no score, narrative or other claims."""
    references = claim.supporting_evidence + claim.contradicting_evidence
    return {"schema_version":"2.0.0", "claim_type":claim.claim_type, "statement":claim.statement,
        "actor_ids":claim.actor_ids, "session_ids":claim.session_ids, "object_ids":claim.object_ids,
        "start":claim.start, "end":claim.end,
        "evidence":[{"event_id":ref.event_id, "relation":ref.relation,
            "trust_label":"UNTRUSTED_LOG_DATA", "fields":{f:getattr(snapshot.by_id[ref.event_id],f) for f in ref.fields}}
            for ref in references if ref.event_id in snapshot.by_id]}


def validate_semantic_references(verdict, claim):
    allowed={r.event_id for r in claim.supporting_evidence+claim.contradicting_evidence}
    support={r.event_id for r in claim.supporting_evidence}
    if not verdict.reasons or not set(verdict.evidence_ids)<=allowed:
        raise ValueError("semantic verdict must cite supplied evidence and give reasons")
    if verdict.label=="SUPPORTED" and not support<=set(verdict.evidence_ids):
        raise ValueError("supported verdict must cite the complete minimum supporting set")
    return verdict


class ScriptedSemanticVerifier:
    """Deterministic protocol fake, not an independent probabilistic support result."""
    model_version = "scripted-semantic-2.0"
    def verify(self, payload):
        contradiction = any(e["relation"] == "contradicts" for e in payload["evidence"])
        overclaim = any(w in payload["statement"].lower() for w in ("fraud", "stole", "malicious", "guilty"))
        label = "CONTRADICTED" if contradiction else "INSUFFICIENT_EVIDENCE" if overclaim else "SUPPORTED"
        return SemanticVerdict(label=label,
            reasons=("scripted protocol check; not measured model support",),
            evidence_ids=tuple(e["event_id"] for e in payload["evidence"]), uncertainty="HIGH" if overclaim else "LOW")


def triage(validation, semantic, *, checks, required_checks, contradictions=(), missing=(),
           truncated=False, selective=True, semantic_enabled=True):
    """Interpretable score-free policy; HIGH severity does not imply high support."""
    if not validation.valid: return "ABSTAINED", validation.failures
    if contradictions: return "ABSTAINED", ("contradicting_evidence",)
    unresolved = set(required_checks)-set(checks)
    if not semantic_enabled: unresolved.discard("semantic_support")
    if missing or truncated or unresolved:
        return "HUMAN_REVIEW_REQUIRED", tuple(sorted(unresolved)) + tuple(missing) + (("truncated",) if truncated else ())
    if semantic_enabled and semantic.label != "SUPPORTED":
        return "HUMAN_REVIEW_REQUIRED", (semantic.label,)
    if selective and semantic_enabled and semantic.uncertainty == "HIGH":
        return "HUMAN_REVIEW_REQUIRED", ("semantic_uncertainty",)
    return "SURFACE_TO_ANALYST", ("all_enabled_obligations_satisfied",)
