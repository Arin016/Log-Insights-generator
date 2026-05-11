"""Confidence gate — routes findings to emit vs manual review.

Findings with confidence >= threshold are emitted to the customer report.
Findings below threshold are routed to manual review.
"""

from __future__ import annotations

from config import CONFIDENCE_THRESHOLD
from core.contracts import Finding


def needs_manual_review(finding: Finding, threshold: float = CONFIDENCE_THRESHOLD) -> bool:
    return finding.confidence < threshold
