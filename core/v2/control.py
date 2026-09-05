"""Observable states, resource reservations and a parent-process kill boundary."""
from __future__ import annotations

from collections import Counter
import multiprocessing
import os
import signal
import time

from pydantic import Field

from .contracts import StrictModel, canonical_json

STATES = ("INGESTED", "SCOPE_VALIDATED", "CAPSULE_READY", "INVESTIGATING", "CLAIMS_PROPOSED",
          "STRUCTURAL_VERIFICATION", "SEMANTIC_VERIFICATION", "COVERAGE_CHECK", "POLICY_DECISION")
TERMINALS = {"SURFACE_TO_ANALYST", "HUMAN_REVIEW_REQUIRED", "ABSTAINED", "FAILED", "EXPIRED", "CANCELLED", "UNSAFE_INPUT"}
FAULTS = {"FAILED", "EXPIRED", "CANCELLED", "UNSAFE_INPUT"}


class Budgets(StrictModel):
    wall_seconds: float = Field(default=10, gt=0, le=600)
    model_calls: int = Field(default=12, ge=0, le=100)
    tool_calls: int = Field(default=30, ge=0, le=300)
    repairs: int = Field(default=2, ge=0, le=10)
    rows: int = Field(default=1000, ge=0)
    bytes: int = Field(default=2000000, ge=0)
    token_upper_bound: int = Field(default=2000000, ge=0)
    output_bytes_per_call: int = Field(default=32768, gt=0)


class Exhausted(RuntimeError): pass


class StateMachine:
    def __init__(self, emit): self.state=None; self.emit=emit
    def transition(self, state):
        if self.state in TERMINALS: raise ValueError("terminal state cannot transition")
        expected = STATES[0] if self.state is None else STATES[STATES.index(self.state)+1] if self.state != STATES[-1] else None
        if state not in FAULTS and state != expected and not (self.state == STATES[-1] and state in TERMINALS):
            raise ValueError(f"invalid transition {self.state} -> {state}")
        self.state=state; self.emit({"kind":"state","state":state})


class Meter:
    def __init__(self,budgets,emit):
        self.budgets=budgets; self.emit=emit; self.counts=Counter(); self.started=time.monotonic()
    def charge(self,kind,count=1):
        limit = getattr(self.budgets,kind,None)
        if count < 0: raise ValueError("negative resource charge")
        if limit is not None and self.counts[kind]+count > limit: raise Exhausted(kind)
        if time.monotonic()-self.started >= self.budgets.wall_seconds: raise Exhausted("wall_seconds")
        self.counts[kind]+=count
        self.emit({"kind":"accounting","counts":dict(self.counts)})


def _child(connection, target, kwargs):
    os.setsid()
    def emit(value): connection.send(value)
    try:
        emit({"kind":"worker_started","pid":os.getpid()})
        result=target(emit=emit,**kwargs)
        emit({"kind":"result","result":result})
    except BaseException as exc:
        emit({"kind":"worker_failure","error":type(exc).__name__+": "+str(exc)})
    finally: connection.close()


def supervised(target, kwargs, seconds, on_event, cancel=None):
    """Parent owns deadline; terminates worker and its descendants without finalization.

    Deadline covers process startup and execution. Cleanup overhead is reported separately.
    The OS is not a real-time scheduler; tests measure observed overshoot.
    """
    ctx=multiprocessing.get_context("spawn")
    parent,child=ctx.Pipe(duplex=False)
    process=ctx.Process(target=_child,args=(child,target,kwargs),daemon=False)
    start=time.monotonic(); deadline=start+seconds
    process.start(); child.close()
    result=None; terminal=None; counts={}; events=[]
    try:
        while result is None and terminal is None:
            remaining=deadline-time.monotonic()
            if cancel is not None and cancel.is_set(): terminal="CANCELLED"; break
            if remaining <= 0: terminal="EXPIRED"; break
            if parent.poll(min(.02,remaining)):
                try: item=parent.recv()
                except EOFError: terminal="FAILED"; break
                events.append(item); on_event(item)
                if item["kind"]=="accounting": counts=item["counts"]
                elif item["kind"]=="result": result=item["result"]
                elif item["kind"]=="worker_failure": terminal="FAILED"
            elif not process.is_alive(): terminal="FAILED"
        decision_at=time.monotonic()
    finally:
        # The process group exists only after setsid; otherwise terminate just our child.
        if process.is_alive():
            try:
                if os.getpgid(process.pid)==process.pid: os.killpg(process.pid,signal.SIGKILL)
                else: process.kill()
            except ProcessLookupError: pass
        process.join(timeout=1)
        parent.close()
        if process.is_alive(): raise RuntimeError("worker failed to terminate")
    if terminal:
        item={"kind":"state","state":terminal,"reason":"parent deadline/cancellation/worker failure"}
        events.append(item); on_event(item)
        result={"state":terminal,"claims":[],"decisions":[],"partial":True,"counts":counts,
                "retrieved_event_ids":sorted({row["event_id"] for e in events if e["kind"]=="tool_result" for row in e["response"]["rows"]}),
                "failures":[e for e in events if e["kind"]=="worker_failure"]}
    result["supervisor"]={"elapsed_seconds":time.monotonic()-start,
        "decision_seconds":decision_at-start,"cleanup_seconds":time.monotonic()-decision_at,
        "deadline_seconds":seconds,"worker_terminated":not process.is_alive()}
    return result
