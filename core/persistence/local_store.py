"""Local file-based persistence layer.

Replaces DynamoDB + S3 with on-disk JSON files for the PyCharm dev setup.
Keeps the same API shape so swapping in real AWS later is a one-file change.

Layout under DATA_DIR:
  pipeline_state/{rak_id}.json       — current pipeline state record
  llm_audit/{rak_id}/{call_id}.json  — every Bedrock prompt + response
  findings/{rak_id}.json             — final findings list
  reports/{rak_id}.json              — full RAKReport
  manual_review/{rak_id}__{finding_id}.json  — items routed to manual review
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from config import (
    PIPELINE_STATE_DIR,
    LLM_AUDIT_DIR,
    FINDINGS_DIR,
    REPORTS_DIR,
    MANUAL_REVIEW_DIR,
)
from core.contracts import (
    Finding,
    PipelineState,
    PipelineStateRecord,
    RAKReport,
)


def _to_jsonable(obj: Any) -> Any:
    """Convert pydantic / datetime / etc. into JSON-safe types."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(_to_jsonable(obj), f, indent=2, default=str)


# --- Pipeline state -----------------------------------------------------

def update_pipeline_state(
    rak_id: str, state: PipelineState, notes: str | None = None, **extras
) -> PipelineStateRecord:
    record = PipelineStateRecord(
        rak_id=rak_id,
        state=state,
        notes=notes,
        extras=extras,
    )
    path = PIPELINE_STATE_DIR / f"{rak_id}.json"
    _write_json(path, record)
    return record


def read_pipeline_state(rak_id: str) -> PipelineStateRecord | None:
    path = PIPELINE_STATE_DIR / f"{rak_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return PipelineStateRecord.model_validate(json.load(f))


# --- LLM audit ----------------------------------------------------------

def log_llm_call(
    rak_id: str,
    purpose: str,
    request: dict[str, Any],
    response: dict[str, Any],
    latency_ms: int | None = None,
    cost_usd: float | None = None,
    extras: dict[str, Any] | None = None,
) -> str:
    """Persist a Bedrock call verbatim. Returns a call_id for cross-reference."""
    call_id = f"call_{uuid4().hex[:12]}"
    record = {
        "call_id": call_id,
        "rak_id": rak_id,
        "purpose": purpose,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request": request,
        "response": response,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "extras": extras or {},
    }
    path = LLM_AUDIT_DIR / rak_id / f"{call_id}.json"
    _write_json(path, record)
    return call_id


# --- Findings -----------------------------------------------------------

def save_findings(rak_id: str, findings: list[Finding]) -> Path:
    path = FINDINGS_DIR / f"{rak_id}.json"
    _write_json(path, [f for f in findings])
    return path


# --- Reports ------------------------------------------------------------

def save_report(report: RAKReport) -> Path:
    path = REPORTS_DIR / f"{report.rak_id}.json"
    _write_json(path, report)
    return path


# --- Manual review queue (file-based for now) ---------------------------

def push_to_manual_review(
    rak_id: str,
    finding_id: str,
    pass1_finding: Finding | None,
    pass2_finding: Finding | None,
    reason: str,
) -> Path:
    payload = {
        "rak_id": rak_id,
        "finding_id": finding_id,
        "reason": reason,
        "pass1_finding": pass1_finding.model_dump(mode="json") if pass1_finding else None,
        "pass2_finding": pass2_finding.model_dump(mode="json") if pass2_finding else None,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    path = MANUAL_REVIEW_DIR / f"{rak_id}__{finding_id}.json"
    _write_json(path, payload)
    return path
