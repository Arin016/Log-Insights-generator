import json

import pytest

from core.v2.engine import _execute,HarnessConfig
from eval.configurations import configurations
from eval.metrics import ratio,case_metrics,aggregate
from eval.runner import freeze,checked_manifest
from eval.synthetic import generate
from tests.test_engine import generated


def test_metric_denominators_and_false_positive():
    s,label,intervention=generated("authorized")
    config=next(c for c in configurations() if c.name=="rules")
    report=_execute([json.loads(e.raw_json) for e in s.events],s.scope.model_dump(),s.missing_sources,
        config.model_dump(),intervention,None,"test",lambda _:None)
    report["supervisor"]={"elapsed_seconds":0}
    metrics=case_metrics(report,label,s)
    assert metrics["fp"]==1 and metrics["metrics"]["atomic_claim_precision"]==ratio(0,1)
    assert report["counts"].get("model_calls",0)==0
    assert ratio(0,0)["value"] is None
    assert aggregate([metrics])["metrics"]["citation_existence_precision"]==ratio(2,2)


def test_configs_cover_requirements():
    configs={c.name:c for c in configurations()}
    assert len(configs)==18
    assert configs["naive_single_pass"].drill_down is False
    assert configs["demo_style_react"].verification=="existence"
    assert configs["v2_no_graph"].graph is False


def test_manifest_tamper_and_exclusive_freeze(tmp_path):
    dataset=tmp_path/"data";generate(dataset,groups=2)
    path=tmp_path/"protocol.json"
    freeze(dataset,path)
    with pytest.raises(FileExistsError):freeze(dataset,path)
    file=next(dataset.glob("*/input.json"));file.write_text("{}")
    with pytest.raises(ValueError):checked_manifest(dataset)
