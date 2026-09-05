from pathlib import Path

import pytest
from pydantic import ValidationError

from core.v2.contracts import SourceRecord, Scope, CanonicalEvent, Hypothesis
from core.v2.provenance import Snapshot


def row(**overrides):
    fields = dict(locator="synthetic-row-1", tenant="synthetic-tenant", request="synthetic-request",
        session="synthetic-session", actor="synthetic-actor", occurred_at="2026-01-01T00:00:00Z",
        ingested_at="2026-01-01T00:01:00Z", event_type="BANK_CHANGE", tcode="XK02",
        table="LFBK", object_id="synthetic-vendor", field="BANKN", old_value="SYNTH-A", new_value="SYNTH-B")
    fields.update(overrides)
    return SourceRecord(**fields)


def snapshot(*rows, missing=()):
    return Snapshot(list(rows or [row()]), Scope(tenant="synthetic-tenant", request="synthetic-request"), missing)


def test_stable_hashes_order_and_duplicates():
    a, b = row(), row(locator="synthetic-row-2")
    x, y = snapshot(a, b), snapshot(b, a, a)
    assert x.id == y.id and x.events == y.events
    assert y.duplicate_count == 1
    x.verify()
    assert snapshot(a.model_copy(update={"new_value": "SYNTH-C"})).id != snapshot(a).id


def test_immutability_and_conflicts():
    s = snapshot()
    with pytest.raises(TypeError): s.id = "other"
    with pytest.raises(TypeError): s.by_id["other"] = s.events[0]
    with pytest.raises(ValidationError): s.events[0].actor = "other"
    with pytest.raises(ValueError): snapshot(row(), row(new_value="other"))
    with pytest.raises(ValueError): snapshot(row(tenant="another-tenant"))


def test_hash_tampering_and_strict_schema():
    e = snapshot().events[0].model_dump()
    e["new_value"] = "altered"
    with pytest.raises(ValidationError): CanonicalEvent(**e)
    with pytest.raises(ValidationError): row(occurred_at="2026-01-01T00:00:00")
    with pytest.raises(ValidationError): row(expected_answer="leak")


def test_hypothesis_is_complete():
    h = Hypothesis.model_validate_json(Path("applications/sap/hypotheses/vendor_bank_change_payment.v2.json").read_text())
    assert {"contradiction_search", "integrity", "semantic_support"} <= set(h.required_checks)
