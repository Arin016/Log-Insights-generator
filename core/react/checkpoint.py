"""Per-use-case checkpoint for crash recovery.

Tracks which use cases completed successfully. On crash, only re-runs
the incomplete ones. Individual ReAct sessions are short enough (≤120s)
that replaying mid-session isn't worth the Zombie Resume risk.
"""

import json
import time
from pathlib import Path
from typing import Any

from config import PIPELINE_STATE_DIR


def _checkpoint_path(rak_id: str) -> Path:
    return PIPELINE_STATE_DIR / f"{rak_id}__react_progress.json"


def load_checkpoint(rak_id: str) -> dict[str, Any]:
    """Load existing checkpoint or return empty state."""
    path = _checkpoint_path(rak_id)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"rak_id": rak_id, "completed_use_cases": {}, "started_at": time.time()}


def mark_use_case_complete(rak_id: str, use_case: str, findings: list[dict]) -> None:
    """Mark a use case as successfully completed with its findings."""
    state = load_checkpoint(rak_id)
    state["completed_use_cases"][use_case] = {
        "findings": findings,
        "completed_at": time.time(),
    }
    path = _checkpoint_path(rak_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)


def clear_checkpoint(rak_id: str) -> None:
    """Remove checkpoint after full pipeline success."""
    path = _checkpoint_path(rak_id)
    if path.exists():
        path.unlink()


def get_completed_use_cases(rak_id: str) -> set[str]:
    """Return use cases that already finished successfully."""
    state = load_checkpoint(rak_id)
    return set(state.get("completed_use_cases", {}).keys())


def get_completed_findings(rak_id: str) -> dict[str, list[dict]]:
    """Return {use_case: findings_dicts} for all completed use cases."""
    state = load_checkpoint(rak_id)
    return {
        uc: data["findings"]
        for uc, data in state.get("completed_use_cases", {}).items()
    }
