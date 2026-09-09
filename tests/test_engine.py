import json

import pytest

from eval.synthetic import case
from core.v2.contracts import Scope,SourceRecord
from core.v2.provenance import Snapshot
from core.v2.engine import _execute,HarnessConfig,run_case
from core.v2.control import Budgets
from core.v2.ledger import verify_ledger


def generated(category):
    source,label,intervention=case(7,0,category,"development")
    snapshot=Snapshot([SourceRecord.model_validate(r) for r in source["records"]],Scope(**source["scope"]),source["missing_sources"])
    return snapshot,label,intervention


@pytest.mark.parametrize("category", ["positive","multihop","authorized","no_evidence","missing_source","conflicting",
    "duplicate_reordered","large","unseen","pending","wrong_actor","wrong_object","delayed","rollback","tool_error",
    "injection_conceal","injection_false_positive","injection_exfiltrate","injection_hijack","injection_exhaust",
    "injection_cross_scope","injection_split"])
def test_end_to_end_synthetic_strata(category):
    s,label,intervention=generated(category)
    result=_execute([json.loads(e.raw_json) for e in s.events],s.scope.model_dump(),s.missing_sources,
        HarnessConfig().model_dump(),intervention,None,"test",lambda _:None)
    assert result["state"]==label["expected_terminal"], result


def test_supervised_positive_ledger(tmp_path):
    s,_,_=generated("positive")
    result,path=run_case(s,HarnessConfig(),tmp_path)
    assert result["state"]=="SURFACE_TO_ANALYST",result
    assert verify_ledger(path)
    assert result["counts"]["initial_calls"]==1
    assert result["counts"]["verifier_calls"]==1
    assert result["counts"]["contradiction_queries"]>=1


def test_malformed_model_and_tiny_budget_expire(tmp_path):
    s,_,_=generated("positive")
    for config,intervention in [
        (HarnessConfig(budgets=Budgets(model_calls=0)),{}),
        (HarnessConfig(),{"model_fault":"malformed"}),
    ]:
        result,path=run_case(s,config,tmp_path,intervention=intervention)
        assert result["state"]=="EXPIRED" and result["partial"]
        assert verify_ledger(path)


def test_isolated_semantic_rejects_overclaim(tmp_path):
    s,_,_=generated("positive")
    result,_=run_case(s,HarnessConfig(),tmp_path,intervention={"model_fault":"overclaim"})
    assert result["state"]=="HUMAN_REVIEW_REQUIRED"


def test_repeated_query_without_new_evidence_terminates_before_budget_exhaustion():
    s,_,_=generated("positive")
    result=_execute([json.loads(e.raw_json) for e in s.events],s.scope.model_dump(),s.missing_sources,
        HarnessConfig().model_dump(),{"model_fault":"repeat_query"},None,"test",lambda _:None)
    assert result["state"]=="HUMAN_REVIEW_REQUIRED"
    assert result["partial"]
    assert result["investigation_termination"]["reason"]=="repeated_query_no_progress"
    assert result["counts"]["model_calls"]==2


def test_missing_source_no_progress_terminates_after_first_query():
    s,_,_=generated("missing_source")
    result=_execute([json.loads(e.raw_json) for e in s.events],s.scope.model_dump(),s.missing_sources,
        HarnessConfig().model_dump(),{"model_fault":"repeat_query"},None,"test",lambda _:None)
    assert result["state"]=="HUMAN_REVIEW_REQUIRED"
    assert result["partial"]
    assert result["investigation_termination"]["reason"]=="missing_source_no_progress"
    assert result["investigation_termination"]["missing_sources"]
    assert result["counts"]["model_calls"]==1
