"""
SAP Challenger — adversarial false-positive review of findings.

Same approach as v3 challenger_sap.py: loads SAP domain docs, challenges
findings in batches, grades evidence tiers, checks against legitimate
business patterns. Findings marked FALSE_POSITIVE are NOT dropped — they
go to manual review with a reason.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.contracts import Finding
from core.logging_setup import log
from core.analyzers.acp_client import KiroAcpSession
from core.analyzers.kiro_client import extract_json

DOCS_DIR = Path(__file__).parent / "docs"
BATCH_SIZE = 6


def _load_doc(name: str) -> dict:
    with open(DOCS_DIR / name) as f:
        return json.load(f)


def _build_challenger_context() -> str:
    """Build challenger prompt context from SAP domain docs."""
    doc = _load_doc("sap_challenger_doc.json")
    analysis_doc = _load_doc("sap_analysis_doc.json")
    sections: list[str] = []

    # Firefighter rules
    ff = doc.get("firefighter_eam_context", {})
    if ff:
        sections.append("FIREFIGHTER/EAM SESSION RULES:")
        for rule in ff.get("rules", []):
            sections.append(f"- {rule}")
        sections.append("")

    # False positive rules
    sections.append("FALSE POSITIVE RULES (apply strictly):")
    for fp in doc.get("false_positive_rules", []):
        sections.append(f"- {fp['rule']}: {fp['action']}")
    sections.append("")

    # Evidence grading
    eg = doc.get("evidence_grading", {})
    if eg:
        sections.append("EVIDENCE GRADING (CRITICAL requires Tier 1 or 2):")
        for tier in ['tier_1_definitive', 'tier_2_strong', 'tier_3_circumstantial', 'tier_4_observational']:
            t = eg.get(tier, {})
            if t:
                sections.append(f"- {tier.upper()}: {t.get('criteria', '')}")
        sections.append("")

    # Risk calibration
    rcm = doc.get("risk_calibration_matrix", {})
    if rcm:
        sections.append("RISK SCORE CALIBRATION (MANDATORY):")
        for key, rule in rcm.items():
            line = f"- {rule['rule']}"
            if 'max_score' in rule:
                line += f"  [CAP: {rule['max_score']}]"
            sections.append(line)
        sections.append("")

    # Tcode behavior facts
    tbf = analysis_doc.get("tcode_behavior_facts", {})
    if tbf:
        sections.append("BUILT-IN TRANSACTION BEHAVIOR (not exploits):")
        for tcode, fact in tbf.get("facts", {}).items():
            sections.append(f"- {tcode}: {fact}")
        sections.append("")

    # Business process patterns
    bpp = doc.get("business_process_patterns", {})
    patterns = bpp.get("patterns", [])
    if patterns:
        sections.append("LEGITIMATE BUSINESS PATTERNS:")
        for p in patterns:
            sections.append(f"- {p['pattern']}: {p['legitimate_explanation']}")
        sections.append("")

    return "\n".join(sections)


PROMPT_CHALLENGE_BATCH = """You are a senior SAP IGA auditor reviewing findings from an automated audit. Be SKEPTICAL — most automated CRITICAL findings are standard business operations.

{sap_context}

RAK CONTEXT:
  Actor: {actor}
  Requested Scope: {requested_scope}
  Sessions: {sessions}

REVIEW INSTRUCTIONS:
1. EVIDENCE GRADING: Tier 1 (CDPOS Old/New) → CRITICAL ok. Tier 3 (SM20 only) → caps at MEDIUM. Tier 4 (volume only) → caps at LOW.
2. Check EVERY legitimate business pattern. Check built-in tcode behavior.
3. Firefighter/EAM = authorized elevated access, not an attack.
4. Apply FALSE POSITIVE RULES and RISK CALIBRATION strictly.
5. BUSINESS JUSTIFICATION: For each finding, assess whether a legitimate business reason could explain this activity (e.g., urgent PO amendment, bulk delivery processing, period-end corrections, vendor onboarding). If yes, state it clearly.

FINDINGS TO REVIEW:
{findings_block}

OUTPUT (JSON only):
{{"results": [
  {{
    "finding_id": "...",
    "evidence_tier": "1|2|3|4",
    "verdict": "CONFIRMED|ADJUSTED|FALSE_POSITIVE",
    "adjusted_severity": "LOW|MEDIUM|HIGH|CRITICAL",
    "adjusted_confidence": 0.0-1.0,
    "reason": "2-3 sentences explaining decision",
    "business_justification": "If a legitimate business explanation exists, state it here. Otherwise null.",
    "corrected_title": "new title or null",
    "corrected_reasoning": "rewritten neutral reasoning or null"
  }}
]}}"""


def challenge_findings(
    findings: list[Finding],
    rak_id: str,
    rak_metadata=None,
) -> tuple[list[Finding], list[tuple[Finding, str]]]:
    """Challenge findings in batches.

    Returns:
        (accepted_findings, manual_review_items)
        manual_review_items = list of (finding, reason) for findings
        the challenger flagged as false positives.
    """
    if not findings:
        return [], []

    sap_context = _build_challenger_context()
    actor = rak_metadata.actor if rak_metadata else "unknown"
    requested_scope = ", ".join(rak_metadata.requested_operations) if rak_metadata else "unknown"
    sessions = ", ".join(rak_metadata.session_ids[:5]) if rak_metadata else "unknown"
    accepted: list[Finding] = []
    manual_review: list[tuple[Finding, str]] = []

    # Process in batches
    for batch_start in range(0, len(findings), BATCH_SIZE):
        batch = findings[batch_start:batch_start + BATCH_SIZE]

        # Build findings block
        findings_block_parts = []
        for j, f in enumerate(batch, 1):
            findings_block_parts.append(
                f"--- FINDING {j} ---\n"
                f"Finding ID: {f.finding_id}\n"
                f"Title: {f.title}\n"
                f"Severity: {f.severity}\n"
                f"Confidence: {f.confidence}\n"
                f"Use Case: {f.use_case}\n"
                f"Reasoning: {f.reasoning}\n"
                f"Evidence IDs: {f.evidence_event_ids[:10]}\n"
            )

        prompt = PROMPT_CHALLENGE_BATCH.format(
            sap_context=sap_context,
            actor=actor,
            requested_scope=requested_scope,
            sessions=sessions,
            findings_block="\n".join(findings_block_parts),
        )

        # Call LLM
        try:
            session = KiroAcpSession(rak_id=rak_id, use_case=f"challenger_batch_{batch_start}")
            session.start()
            raw = session.send_message(prompt, purpose="challenger_review", timeout=150)
            session.close()
            result = extract_json(raw)
        except Exception as e:
            log.warning("challenger.batch_failed", error=str(e), batch_start=batch_start)
            # On failure, keep all findings as-is
            accepted.extend(batch)
            continue

        results_list = result.get("results", [])

        for j, f in enumerate(batch):
            r = results_list[j] if j < len(results_list) else None
            if not r:
                accepted.append(f)
                continue

            verdict = r.get("verdict", "CONFIRMED")
            reason = r.get("reason", "No reason provided")

            if verdict == "CONFIRMED":
                if r.get("business_justification"):
                    f.business_justification = r["business_justification"]
                accepted.append(f)
                log.info("challenger.confirmed", finding_id=f.finding_id)

            elif verdict == "ADJUSTED":
                # Update finding but keep it
                if r.get("adjusted_severity"):
                    f.severity = r["adjusted_severity"]
                if r.get("adjusted_confidence") is not None:
                    f.confidence = r["adjusted_confidence"]
                if r.get("corrected_title"):
                    f.title = r["corrected_title"]
                if r.get("corrected_reasoning"):
                    f.reasoning = r["corrected_reasoning"]
                if r.get("business_justification"):
                    f.business_justification = r["business_justification"]
                accepted.append(f)
                log.info("challenger.adjusted", finding_id=f.finding_id,
                         severity=f.severity, reason=reason)

            elif verdict == "FALSE_POSITIVE":
                # Route to manual review — never drop
                manual_review.append((
                    f,
                    f"CHALLENGER_FALSE_POSITIVE: {reason} "
                    f"(evidence_tier={r.get('evidence_tier', '?')})"
                ))
                log.info("challenger.to_manual_review", finding_id=f.finding_id,
                         reason=reason)

    log.info("challenger.complete", rak_id=rak_id,
             accepted=len(accepted), to_manual_review=len(manual_review))
    return accepted, manual_review
