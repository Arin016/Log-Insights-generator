import json
import threading
import time

import pytest

from core.v2.control import Budgets, Meter, Exhausted, StateMachine, STATES, supervised
from core.v2.ledger import RunLedger, verify_ledger


def hanging(emit):
    emit({"kind":"accounting","counts":{"model_calls":1}})
    while True: time.sleep(.1)


def test_external_deadline_kills_blocked_worker():
    events=[]
    result=supervised(hanging,{},.5,events.append)
    assert result["state"]=="EXPIRED" and result["partial"]
    assert result["supervisor"]["worker_terminated"]
    assert result["supervisor"]["elapsed_seconds"]<1.5
    assert any(e["kind"]=="accounting" for e in events)


def test_cancellation():
    cancel=threading.Event(); cancel.set()
    assert supervised(hanging,{},2,lambda _:None,cancel)["state"]=="CANCELLED"


def test_state_transitions():
    machine=StateMachine(lambda _:None)
    with pytest.raises(ValueError): machine.transition("SURFACE_TO_ANALYST")
    for state in STATES: machine.transition(state)
    machine.transition("ABSTAINED")
    with pytest.raises(ValueError): machine.transition("INGESTED")


def test_meter_counts_all_and_reserves_before_work():
    meter=Meter(Budgets(model_calls=1,rows=1),lambda _:None)
    meter.charge("model_calls"); meter.charge("errors"); meter.charge("initial_calls")
    with pytest.raises(Exhausted): meter.charge("model_calls")
    assert meter.counts["model_calls"]==1 and meter.counts["errors"]==1


def test_immutable_ledger_and_tamper_detection(tmp_path):
    ledger=RunLedger(tmp_path,{"synthetic":True},run_id="one")
    ledger.append({"kind":"state","state":"INGESTED"}); ledger.write("report.json",{"state":"ABSTAINED"})
    ledger.seal()
    assert verify_ledger(ledger.path)
    with pytest.raises(FileExistsError): RunLedger(tmp_path,{},run_id="one")
    with pytest.raises(ValueError): ledger.write("other.json",{})
    file=ledger.path/"report.json"; file.chmod(0o644); file.write_text("{}")
    with pytest.raises(ValueError): verify_ledger(ledger.path)
