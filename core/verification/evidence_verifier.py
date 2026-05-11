"""Evidence verification.

Pure code check: every cited evidence_event_id in a finding must exist
in the events that analyzer received. Hallucinated event_ids → reject.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts import Finding, LogEvent


@dataclass
class VerificationResult:
    is_valid: bool
    hallucinated_event_ids: list[str]
    reason: str | None = None


def verify_finding(
    finding: Finding, scoped_event_ids: set[str]
) -> VerificationResult:
    cited = set(finding.evidence_event_ids)

    if not cited:
        return VerificationResult(
            is_valid=False,
            hallucinated_event_ids=[],
            reason="finding has no evidence_event_ids",
        )

    hallucinated = sorted(cited - scoped_event_ids)
    if hallucinated:
        return VerificationResult(
            is_valid=False,
            hallucinated_event_ids=hallucinated,
            reason=f"cited event_ids not in input: {hallucinated[:5]}",
        )

    return VerificationResult(is_valid=True, hallucinated_event_ids=[])


def collect_event_ids(events: list[LogEvent]) -> set[str]:
    return {e.event_id for e in events}
