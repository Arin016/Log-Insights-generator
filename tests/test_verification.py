import pytest

from core.v2.contracts import AtomicClaim, SemanticVerdict
from core.v2.graph import build_graph
from core.v2.provenance import reference
from core.v2.verification import verify_claim, semantic_payload, ScriptedSemanticVerifier, triage
from tests.test_graph_capsules import chain, hypothesis


FIELDS = ("event_type","actor","session","object_id","occurred_at","field","old_value","new_value",
          "table","tcode","approved_operations","status")


def claim_for(s=None):
    s = s or chain()
    bank,payment = s.events[0],s.events[-1]
    return AtomicClaim(claim_id="synthetic-claim", statement="Bank details changed outside approved scope before payment.",
        actor_ids=(bank.actor,), session_ids=(bank.session,), object_ids=(bank.object_id,),
        start=bank.occurred_at,end=payment.occurred_at,
        supporting_evidence=tuple(reference(e,FIELDS) for e in (bank,payment)),
        relationship_path=build_graph(s).path(bank.event_id,payment.event_id),
        prompt_version="2.0", model_version="scripted")


def verify(c,s=None):
    s = s or chain()
    return verify_claim(c,s,build_graph(s),hypothesis(),{e.event_id:{"initial"} for e in s.events})


def test_all_structural_checks():
    assert verify(claim_for()).valid


@pytest.mark.parametrize("change,failure", [
    ({"actor_ids":("other",)},"identity"), ({"session_ids":("other",)},"identity"),
    ({"object_ids":("other",)},"identity"), ({"relationship_path":()},"relationship_path"),
    ({"end":"2026-02-01T00:00:00+00:00"},"temporal"), ({"severity":"CRITICAL"},"severity_policy")])
def test_wrong_claim_rejected(change,failure):
    assert failure in verify(claim_for().model_copy(update=change)).failures


def test_real_irrelevant_and_fabricated_evidence():
    s,c = chain(),claim_for()
    refs = (reference(s.events[1],FIELDS),c.supporting_evidence[1])
    assert "minimum_evidence" in verify(c.model_copy(update={"supporting_evidence":refs})).failures
    ref=c.supporting_evidence[0].model_copy(update={"event_id":"fabricated"})
    assert "event_existence" in verify(c.model_copy(update={"supporting_evidence":(ref,c.supporting_evidence[1])})).failures


def test_field_and_query_integrity():
    c=claim_for()
    ref=c.supporting_evidence[0].model_copy(update={"retrieved_by_query":"invented", "content_hash":"0"*64})
    verdict=verify(c.model_copy(update={"supporting_evidence":(ref,c.supporting_evidence[1])}))
    assert {"integrity","unobserved_evidence"} <= set(verdict.failures)


def test_isolated_semantic_interface_and_triage():
    c,s=claim_for(),chain()
    payload=semantic_payload(c,s)
    assert not {"confidence","severity","model_version","reasoning"} & payload.keys()
    verifier=ScriptedSemanticVerifier()
    verdict=verifier.verify(payload)
    checks=hypothesis().required_checks
    assert triage(verify(c),verdict,checks=checks,required_checks=checks)[0] == "SURFACE_TO_ANALYST"
    assert triage(verify(c),verdict,checks=checks,required_checks=checks,missing=("payment_source",))[0] == "HUMAN_REVIEW_REQUIRED"
    payload["statement"]="Actor committed fraud"
    assert verifier.verify(payload).label == "INSUFFICIENT_EVIDENCE"
