import os
import time

import pytest

from core.v2.elasticsearch import seed_dataset,ESBackend,validate_index_name,client
from core.v2.gateway import Gateway,Capability
from eval.synthetic import generate,load_case


@pytest.mark.parametrize("name",["ff_insights_events","*","ff-insights-synthetic-v2-*","unknown"])
def test_unknown_index_denied(name):
    with pytest.raises(PermissionError):validate_index_name(name)


def test_nonlocal_endpoint_denied():
    with pytest.raises(ValueError):client("https://example.com")


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("FF_ES_INTEGRATION")!="1",reason="opt-in dedicated local ES")
def test_real_elasticsearch_roundtrip_and_pagination(tmp_path):
    corpus=tmp_path/"data";manifest=generate(corpus,seed=909,groups=2)
    seeded=seed_dataset(corpus)
    assert seed_dataset(corpus)==seeded
    backend=ESBackend(seeded["url"],seeded["index"])
    for item in manifest["cases"]:
        s=load_case(corpus,item["case_id"])
        gateway=Gateway(s,Capability(scope=s.scope,snapshot=s.id,row_limit=2,
            run_id="integration",expires_monotonic=time.monotonic()+30),backend)
        for typ in ("BANK_CHANGE","PAYMENT"):
            ids=[e.event_id for e in s.events if e.event_type==typ]
            if not ids:continue
            query={"template":"events_by_ids","event_ids":ids};found=[]
            while True:
                response=gateway.query(query);found.extend(row["event_id"] for row in response["rows"])
                if not response["truncated"]:break
                query["cursor"]=response["next_cursor"]
            assert set(found)==set(ids)
    from core.v2.engine import run_case,HarnessConfig
    from core.v2.ledger import verify_ledger
    for category in ("positive","multihop","conflicting","missing_source"):
        item=next(c for c in manifest["cases"] if c["category"]==category)
        s=load_case(corpus,item["case_id"])
        report,path=run_case(s,HarnessConfig(),tmp_path/"runs",es={"url":seeded["url"],"index":seeded["index"]})
        expected="HUMAN_REVIEW_REQUIRED" if category=="missing_source" else "ABSTAINED" if category=="conflicting" else "SURFACE_TO_ANALYST"
        assert report["state"]==expected
        assert verify_ledger(path)
