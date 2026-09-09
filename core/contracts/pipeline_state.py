"""Pipeline state machine for a RAK's lifecycle through the system."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PipelineState(str, Enum):
    INITIATED = "INITIATED"
    PARSED = "PARSED"
    SCOPED = "SCOPED"
    PASS1_COMPLETE = "PASS1_COMPLETE"
    PASS1_VERIFIED = "PASS1_VERIFIED"
    GATE_DECIDED = "GATE_DECIDED"
    PASS2_COMPLETE = "PASS2_COMPLETE"
    PASS2_VERIFIED = "PASS2_VERIFIED"
    AGGREGATED = "AGGREGATED"
    EMITTED = "EMITTED"
    FAILED = "FAILED"


class PipelineStateRecord(BaseModel):
    rak_id: str
    state: PipelineState
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
