"""Pipeline orchestrator v1.5 — stateful ReAct per use case.

Flow:
  1. Scope events per use case (YAML-driven)
  2. Parallel stateful ReAct sessions (one per use case, tools available upfront)
  3. Evidence verification (drop hallucinated event_ids)
  4. Challenger — adversarial FP review (false positives → manual review with reason)
  5. Confidence gate (>= 0.70 → emit, < 0.70 → manual review with reason)
  6. Persist findings + report
"""

from __future__ import annotations

import glob
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from config import (
    CONFIDENCE_THRESHOLD, KIRO_MODEL, PIPELINE_VERSION, PROMPT_VERSIONS,
    FINDINGS_DIR, LLM_AUDIT_DIR, MANUAL_REVIEW_DIR, REPORTS_DIR,
)
from core.contracts import (
    Finding,
    LogEvent,
    PipelineState,
    RAKMetadata,
    RAKReport,
    ReportMetadata,
)
from core.logging_setup import log
from core.persistence.local_store import (
    push_to_manual_review,
    save_findings,
    save_report,
    update_pipeline_state,
)
from core.scoping.filter_engine import apply_use_case_filter
from core.verification.retry_handler import verify_and_filter_findings
from core.react.checkpoint import get_completed_use_cases, get_completed_findings, clear_checkpoint
from core.react.factory import get_react_runner


def _clean_previous_run(rak_id: str) -> None:
    """Remove artifacts from previous runs for this RAK."""
    for f in glob.glob(str(MANUAL_REVIEW_DIR / f"{rak_id}__*.json")):
        os.remove(f)
    for path in [FINDINGS_DIR / f"{rak_id}.json", REPORTS_DIR / f"{rak_id}.json"]:
        if path.exists():
            os.remove(path)


def run_pipeline(
    *,
    rak_metadata: RAKMetadata,
    parsed_events: list[LogEvent],
    event_store: Any,
    use_case_configs: dict[str, dict[str, Any]],
    custom_overrides: list[dict[str, Any]],
    register_tools_fn: Callable[[Any], None],
) -> RAKReport:
    """Execute the full pipeline. Returns the final RAKReport."""
    rak_id = rak_metadata.request_access_key
    pipeline_start = time.time()
    react_runner_fn = get_react_runner()
    update_pipeline_state(rak_id, PipelineState.INITIATED)

    # ─── Clean previous run artifacts ──────────────────────────────────
    _clean_previous_run(rak_id)

    # ─── Step 1: Scope events per use case ─────────────────────────────
    scoped_per_use_case: dict[str, list[LogEvent]] = {}
    for use_case_name, use_case_config in use_case_configs.items():
        scoped = apply_use_case_filter(parsed_events, use_case_config)
        scoped_per_use_case[use_case_name] = scoped
        log.info("scoping.complete", use_case=use_case_name, rak_id=rak_id,
                 event_count=len(scoped))
    update_pipeline_state(rak_id, PipelineState.SCOPED)

    # ─── Step 2: Register tools (bind to event store) ──────────────────
    register_tools_fn(event_store)

    # ─── Step 3: Parallel stateful ReAct sessions ──────────────────────
    react_findings_per_use_case: dict[str, list[Finding]] = {}
    react_call_count = 0

    # Resume support: skip use cases that completed in a previous (crashed) run
    already_done = get_completed_use_cases(rak_id)
    use_cases_to_run = {uc: scoped for uc, scoped in scoped_per_use_case.items()
                        if uc not in already_done}
    if already_done:
        log.info("pipeline.resuming", rak_id=rak_id, skipped=sorted(already_done))
        # Reload findings from checkpoint for completed use cases
        for uc, raw_findings in get_completed_findings(rak_id).items():
            react_findings_per_use_case[uc] = [
                Finding.model_validate(f) for f in raw_findings
            ]
            react_call_count += 1

    def _run_use_case(use_case_name: str, scoped: list[LogEvent]) -> tuple[str, list[Finding]]:
        findings = react_runner_fn(
            use_case=use_case_name,
            rak_metadata=rak_metadata,
            scoped_events=scoped,
            custom_overrides=custom_overrides,
        )
        return use_case_name, findings

    with ThreadPoolExecutor(max_workers=len(use_cases_to_run) or 1) as executor:
        futures = {
            executor.submit(_run_use_case, uc, scoped): uc
            for uc, scoped in use_cases_to_run.items()
        }
        for future in as_completed(futures):
            use_case_name, findings = future.result()
            react_findings_per_use_case[use_case_name] = findings
            react_call_count += 1

    update_pipeline_state(rak_id, PipelineState.PASS1_VERIFIED)

    # ─── Step 4: Evidence verification ─────────────────────────────────
    verified_per_use_case: dict[str, list[Finding]] = {}
    for uc, findings in react_findings_per_use_case.items():
        verified = verify_and_filter_findings(
            findings=findings,
            scoped_events=parsed_events,  # entire RAK is valid universe
            retry_callable=None,  # no retry — ReAct already investigated
            label=f"react.{uc}",
        )
        verified_per_use_case[uc] = verified

    # ─── Step 5: Challenger — adversarial false-positive review ──────
    from core.challenger import challenge_findings

    challenged_per_use_case: dict[str, list[Finding]] = {}
    challenger_manual_count = 0

    for uc, findings in verified_per_use_case.items():
        if not findings:
            challenged_per_use_case[uc] = []
            continue
        accepted, manual_items = challenge_findings(findings, rak_id)
        challenged_per_use_case[uc] = accepted
        for finding, reason in manual_items:
            push_to_manual_review(
                rak_id=rak_id,
                finding_id=finding.finding_id,
                pass1_finding=finding,
                pass2_finding=None,
                reason=reason,
            )
            challenger_manual_count += 1

    # ─── Step 6: Confidence gate ───────────────────────────────────────
    final_findings_per_use_case: dict[str, list[Finding]] = {}
    manual_review_count = challenger_manual_count

    for uc, findings in challenged_per_use_case.items():
        emitted: list[Finding] = []
        for f in findings:
            if f.confidence >= CONFIDENCE_THRESHOLD:
                emitted.append(f)
            else:
                # Use the LLM's own reasoning + factor-based note
                factors = f.confidence_factors
                issues = []
                if not factors.sufficient_context:
                    issues.append("insufficient context")
                if not factors.unambiguous_evidence:
                    issues.append("ambiguous evidence")
                if not factors.pattern_clear:
                    issues.append("borderline pattern")
                if not factors.scope_unambiguous:
                    issues.append("unclear scope")

                reason_text = f.reasoning
                if issues:
                    reason_text += f" [Flagged: {', '.join(issues)}]"

                push_to_manual_review(
                    rak_id=rak_id,
                    finding_id=f.finding_id,
                    pass1_finding=f,
                    pass2_finding=None,
                    reason=reason_text,
                )
                manual_review_count += 1
        final_findings_per_use_case[uc] = emitted

    update_pipeline_state(rak_id, PipelineState.AGGREGATED)

    # ─── Step 6: Persist ───────────────────────────────────────────────
    pipeline_latency = time.time() - pipeline_start
    all_findings: list[Finding] = []
    for findings in final_findings_per_use_case.values():
        all_findings.extend(findings)

    report = RAKReport(
        rak_id=rak_id,
        metadata=rak_metadata,
        findings_by_use_case=final_findings_per_use_case,
        report_metadata=ReportMetadata(
            pipeline_version=PIPELINE_VERSION,
            prompt_versions=PROMPT_VERSIONS,
            model_id=KIRO_MODEL,
            pass1_invocations=react_call_count,
            pass2_invocations=0,
            total_bedrock_calls=react_call_count,
            pipeline_latency_seconds=round(pipeline_latency, 2),
            cost_estimate_usd=0.0,
            manual_review_count=manual_review_count,
        ),
    )

    save_findings(rak_id, all_findings)
    save_report(report)
    update_pipeline_state(rak_id, PipelineState.EMITTED,
                          notes=f"latency={pipeline_latency:.1f}s")
    clear_checkpoint(rak_id)

    log.info("pipeline.complete", rak_id=rak_id,
             latency_seconds=round(pipeline_latency, 2),
             finding_count=len(all_findings),
             manual_review_count=manual_review_count)

    return report
