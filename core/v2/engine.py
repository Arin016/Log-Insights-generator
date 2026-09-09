"""One-family end-to-end investigation with externally supervised execution."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import time

from pydantic import Field

from .contracts import StrictModel, SourceRecord, Scope, Hypothesis, SemanticVerdict, canonical_json, digest
from .provenance import Snapshot, reference
from .graph import build_graph
from .gateway import Gateway, Capability, MemoryBackend, Query
from .capsules import build_capsule
from .control import Budgets, Meter, StateMachine, Exhausted, supervised
from .ledger import RunLedger, code_identity
from .models import ScriptedInvestigator, OllamaAdapter, ModelTurn, ProposalTurn, compile_proposals, proposal_schema, local_payload, LOCAL_CONTEXT_TOKENS, FIELDS, INVESTIGATOR_PROMPT, SEMANTIC_PROMPT
from .security import detect
from .verification import verify_claim, contradiction_ids, semantic_payload, validate_semantic_references, ScriptedSemanticVerifier, triage


class HarnessConfig(StrictModel):
    name: str = "v2"
    representation: str = "hybrid"
    graph: bool = True
    contradiction: bool = True
    semantic: bool = True
    selective: bool = True
    defenses: bool = True
    coverage: bool = True
    drill_down: bool = True
    initial: str = "seeds"
    verification: str = "v2"
    row_limit: int = Field(default=32,gt=0,le=1000)
    capsule_rows: int = Field(default=128,gt=0,le=1000)
    capsule_bytes: int = Field(default=300000,gt=0)
    budgets: Budgets = Budgets()
    adapter: str = "scripted"
    model: str = "scripted-investigator-2.0"
    verifier_model: str = "scripted-semantic-2.0"
    model_url: str = "http://127.0.0.1:11434"
    model_digest: str | None = None
    verifier_digest: str | None = None
    spending_ledger: str | None = None


def load_hypothesis():
    root=Path(__file__).resolve().parents[2]
    return Hypothesis.model_validate_json((root/"applications/sap/hypotheses/vendor_bank_change_payment.v2.json").read_text())


def _execute(records,scope,missing_sources,config,intervention,es,run_id,emit):
    config=HarnessConfig.model_validate(config)
    meter=Meter(config.budgets,emit); machine=StateMachine(emit)
    claims=[]; decisions=[]; validations=[]; semantic_results=[]; capsules=[]; retrieved={}; observed={}
    investigation_incomplete=False; investigation_termination=None
    try:
        machine.transition("INGESTED")
        snapshot=Snapshot([SourceRecord.model_validate(r) for r in records],Scope.model_validate(scope),missing_sources)
        snapshot.verify(); hypothesis=load_hypothesis()
        machine.transition("SCOPE_VALIDATED")
        if config.defenses:
            flags=detect(snapshot.events)
            if flags:
                emit({"kind":"security","flags":flags}); machine.transition("UNSAFE_INPUT")
                return {"state":machine.state,"claims":[],"decisions":[],"partial":True,"counts":dict(meter.counts)}
        cap=Capability(scope=snapshot.scope,snapshot=snapshot.id,row_limit=config.row_limit,
            run_id=run_id,expires_monotonic=meter.started+config.budgets.wall_seconds)
        backend=None
        if es:
            from .elasticsearch import ESBackend
            backend=ESBackend(es["url"],es["index"])
        gateway=Gateway(snapshot,cap,backend)
        def query(raw,purpose="tool_queries"):
            meter.charge("tool_calls");meter.charge(purpose)
            emit({"kind":"tool_request","purpose":purpose,"request":raw})
            try:
                if intervention.get("fault")=="error": raise RuntimeError("synthetic injected tool failure")
                if intervention.get("fault")=="timeout": time.sleep(config.budgets.wall_seconds+2)
                result=gateway.query(raw)
                meter.charge("observed_rows",result["returned_count"])
                meter.charge("rows",result["returned_count"])
                meter.charge("bytes",len(canonical_json(result).encode()))
                for row in result["rows"]:
                    event=snapshot.by_id[row["event_id"]]
                    observed[event.event_id]=event
                    retrieved.setdefault(event.event_id,set()).add(result["query_id"])
                emit({"kind":"tool_result","purpose":purpose,"response":result})
                return result
            except Exception as exc:
                meter.charge("errors")
                emit({"kind":"tool_error","error":type(exc).__name__+": "+str(exc)})
                raise
        def pages(raw,purpose):
            out=[]
            while True:
                result=query(raw,purpose);out.extend(snapshot.by_id[e["event_id"]] for e in result["rows"])
                if not result["truncated"]:return out,False
                if not result["next_cursor"]:return out,True
                raw=raw|{"cursor":result["next_cursor"]}
        # Initial context is a deterministic view of the pinned snapshot. Its rows/bytes are counted.
        initial=list(snapshot.events) if config.initial=="full" else [e for e in snapshot.events if
            e.event_type in ({"BANK_CHANGE","INVOICE","PAYMENT"} if config.initial=="scoped" else {"BANK_CHANGE"})]
        # ES runs retrieve these IDs through the same gateway; no source bypass for model-visible context.
        initial_events=[]; initial_incomplete=False
        for i in range(0,len(initial),32):
            fetched,incomplete=pages({"template":"events_by_ids","event_ids":[e.event_id for e in initial[i:i+32]]},"initial_queries")
            initial_events.extend(fetched);initial_incomplete |= incomplete
        graph=build_graph(snapshot, None if config.graph else [])
        def capsule(events):
            cap=build_capsule(snapshot,hypothesis,events,representation=config.representation,
                row_budget=config.capsule_rows,byte_budget=config.capsule_bytes,token_budget=config.capsule_bytes,
                query_metadata=[{k:v for k,v in entry.get("response",{}).items() if k!="rows"} for entry in gateway.trace],
                defenses=config.defenses,graph_enabled=config.graph)
            capsules.append(cap.model_dump(mode="json"));emit({"kind":"capsule","capsule":capsules[-1]})
            return cap
        current=capsule(initial_events)
        machine.transition("CAPSULE_READY"); machine.transition("INVESTIGATING")
        if config.adapter in {"scripted","rules"}:
            model=ScriptedInvestigator(tools=config.drill_down,fault=intervention.get("model_fault"))
            verifier=ScriptedSemanticVerifier()
        elif config.adapter=="ollama":
            model=OllamaAdapter(config.model_url,config.model,config.budgets.wall_seconds,config.model_digest)
            verifier=OllamaAdapter(config.model_url,config.verifier_model,config.budgets.wall_seconds,config.verifier_digest)
        elif config.adapter=="anthropic":
            from .anthropic_adapter import ClaudeAdapter
            model=ClaudeAdapter(config.model,config.budgets.wall_seconds,config.spending_ledger,run_id)
            verifier=ClaudeAdapter(config.verifier_model,config.budgets.wall_seconds,config.spending_ledger,run_id)
        else: raise ValueError("unknown model adapter")
        def model_call(payload,purpose,semantic=False):
            if config.adapter=="rules":
                meter.charge("rule_evaluations")
                return model.respond(payload)[0]
            meter.charge("model_calls");meter.charge(purpose)
            size=len(canonical_json(payload).encode())
            # Conservative UTF-8-byte reservation; never presented as measured tokenizer usage.
            meter.charge("token_upper_bound",size+config.budgets.output_bytes_per_call)
            emit({"kind":"model_request","purpose":purpose,"payload":payload,
                  "provider_payload":local_payload(payload) if config.adapter in {"ollama","anthropic"} else None})
            if semantic and config.adapter=="scripted":
                raw=verifier.verify(payload).model_dump_json();usage=None
            elif semantic: raw,usage=verifier.semantic(payload)
            else:raw,usage=model.respond(payload)
            output_size=len(raw.encode())
            meter.charge("model_output_bytes",output_size)
            if output_size>config.budgets.output_bytes_per_call: raise Exhausted("model_output_bytes")
            if usage:
                if all(usage.get(key) is not None for key in ("input_tokens","output_tokens")):
                    meter.charge("usage_reported_calls")
                for key in ("input_tokens","output_tokens"):
                    if usage.get(key) is not None: meter.charge(key,usage[key])
                if usage.get("cost_microusd") is not None:meter.charge("cost_microusd",usage["cost_microusd"])
            emit({"kind":"model_response","purpose":purpose,"output":raw,"usage":usage})
            if config.adapter=="anthropic" and usage and (usage["stop_reason"]!="end_turn" or usage["provider_model"] not in {config.model,config.verifier_model}):
                raise ValueError("Claude incomplete/refused response or unexpected model; usage recorded")
            return raw
        observation=None; purpose="initial_calls"; investigator_queries=set()
        while True:
            payload={"capsule":current.model_dump(mode="json"),"hypothesis":hypothesis.model_dump(mode="json"),
                "query_schema":Query.model_json_schema(),"claim_schema":proposal_schema(config.drill_down) if config.adapter in {"ollama","anthropic"} else ModelTurn.model_json_schema(),
                "tools_allowed":config.drill_down,
                "evidence_queries":{key:sorted(value) for key,value in retrieved.items()},"observation":observation}
            raw=model_call(payload,purpose)
            try:
                if config.adapter in {"ollama","anthropic"}:
                    turn=compile_proposals(ProposalTurn.model_validate_json(raw),snapshot,graph,retrieved,
                                           config.model,config.graph)
                else:turn=ModelTurn.model_validate_json(raw)
            except ValueError as exc:
                # Validation detail is observable; do not include private model reasoning.
                detail=exc.errors(include_input=False,include_url=False) if hasattr(exc,"errors") else [{"msg":str(exc)}]
                detail=[{"loc":list(e.get("loc",())),"msg":e["msg"],"type":e.get("type","value_error")} for e in detail]
                emit({"kind":"schema_error","errors":detail})
                meter.charge("errors");meter.charge("repairs");purpose="repair_calls"
                observation={"schema_error":"Return a valid object matching claim_schema; final requires query null.","errors":detail}
                continue
            if turn.action=="final":
                meter.charge("finalization_calls")
                claims=[c.model_copy(update={"mandatory_checks":hypothesis.required_checks}) for c in turn.claims];break
            if not config.drill_down: raise PermissionError("single-pass harness cannot query tools")
            request=turn.query.model_dump(exclude_none=True)
            request_signature=digest(request)
            before=set(observed)
            observation=query(request,"investigator_queries")
            new_evidence=sorted(set(observed)-before)
            repeated=request_signature in investigator_queries
            investigator_queries.add(request_signature)
            # Missing sources can never be recovered through this snapshot-bound capability.
            # Likewise, replaying an identical query that contributes no new evidence is not
            # useful investigation. Terminate deterministically instead of spending the model
            # budget until EXPIRED; coverage policy below routes the incomplete run to review.
            if not new_evidence and (snapshot.missing_sources or repeated):
                reason="missing_source_no_progress" if snapshot.missing_sources else "repeated_query_no_progress"
                investigation_incomplete=True
                investigation_termination={
                    "reason":reason,
                    "query_signature":request_signature,
                    "missing_sources":list(snapshot.missing_sources),
                    "new_evidence_count":0,
                }
                emit({"kind":"investigation_termination",**investigation_termination})
                claims=[]
                break
            current=capsule(observed.values());purpose="continuation_calls"
        # The candidate is now immutable; later deterministic evidence additions are separately traced.
        machine.transition("CLAIMS_PROPOSED")
        emit({"kind":"candidate_claims","claims":[c.model_dump(mode="json") for c in claims]})
        machine.transition("STRUCTURAL_VERIFICATION")
        for claim in claims:
            if config.verification=="v2":
                val=verify_claim(claim,snapshot,graph,hypothesis,retrieved,graph_enabled=config.graph)
            else:
                from .verification import Validation
                exists=all(ref.event_id in snapshot.by_id for ref in claim.supporting_evidence)
                val=Validation(valid=exists if config.verification=="existence" else True,checks=(),
                               failures=() if exists else ("event_existence",))
            validations.append(val)
        emit({"kind":"structural_verdicts","verdicts":[v.model_dump() for v in validations]})
        machine.transition("SEMANTIC_VERIFICATION")
        incomplete=initial_incomplete or current.truncated or investigation_incomplete
        enriched=[]; contradictions=[]
        for claim,val in zip(claims,validations):
            found=[]; query_partial=False
            if config.contradiction and val.valid:
                for obj in claim.object_ids:
                    rows,partial=pages({"template":"contradictions_by_object","value":obj},"contradiction_queries")
                    found.extend(rows); query_partial |= partial
            ids=contradiction_ids(claim,found)
            contradictions.append(ids)
            references=tuple(reference(snapshot.by_id[eid],FIELDS,sorted(retrieved[eid])[0],"contradicts") for eid in ids)
            claim=claim.model_copy(update={"contradicting_evidence":references})
            enriched.append(claim);incomplete |= query_partial
            if val.valid and config.semantic:
                raw=model_call(semantic_payload(claim,snapshot),"verifier_calls",True)
                sem=validate_semantic_references(SemanticVerdict.model_validate_json(raw),claim)
            else:
                sem=SemanticVerdict(label="INSUFFICIENT_EVIDENCE",reasons=("disabled or structural rejection",),evidence_ids=(),uncertainty="HIGH")
            semantic_results.append(sem)
        claims=enriched
        emit({"kind":"semantic_verdicts","verdicts":[v.model_dump() for v in semantic_results]})
        machine.transition("COVERAGE_CHECK")
        # Any unconsumed gateway page remains observable and blocks normal completion.
        for entry in gateway.trace:
            response=entry.get("response",{})
            cursor=response.get("next_cursor")
            if response.get("truncated") and (not cursor or not any(e["request"].get("cursor")==cursor for e in gateway.trace)):
                incomplete=True
        for claim,val,sem,contradiction in zip(claims,validations,semantic_results,contradictions):
            checks=set(val.checks)
            if config.contradiction and val.valid:checks.add("contradiction_search")
            if not incomplete:checks.add("query_completeness")
            if not snapshot.missing_sources:checks.add("source_completeness")
            if sem.label=="SUPPORTED":checks.add("semantic_support")
            required=set(hypothesis.required_checks)
            if not config.contradiction:required.discard("contradiction_search")
            if not config.coverage:required -= {"query_completeness","source_completeness"}
            if config.verification!="v2":
                state="SURFACE_TO_ANALYST" if val.valid else "ABSTAINED";reasons=("baseline_policy",)
            else:
                state,reasons=triage(val,sem,checks=checks,required_checks=required,
                    contradictions=contradiction,missing=snapshot.missing_sources if config.coverage else (),
                    truncated=incomplete if config.coverage else False,selective=config.selective,semantic_enabled=config.semantic)
                if claim.unknowns and state=="SURFACE_TO_ANALYST":
                    state,reasons="HUMAN_REVIEW_REQUIRED",("unresolved_claim_unknowns",)
            decisions.append({"claim_id":claim.claim_id,"state":state,"reasons":reasons,
                              "checks":sorted(checks),"support_label":sem.label,"severity":claim.severity})
        machine.transition("POLICY_DECISION")
        if config.coverage and (incomplete or snapshot.missing_sources):
            state="HUMAN_REVIEW_REQUIRED"
        elif any(d["state"]=="HUMAN_REVIEW_REQUIRED" for d in decisions):state="HUMAN_REVIEW_REQUIRED"
        elif any(d["state"]=="SURFACE_TO_ANALYST" for d in decisions):state="SURFACE_TO_ANALYST"
        else:state="ABSTAINED"
        machine.transition(state)
        return {"state":state,"claims":[c.model_dump(mode="json") for c in claims],"decisions":decisions,
            "structural":[v.model_dump() for v in validations],"semantic":[v.model_dump() for v in semantic_results],
            "retrieved_event_ids":sorted(observed),"graph":graph.model_dump(mode="json") if config.graph else None,
            "partial":bool(incomplete or snapshot.missing_sources),"counts":dict(meter.counts),
            "investigation_termination":investigation_termination,
            "tokens_measured":config.adapter in {"ollama","anthropic"},
            "cost_usd":meter.counts["cost_microusd"]/1e6 if config.adapter=="anthropic" else None}
    except (Exhausted,TimeoutError) as exc:
        machine.transition("EXPIRED")
        return {"state":"EXPIRED","claims":[],"decisions":[],"partial":True,"counts":dict(meter.counts),
                "retrieved_event_ids":sorted(observed),"failure":str(exc)}
    except Exception as exc:
        machine.transition("FAILED")
        return {"state":"FAILED","claims":[],"decisions":[],"partial":True,"counts":dict(meter.counts),
                "retrieved_event_ids":sorted(observed),"failure":type(exc).__name__+": "+str(exc)}


def run_case(snapshot,config,output_root,*,dataset_hash="unit-fixture",intervention=None,es=None,cancel=None,identity=None):
    hypothesis=load_hypothesis()
    decoding={"temperature":0,"seed":20260905,"num_predict":2048,"think":False,"num_ctx":LOCAL_CONTEXT_TOKENS}
    if config.adapter=="anthropic":
        decoding={"temperature":"provider_default" if config.model=="claude-sonnet-5" else 0,
                  "seed":None,"max_tokens":2048,"thinking":"disabled","prompt_caching":False,"automatic_retries":False}
    manifest={"code":identity or code_identity(),"dataset_hash":dataset_hash,"snapshot":snapshot.id,
        "parser":"synthetic-canonical-2.0.0","contract_hash":digest(hypothesis),"contract":hypothesis.model_dump(mode="json"),
        "prompt_hashes":{"investigator":digest(INVESTIGATOR_PROMPT),"semantic":digest(SEMANTIC_PROMPT)},
        "tool_schema":Query.model_json_schema(),"config":config.model_dump(mode="json"),"es":es,
        "model":{"provider":config.adapter,"version":config.model,"verifier":config.verifier_model,
                 "decoding":decoding,
                 "digest":config.model_digest,"verifier_digest":config.verifier_digest,
                 "scripted_only":config.adapter in {"scripted","rules"}},
        "disclosure":"newly-generated-synthetic-only","intervention":intervention or {}}
    ledger=RunLedger(output_root,manifest)
    inputs={"records":[json.loads(e.raw_json) for e in snapshot.events],"scope":snapshot.scope.model_dump(),
            "missing_sources":snapshot.missing_sources}
    ledger.write("input.json",inputs|{"deduplicated_source_rows":snapshot.duplicate_count})
    try:
        result=supervised(_execute,inputs|{"config":config.model_dump(mode="json"),"intervention":intervention or {},
            "es":es,"run_id":ledger.run_id},config.budgets.wall_seconds,ledger.append,cancel)
        ledger.write("report.json",result)
    finally:ledger.seal()
    return result,ledger.path
