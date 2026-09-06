from core.v2.models import Proposal,ProposalTurn,compile_proposals,proposal_schema
from core.v2.graph import build_graph
from core.v2.verification import verify_claim
from tests.test_graph_capsules import chain,hypothesis


def test_compiler_attaches_provenance_but_does_not_promote_wrong_identity():
    s=chain();bank,payment=s.events[0],s.events[-1]
    p=Proposal(bank_event_id=bank.event_id,payment_event_id=payment.event_id,actor_id="wrong-actor",
        session_id=bank.session,object_id=bank.object_id,statement="Bank changed before payment.")
    observed={e.event_id:{"q-1"} for e in s.events}
    claim=compile_proposals(ProposalTurn(action="final",proposals=(p,)),s,build_graph(s),observed,"local-test").claims[0]
    assert "identity" in verify_claim(claim,s,build_graph(s),hypothesis(),observed).failures
    assert claim.supporting_evidence[0].content_hash==bank.raw_content_hash


def test_compiler_does_not_promote_unobserved_graph_evidence():
    s=chain();bank,payment=s.events[0],s.events[-1]
    p=Proposal(bank_event_id=bank.event_id,payment_event_id=payment.event_id,actor_id=bank.actor,
        session_id=bank.session,object_id=bank.object_id,statement="Bank changed before payment.")
    observed={e.event_id:{"q-1"} for e in (bank,payment)}
    claim=compile_proposals(ProposalTurn(action="final",proposals=(p,)),s,build_graph(s),observed,"local-test").claims[0]
    assert "unobserved_path_evidence" in verify_claim(claim,s,build_graph(s),hypothesis(),observed).failures


def test_live_grammar_encodes_final_query_null():
    schema=proposal_schema(False)
    assert schema["properties"]["action"]["const"]=="final"
    assert schema["properties"]["query"]=={"type":"null"}
    branches=proposal_schema(True)["anyOf"]
    assert branches[0]["properties"]["proposals"]["maxItems"]==0


def test_semantic_verdict_cannot_cite_fabricated_or_incomplete_evidence():
    import pytest
    from core.v2.contracts import SemanticVerdict
    from core.v2.verification import validate_semantic_references
    from tests.test_verification import claim_for
    claim=claim_for()
    for ids in (("fabricated",),()):
        verdict=SemanticVerdict(label="SUPPORTED",reasons=("supported",),evidence_ids=ids,uncertainty="LOW")
        with pytest.raises(ValueError):validate_semantic_references(verdict,claim)
