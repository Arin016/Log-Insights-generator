"""Finding = the unit of analyzer output."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ConfidenceFactors(BaseModel):
    """Structured anchoring for confidence scores.

    Each factor is a yes/no judgment the analyzer must answer. This makes
    confidence scores reasoned rather than vibes-based.
    """

    sufficient_context: bool = Field(
        ..., description="Did the analyzer have everything it needed?"
    )
    unambiguous_evidence: bool = Field(
        ..., description="Are the cited events unambiguous?"
    )
    pattern_clear: bool = Field(
        ..., description="Is the pattern obvious or borderline?"
    )
    scope_unambiguous: bool = Field(
        ..., description="Is scope deviation from requested FF clear?"
    )


class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"f_{uuid4().hex[:12]}")
    rak_id: str
    use_case: str
    title: str
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_factors: ConfidenceFactors
    evidence_event_ids: list[str]
    affected_session_ids: list[str]
    reasoning: str

    # Provenance
    pass_label: Literal["pass_1", "pass_2", "manual_review"] = "pass_1"
    refined_from: str | None = None
    prompt_version: str = "v1"
    model_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
