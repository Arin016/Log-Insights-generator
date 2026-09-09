"""Contracts for blinded human review; review evidence is not generator truth."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .contracts import StrictModel


ATTESTATION = "I did not access generator labels or other reviewers' annotations before completing this review."


class ReviewAnnotation(StrictModel):
    schema_version: Literal["ff-blinded-review-v1"] = "ff-blinded-review-v1"
    package_id: str = Field(pattern=r"^review-[a-f0-9]{16}$")
    case_id: str = Field(min_length=1, max_length=120)
    reviewer_id: str = Field(min_length=3, max_length=80)
    reviewer_role: str = Field(min_length=3, max_length=120)
    pattern_present: Literal["YES", "NO", "UNCERTAIN"]
    recommended_disposition: Literal[
        "SURFACE_TO_ANALYST", "HUMAN_REVIEW_REQUIRED", "ABSTAINED", "UNSAFE_INPUT"
    ]
    supporting_event_ids: tuple[str, ...] = Field(default=(), max_length=30)
    contradicting_event_ids: tuple[str, ...] = Field(default=(), max_length=30)
    missing_information: tuple[str, ...] = Field(default=(), max_length=20)
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    review_seconds: int = Field(gt=0, le=7200)
    notes: str = Field(default="", max_length=4000)
    reviewed_at: str
    reviewer_attestation: Literal[ATTESTATION]

    @field_validator("reviewed_at")
    @classmethod
    def timezone_required(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("reviewed_at requires a timezone")
        return parsed.isoformat()

    @model_validator(mode="after")
    def evidence_shape(self):
        support = set(self.supporting_event_ids)
        contradiction = set(self.contradicting_event_ids)
        if len(support) != len(self.supporting_event_ids) or len(contradiction) != len(self.contradicting_event_ids):
            raise ValueError("duplicate evidence IDs")
        if support & contradiction:
            raise ValueError("an event cannot be both supporting and contradicting")
        if self.pattern_present == "YES" and not support:
            raise ValueError("a positive review requires supporting evidence")
        if self.pattern_present == "UNCERTAIN" and not self.missing_information:
            raise ValueError("an uncertain review must identify missing information")
        return self
