import json

import pytest

from applications.sap.parser import parse_log_line
from core.scoping.filter_engine import apply_use_case_filter
from core.v2.control import Budgets
from core.v2.engine import HarnessConfig,run_case
from core.v2.models import ModelTurn,OllamaAdapter
from core.v2.security import detect
from tests.test_baseline import synthetic_line
from tests.test_engine import generated


@pytest.mark.parametrize("detail",["[]","null","42",'"scalar"'])
def test_parser_nonobject_json_does_not_crash(detail):
    line=synthetic_line().rsplit("|",1)[0]+"|"+detail
    assert parse_log_line(line).attributes["field"] is None


def test_pipe_inside_json_and_utc():
    line=synthetic_line().replace("SYNTH-B","SYNTH|B")
    event=parse_log_line(line)
    assert event.attributes["new_val"]=="SYNTH|B"
    assert event.timestamp_utc.utcoffset().total_seconds()==0


@pytest.mark.parametrize("rules",[[{}],[{"unknown":[]}],[{"operation_matches":[] }],
    [{"deviation_flagged":"false"}],[{"operation_matches":["*"]},{"unknown":["x"]}]])
def test_filter_rejects_invalid_rules_on_empty_input(rules):
    with pytest.raises(ValueError):apply_use_case_filter([],{"scope_filter":{"match_any":rules}})


def test_model_schema_rejects_shell_and_scope():
    for query in ({"template":"shell","command":"whoami"},{"template":"seed_events","tenant":"foreign"}):
        with pytest.raises(ValueError):ModelTurn.model_validate({"action":"tool_call","query":query})
    with pytest.raises(ValueError):OllamaAdapter("http://example.com","model")


def test_split_injection_and_normal_utility():
    assert detect(generated("injection_split")[0].events)
    assert not detect(generated("positive")[0].events)


def test_tool_timeout_preserves_partial_trace(tmp_path):
    s,_,_=generated("positive")
    result,path=run_case(s,HarnessConfig(budgets=Budgets(wall_seconds=.5)),tmp_path,
        intervention={"fault":"timeout"})
    assert result["state"]=="EXPIRED" and result["supervisor"]["worker_terminated"]
    trace=(path/"trace.jsonl").read_text()
    assert '"tool_request"' in trace and '"EXPIRED"' in trace
