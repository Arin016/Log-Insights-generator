"""Retry handler for evidence verification failures.

Strategy: if any finding from a Pass 1 analyzer cites bad event_ids,
re-invoke that analyzer with a stricter prompt suffix warning about the
hallucination. After max_retries failures, drop the offending findings
and keep the verified ones.

Deduplication: the retry callable produces a full new finding set (not
just replacements). We deduplicate using Jaccard similarity over
evidence_event_ids — same evidence = same finding.
"""

from __future__ import annotations

from typing import Callable

from config import EVIDENCE_VERIFY_MAX_RETRIES
from core.contracts import Finding, LogEvent
from core.logging_setup import log
from core.verification.evidence_verifier import (
    collect_event_ids,
    verify_finding,
)

_JACCARD_DEDUP_THRESHOLD = 0.7


def _is_duplicate(candidate: Finding, existing: list[Finding]) -> bool:
    """Check if candidate overlaps with any existing finding by evidence."""
    cand_set = frozenset(candidate.evidence_event_ids)
    if not cand_set:
        return False
    for f in existing:
        ex_set = frozenset(f.evidence_event_ids)
        if not ex_set:
            continue
        intersection = cand_set & ex_set
        union = cand_set | ex_set
        if len(intersection) / len(union) >= _JACCARD_DEDUP_THRESHOLD:
            return True
    return False


def _deduplicate(findings: list[Finding], *, label: str = "") -> list[Finding]:
    """Remove findings with Jaccard overlap >= threshold within a use case."""
    kept: list[Finding] = []
    dropped = 0
    for f in findings:
        if not _is_duplicate(f, kept):
            kept.append(f)
        else:
            dropped += 1
    if dropped:
        log.info("evidence.dedup_removed", label=label, dropped=dropped, kept=len(kept))
    return kept


def verify_and_filter_findings(
    *,
    findings: list[Finding],
    scoped_events: list[LogEvent],
    retry_callable: Callable[[list[str]], list[Finding]] | None = None,
    max_retries: int = EVIDENCE_VERIFY_MAX_RETRIES,
    label: str = "pass1",
) -> list[Finding]:
    """Verify all findings; retry the analyzer for hallucinated ones.

    Args:
      findings: the analyzer's output to verify.
      scoped_events: events the analyzer received (defines valid event_ids).
      retry_callable: optional function called with the list of hallucinated
        event_ids; should return a fresh list of findings from a stricter
        retry. If None, hallucinated findings are simply dropped.
      max_retries: max number of retry rounds.
      label: log label.

    Returns:
      Verified findings (those that passed evidence verification).
    """
    valid_ids = collect_event_ids(scoped_events)

    # First pass: verify all findings
    verified: list[Finding] = []
    bad: list[Finding] = []
    all_hallucinated: set[str] = set()

    for finding in findings:
        result = verify_finding(finding, valid_ids)
        if result.is_valid:
            verified.append(finding)
        else:
            bad.append(finding)
            all_hallucinated.update(result.hallucinated_event_ids)
            log.warning(
                "evidence.verification_failed",
                label=label,
                finding_id=finding.finding_id,
                title=finding.title,
                reason=result.reason,
                retry=0,
            )

    if not bad:
        log.info("evidence.all_verified", label=label, count=len(verified), retries_used=0)
        return _deduplicate(verified, label=label)

    if retry_callable is None or max_retries < 1:
        log.warning(
            "evidence.dropping_unverified",
            label=label,
            dropped=len(bad),
            kept=len(verified),
            retries_used=0,
        )
        return _deduplicate(verified, label=label)

    # Retry: re-run the analyzer, verify the new output, deduplicate
    log.info(
        "evidence.retrying",
        label=label,
        bad_count=len(bad),
        hallucinated_ids=sorted(all_hallucinated)[:10],
        retry=1,
    )

    new_findings = retry_callable(sorted(all_hallucinated))

    # Verify retry output
    retry_verified: list[Finding] = []
    for finding in new_findings:
        result = verify_finding(finding, valid_ids)
        if result.is_valid:
            retry_verified.append(finding)
        else:
            log.warning(
                "evidence.retry_still_bad",
                label=label,
                finding_id=finding.finding_id,
                title=finding.title,
                reason=result.reason,
            )

    # Deduplicate: only keep retry findings that don't overlap with
    # already-verified findings (Jaccard >= 0.7 on evidence = duplicate)
    deduplicated = [f for f in retry_verified if not _is_duplicate(f, verified)]

    log.info(
        "evidence.retry_complete",
        label=label,
        originally_verified=len(verified),
        retry_verified=len(retry_verified),
        deduplicated_new=len(deduplicated),
    )

    return _deduplicate(verified + deduplicated, label=label)
