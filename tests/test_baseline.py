import json

import pytest

from applications.sap.parser import PIPE_FIELDS, parse_log_line
from applications.sap.catalogs import load_tcode_catalog, load_use_case, list_use_cases
from core.scoping.filter_engine import apply_use_case_filter
from core.verification.evidence_verifier import verify_finding
from core.contracts import Finding, ConfidenceFactors
from core.analyzers.kiro_client import extract_json


def synthetic_line():
    fields = dict(log_id="synthetic-event-1", request_id="synthetic-request-1",
                  session_id="synthetic-session-1", ff_id="synthetic-actor-1",
                  start_time_utc="20260101120000", log_type="CHANGE LOG",
                  transaction_code="XK02", requested_tcode="SE16",
                  tcode_deviation="YES", details=json.dumps({"Table": "LFBK",
                  "Field": "BANKN", "Old val": "SYNTH-A", "New val": "SYNTH-B",
                  "Cha.Ind.": "U", "Table Key": "synthetic-vendor-1"}))
    return "|".join(fields.get(k, "") for k in PIPE_FIELDS)


def test_parser_catalog_and_scope():
    event = parse_log_line(synthetic_line())
    assert event.attributes["new_val"] == "SYNTH-B"
    assert event.action_type == "UPDATE"
    assert load_tcode_catalog().category_for("XK02") == "master_data_modification"
    assert apply_use_case_filter([event], load_use_case("vendor_master_manipulation")) == [event]
    assert len(list_use_cases()) == 3


def test_parser_invalid_and_filter_unknown():
    assert parse_log_line("malformed") is None
    with pytest.raises(ValueError):
        apply_use_case_filter([parse_log_line(synthetic_line())], {"scope_filter": {"match_any": [{"unknown": []}]}})


def test_existence_does_not_prove_support():
    finding = Finding(rak_id="synthetic-request-1", use_case="vendor_master_manipulation",
        title="Unsupported payment claim", severity="HIGH", confidence=.99,
        confidence_factors=ConfidenceFactors(sufficient_context=True,
            unambiguous_evidence=True, pattern_clear=True, scope_unambiguous=True),
        evidence_event_ids=["synthetic-event-1"], affected_session_ids=["synthetic-session-1"],
        reasoning="A payment occurred (deliberately unsupported synthetic fixture).")
    assert verify_finding(finding, {"synthetic-event-1"}).is_valid
    assert not verify_finding(finding, set()).is_valid


def test_json_extraction():
    assert extract_json('```json\n{"action":"final","findings":[]}\n```')["action"] == "final"
    with pytest.raises(ValueError):
        extract_json("no structured output")
