"""RAK = Request Access Key. Unit of work for the pipeline."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .findings import Finding


class RAKMetadata(BaseModel):
    request_access_key: str
    application: str = "sap"
    actor: str
    requested_operations: list[str]
    session_ids: list[str]
    rak_start: datetime
    rak_end: datetime
    total_event_count: int = 0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ReportMetadata(BaseModel):
    pipeline_version: str
    prompt_versions: dict[str, str]
    model_id: str
    pass1_invocations: int = 0
    pass2_invocations: int = 0
    total_bedrock_calls: int = 0
    pipeline_latency_seconds: float = 0.0
    cost_estimate_usd: float = 0.0
    manual_review_count: int = 0


class RAKReport(BaseModel):
    """Final per-RAK output."""

    rak_id: str
    metadata: RAKMetadata
    findings_by_use_case: dict[str, list[Finding]] = Field(default_factory=dict)
    report_metadata: ReportMetadata
    raw_extras: dict[str, Any] = Field(default_factory=dict)
