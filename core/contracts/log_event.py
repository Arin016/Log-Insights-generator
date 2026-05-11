"""Generic, application-agnostic event model.

Application-specific raw fields live in `attributes`. The semantic fields
(action_type, entity_classification, operation_category) are populated by
the per-application parser using catalog lookups.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal["READ", "CREATE", "UPDATE", "DELETE", "EXECUTE", "OTHER"]


class LogEvent(BaseModel):
    """One parsed event. Engine code only reads these fields, never raw."""

    event_id: str
    request_access_key: str
    session_id: str
    timestamp_utc: datetime
    actor: str

    # Generic semantic fields (populated by parser via YAML catalog lookup)
    action_type: ActionType = "OTHER"
    entity_accessed: str | None = None
    entity_classification: str | None = None
    operation: str | None = None
    operation_category: str | None = None

    # Scope context
    requested_operation: str | None = None
    deviation_flagged: bool = False

    # Raw + app-specific
    application: str = "sap"
    attributes: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
