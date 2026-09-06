import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pytest

from core.v2.control import Exhausted
from core.v2.spending import SpendingLedger
from core.v2.anthropic_adapter import ClaudeAdapter,private_key,ProviderError,supported_schema


def test_provider_schema_inlines_refs_and_preserves_original_validation():
    from core.v2.models import proposal_schema,ProposalTurn
    converted=supported_schema(proposal_schema())
    assert '$defs' not in json.dumps(converted) and '$ref' not in json.dumps(converted)
    assert 'maxLength' not in json.dumps(converted)
    with pytest.raises(ValueError):ProposalTurn.model_validate({'action':'final','query':{'template':'seed_events'}})


def test_reservations_survive_reopen_and_cannot_reset(tmp_path):
    p=tmp_path/'spending.sqlite';b=SpendingLedger.initialize(p,500)
    call=b.reserve(400,'run','model')
    with pytest.raises(Exhausted):SpendingLedger(p).reserve(101,'run2','model')
    with pytest.raises(FileExistsError):SpendingLedger.initialize(p,1000)
    b.settle(call,20,{'input_tokens':20})
    assert b.snapshot()['measured_microusd']==20
    b.reserve(480,'run2','model')
    with pytest.raises(Exhausted):b.reserve(1,'run3','model')


def test_parallel_budget_reservations_are_serialized(tmp_path):
    p=tmp_path/'spending.sqlite';b=SpendingLedger.initialize(p,100)
    def request(_):
        try:SpendingLedger(p).reserve(60,'run','model');return True
        except Exhausted:return False
    with ThreadPoolExecutor(max_workers=4) as pool:assert sum(pool.map(request,range(4)))==1
    assert b.snapshot()['unresolved_reserved_microusd']==60


def test_credential_permissions_and_redaction(tmp_path,monkeypatch):
    key=tmp_path/'key';key.write_text('sk-ant-synthetic-test-only');key.chmod(0o644)
    monkeypatch.setenv('FF_CLAUDE_KEY_FILE',str(key))
    with pytest.raises(PermissionError):private_key()
    key.chmod(0o600)
    assert private_key().startswith('sk-ant-')


def test_claude_records_cost_and_discards_private_blocks(tmp_path,monkeypatch):
    key=tmp_path/'key';key.write_text('sk-ant-synthetic-test-only');key.chmod(0o600)
    monkeypatch.setenv('FF_CLAUDE_KEY_FILE',str(key))
    budget=SpendingLedger.initialize(tmp_path/'budget.sqlite',5_000_000)
    adapter=ClaudeAdapter('claude-haiku-4-5-20251001',2,budget.path,'synthetic-run')
    class Response(BytesIO):headers={'request-id':'synthetic-request'}
    class Fake:
        def open(self,request,timeout):
            body=json.loads(request.data)
            assert request.full_url=='https://api.anthropic.com/v1/messages'
            assert 'synthetic-test-only' not in request.data.decode()
            assert body['thinking']=={'type':'disabled'} and 'tools' not in body
            return Response(json.dumps({'model':adapter.model_version,'stop_reason':'end_turn',
                'content':[{'type':'thinking','thinking':'PRIVATE-TEST'},{'type':'text','text':'{}'}],
                'usage':{'input_tokens':100,'output_tokens':10}}).encode())
    adapter._opener=Fake()
    raw,usage=adapter._call({'evidence':[]},'system',{'type':'object','properties':{},'additionalProperties':False})
    assert raw=='{}' and usage['cost_microusd']==150
    snapshot=budget.snapshot()
    assert snapshot['measured_microusd']==150 and snapshot['unresolved_reserved_microusd']==0
    assert 'PRIVATE-TEST' not in json.dumps(snapshot) and 'sk-ant-' not in json.dumps(snapshot)


def test_network_ambiguity_keeps_reservation(tmp_path,monkeypatch):
    from urllib.error import URLError
    key=tmp_path/'key';key.write_text('sk-ant-synthetic-test-only');key.chmod(0o600)
    monkeypatch.setenv('FF_CLAUDE_KEY_FILE',str(key))
    budget=SpendingLedger.initialize(tmp_path/'budget.sqlite',5_000_000)
    adapter=ClaudeAdapter('claude-haiku-4-5-20251001',2,budget.path,'synthetic-run')
    class Fake:
        def open(self,*a,**kw):raise URLError('do not copy private transport details')
    adapter._opener=Fake()
    with pytest.raises(ProviderError,match='reservation retained'):adapter._call({},'system',{})
    assert budget.snapshot()['unresolved_reserved_microusd']==210240
