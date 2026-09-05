"""Immutable contracts. No mutable nested log dictionaries enter the evidence plane."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical_json(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Scope(StrictModel):
    tenant: str = Field(min_length=1, max_length=120)
    request: str = Field(min_length=1, max_length=120)


class SourceRecord(StrictModel):
    """Entirely synthetic canonical source, not a claim of SAP format fidelity."""
    locator: str = Field(min_length=1, max_length=160)
    tenant: str
    request: str
    session: str
    actor: str
    occurred_at: str
    ingested_at: str
    source: Literal["synthetic_audit", "synthetic_policy"] = "synthetic_audit"
    event_type: Literal["BANK_CHANGE", "INVOICE", "PAYMENT", "APPROVAL", "REVERSAL", "DISPLAY"]
    tcode: str
    table: str
    object_id: str
    field: str = ""
    old_value: str = ""
    new_value: str = ""
    approved_operations: tuple[str, ...] = ("SE16",)
    status: Literal["POSTED", "PENDING", "REVERSED", "UNKNOWN"] = "POSTED"
    text: str = Field(default="", max_length=8192)

    @field_validator("occurred_at", "ingested_at")
    @classmethod
    def timestamp(cls, value):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timezone required")
        return dt.astimezone(timezone.utc).isoformat()

    @field_validator("locator", "tenant", "request", "session", "actor", "object_id", "tcode", "table")
    @classmethod
    def nonempty(cls, value):
        if not value or len(value) > 160 or any(ord(c) < 32 for c in value):
            raise ValueError("invalid identifier")
        return value


class CanonicalEvent(SourceRecord):
    event_id: str
    source_snapshot_id: str
    source_record_locator: str
    parser_version: Literal["synthetic-canonical-2.0.0"] = "synthetic-canonical-2.0.0"
    raw_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    raw_json: str
    trust_label: Literal["UNTRUSTED_LOG_DATA"] = "UNTRUSTED_LOG_DATA"

    @model_validator(mode="after")
    def verify_source(self):
        raw = SourceRecord.model_validate_json(self.raw_json)
        if digest(raw) != self.raw_content_hash:
            raise ValueError("raw hash mismatch")
        for name in SourceRecord.model_fields:
            if getattr(raw, name) != getattr(self, name):
                raise ValueError("derived/source mismatch: " + name)
        expected = "evt-" + digest([self.tenant, self.request, self.source, self.locator])[:24]
        if self.event_id != expected or self.source_record_locator != self.locator:
            raise ValueError("source identity mismatch")
        return self

    def visible(self, *, include_text=True):
        return self.model_dump(mode="json", exclude={"raw_json"} | (set() if include_text else {"text"}))


class Hypothesis(StrictModel):
    use_case: Literal["vendor_bank_change_payment"]
    version: str
    owner: str
    objective: str
    non_objectives: tuple[str, ...]
    allowed_sources: tuple[str, ...]
    seed_predicates: tuple[str, ...]
    required_checks: tuple[str, ...]
    optional_checks: tuple[str, ...]
    minimum_evidence: tuple[str, ...]
    benign_explanations: tuple[str, ...]
    contradiction_queries: tuple[str, ...]
    termination_criteria: tuple[str, ...]
    abstention_criteria: tuple[str, ...]
    severity_policy: str
    bank_tables: tuple[str, ...]
    bank_fields: tuple[str, ...]
    payment_tcodes: tuple[str, ...]
    window_seconds: int = Field(gt=0)


class EvidenceReference(StrictModel):
    event_id: str
    source_snapshot: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    fields: tuple[str, ...] = Field(min_length=1)
    value_hashes: tuple[str, ...]
    relation: Literal["supports", "contradicts", "context_only"]
    retrieved_by_query: str

    @model_validator(mode="after")
    def hashes_match_fields(self):
        if len(self.fields) != len(self.value_hashes) or len(set(self.fields)) != len(self.fields):
            raise ValueError("one hash per distinct field required")
        return self


class AtomicClaim(StrictModel):
    claim_id: str
    claim_type: Literal["BANK_CHANGE_BEFORE_PAYMENT"] = "BANK_CHANGE_BEFORE_PAYMENT"
    statement: str = Field(min_length=1, max_length=600)
    actor_ids: tuple[str, ...] = Field(min_length=1)
    session_ids: tuple[str, ...] = Field(min_length=1)
    object_ids: tuple[str, ...] = Field(min_length=1)
    start: str
    end: str
    supporting_evidence: tuple[EvidenceReference, ...] = Field(min_length=1, max_length=30)
    contradicting_evidence: tuple[EvidenceReference, ...] = ()
    relationship_path: tuple[str, ...] = ()
    mandatory_checks: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    prompt_version: str
    model_version: str


class SemanticVerdict(StrictModel):
    label: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    uncertainty: Literal["LOW", "HIGH"]


class Feedback(StrictModel):
    claim_id: str
    review_action: Literal["ACCEPT", "ADJUST", "REJECT", "INSUFFICIENT_DATA"]
    corrected_claim: AtomicClaim | None = None
    correct_supporting_event_ids: tuple[str, ...] = ()
    missing_evidence_event_ids: tuple[str, ...] = ()
    reason_code: str
    reviewer_role: str
    policy_version: str
    reviewed_at: str
