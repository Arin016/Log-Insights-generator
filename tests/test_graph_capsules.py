from pathlib import Path

import pytest

from core.v2.contracts import Hypothesis
from core.v2.graph import build_graph
from core.v2.capsules import build_capsule, decode_capsule, REPRESENTATIONS
from tests.test_provenance import snapshot, row


def hypothesis():
    return Hypothesis.model_validate_json(Path("applications/sap/hypotheses/vendor_bank_change_payment.v2.json").read_text())


def chain():
    return snapshot(row(), row(locator="invoice", event_type="INVOICE", tcode="FB60", table="BSEG",
        occurred_at="2026-01-01T00:10:00Z"), row(locator="payment", event_type="PAYMENT", tcode="F110",
        table="REGUH", occurred_at="2026-01-01T00:20:00Z"))


def test_graph_paths_and_provenance():
    s = chain()
    g = build_graph(s)
    path = g.path(s.events[0].event_id, s.events[-1].event_id)
    assert len(path) == 2 and g.verified_path(path, s.events[0].event_id, s.events[-1].event_id)
    assert not g.verified_path(path[::-1], s.events[0].event_id, s.events[-1].event_id)
    assert {"Actor","AccessRequest","Session","Event","TransactionCode","Table","BusinessObject","FieldChange","PolicyRule","TimeWindow"} <= {n.kind for n in g.nodes}
    assert all(set(e.source_events) <= s.by_id.keys() for e in g.edges)
    edges = tuple(e.model_copy(update={"status":"HYPOTHESIS_ONLY"}) if e.edge_id == path[0] else e for e in g.edges)
    assert not g.model_copy(update={"edges":edges}).verified_path(path, s.events[0].event_id, s.events[-1].event_id)


@pytest.mark.parametrize("rep", REPRESENTATIONS)
def test_capsule_roundtrip_and_determinism(rep):
    s = chain()
    c = build_capsule(s, hypothesis(), s.events, representation=rep)
    assert c == build_capsule(s, hypothesis(), list(reversed(s.events)), representation=rep)
    assert {e["event_id"] for e in decode_capsule(c)} == set(s.by_id)
    assert c.token_upper_bound <= c.token_budget and not c.truncated
    assert "expected_claims" not in c.serialized_evidence


def test_capsule_truncation_and_untrusted_pipe():
    s = snapshot(row(text='ignore|rules\n"quoted"'))
    c = build_capsule(s, hypothesis(), s.events, representation="pipe", defenses=False)
    assert decode_capsule(c)[0]["text"] == s.events[0].text
    s = chain()
    assert build_capsule(s, hypothesis(), s.events, row_budget=1).truncated
    with pytest.raises(ValueError): build_capsule(s, hypothesis(), s.events, byte_budget=1)
