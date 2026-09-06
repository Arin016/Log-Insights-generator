"""Explicit paid-Claude adapter: official endpoint, private credentials, shared budget."""
import json
import os
from pathlib import Path
import stat
from urllib.request import Request,build_opener,HTTPRedirectHandler,ProxyHandler
from urllib.error import HTTPError,URLError

from .contracts import canonical_json,digest
from .control import Exhausted
from .models import local_payload,proposal_schema,INVESTIGATOR_PROMPT,SEMANTIC_PROMPT
from .spending import SpendingLedger

# Standard global rates verified 2026-09-06 from Anthropic's pricing page.
# USD per million tokens equals integer micro-USD per token.
MODEL_RATES={"claude-haiku-4-5-20251001":{"input":1,"output":5,"max_input":200000},
             "claude-sonnet-5":{"input":2,"output":10,"max_input":1000000},
             "claude-sonnet-4-6":{"input":3,"output":15,"max_input":1000000}}
PRICE_SOURCE="https://platform.claude.com/docs/en/about-claude/pricing"
MAX_OUTPUT=2048


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise PermissionError("Claude API redirects refused")


class ProviderError(RuntimeError):pass


def private_key():
    path=Path(os.environ.get("FF_CLAUDE_KEY_FILE",str(Path(__file__).resolve().parents[2]/".runtime/anthropic_api_key")))
    if path.is_symlink():raise PermissionError("credential symlink refused")
    mode=path.stat().st_mode
    if not stat.S_ISREG(mode) or stat.S_IMODE(mode)&0o077:raise PermissionError("credential file must be private (mode 600)")
    with path.open() as f:key=f.read(512).strip()
    if not key.startswith("sk-ant-") or any(c.isspace() for c in key):raise ValueError("invalid credential configuration")
    return key


def supported_schema(value):
    """Remove unsupported decoder constraints, retaining strict Pydantic validation."""
    if isinstance(value,list):return [supported_schema(v) for v in value]
    if not isinstance(value,dict):return value
    removed={"minLength","maxLength","minimum","maximum","maxItems","title"}
    out={k:supported_schema(v) for k,v in value.items() if k not in removed}
    if out.get("minItems",0)>1:out["minItems"]=1
    if out.get("type")=="object":out["additionalProperties"]=False
    if out.get("type")=="array" and out.get("items")=={}:out["items"]={"type":"string"}
    return out


class ClaudeAdapter:
    def __init__(self,model,timeout,budget_path,run_id):
        if model not in MODEL_RATES:raise ValueError("Claude model requires verified price and capacity entry")
        self.model_version=model;self.timeout=timeout;self.budget=SpendingLedger(budget_path);self.run_id=run_id
        self._key=private_key()
        self._opener=build_opener(ProxyHandler({}),NoRedirect())

    def _call(self,payload,system,schema):
        payload=local_payload(payload)
        body={"model":self.model_version,"max_tokens":MAX_OUTPUT,"stream":False,
              "system":system,"messages":[{"role":"user","content":canonical_json(payload)}],
              "thinking":{"type":"disabled"},
              "output_config":{"format":{"type":"json_schema","schema":supported_schema(schema)}}}
        # Sonnet 5 does not accept sampling-parameter overrides. Freeze this distinction.
        if self.model_version!="claude-sonnet-5":body["temperature"]=0
        encoded=canonical_json(body).encode();rates=MODEL_RATES[self.model_version]
        if len(encoded)+4096+MAX_OUTPUT>min(100000,rates["max_input"]):raise Exhausted("claude_context_upper_bound")
        # Reserve the entire model input capacity, not an optimistic token estimate.
        # A killed worker leaves this reservation charged until independently reconciled.
        reserve=rates["max_input"]*rates["input"]+MAX_OUTPUT*rates["output"]
        ident=self.budget.reserve(reserve,self.run_id,self.model_version)
        req=Request("https://api.anthropic.com/v1/messages",data=encoded,
                    headers={"x-api-key":self._key,"anthropic-version":"2023-06-01","content-type":"application/json"})
        try:
            with self._opener.open(req,timeout=self.timeout) as response:
                raw=response.read(262145);request_id=response.headers.get("request-id")
            if len(raw)>262144:raise ProviderError("provider response exceeds byte limit")
            data=json.loads(raw)
        except HTTPError as exc:
            # Never serialize request headers, credentials or raw provider error bodies.
            # Definite validation/auth/rate-limit rejection has no generated-token charge.
            if exc.code in {400,401,403,404,413,429}:
                self.budget.settle(ident,0,{"http_status":exc.code,"generation_rejected":True})
            raise ProviderError("Claude HTTP "+str(exc.code)) from None
        except (URLError,TimeoutError):raise ProviderError("Claude transport failure; spending reservation retained") from None
        usage=data.get("usage",{})
        inputs=usage.get("input_tokens");outputs=usage.get("output_tokens")
        if not all(type(v) is int and v>=0 for v in (inputs,outputs)):
            raise ProviderError("Claude usage missing; spending reservation retained")
        if usage.get("cache_creation_input_tokens",0) or usage.get("cache_read_input_tokens",0):
            raise ProviderError("unexpected prompt caching; spending reservation retained")
        cost=inputs*rates["input"]+outputs*rates["output"]
        measured={"input_tokens":inputs,"output_tokens":outputs,"cost_microusd":cost,"cost_usd":cost/1e6,
                  "provider_model":data.get("model"),"provider_request_id":request_id,
                  "stop_reason":data.get("stop_reason"),"spending_reservation":ident,"request_payload_hash":digest(payload)}
        self.budget.settle(ident,cost,measured)
        text="".join(b["text"] for b in data.get("content",[]) if b.get("type")=="text")
        # Private reasoning blocks are discarded even if unexpectedly returned.
        return text,measured

    def respond(self,payload):return self._call(payload,INVESTIGATOR_PROMPT,proposal_schema(payload["tools_allowed"]))
    def semantic(self,payload):
        from .contracts import SemanticVerdict
        return self._call(payload,SEMANTIC_PROMPT,SemanticVerdict.model_json_schema())
