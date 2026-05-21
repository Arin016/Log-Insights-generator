"""Local entry point: fetch a RAK from Elasticsearch and run the pipeline.

Usage:
  python run_local.py --rak-id <rak_id>
"""

from __future__ import annotations

import argparse
import sys

from core.contracts import RAKMetadata
from core.logging_setup import log
from core.orchestrator.pipeline import run_pipeline
from core.pass2.event_store import ElasticsearchEventStore

from applications.sap.catalogs import (
    load_tcode_catalog,
    load_table_catalog,
    load_use_case,
    list_use_cases,
)
from applications.sap.tools.sap_tools import register_sap_pass2_tools


def derive_rak_metadata_from_events(events) -> RAKMetadata:
    """Derive RAK metadata from the parsed events themselves."""
    if not events:
        raise ValueError("No events to derive metadata from.")

    rak_id = events[0].request_access_key
    actor = events[0].actor
    session_ids = sorted({e.session_id for e in events})
    requested = sorted({e.requested_operation for e in events if e.requested_operation})
    timestamps = [e.timestamp_utc for e in events]

    return RAKMetadata(
        request_access_key=rak_id,
        application="sap",
        actor=actor,
        requested_operations=requested,
        session_ids=session_ids,
        rak_start=min(timestamps),
        rak_end=max(timestamps),
        total_event_count=len(events),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FF Insights pipeline on a seeded RAK.")
    parser.add_argument("--rak-id", required=True, help="The Request Access Key to analyze.")
    args = parser.parse_args()

    log.info("pipeline.start", rak_id=args.rak_id)

    # ─── Fetch events from Elasticsearch ────────────────────────────────
    event_store = ElasticsearchEventStore(rak_id=args.rak_id)
    events = event_store.fetch_all_events()

    if not events:
        log.error("no_events_for_rak", rak_id=args.rak_id)
        print(f"\nNo events found for RAK '{args.rak_id}'.\n"
              "Did you seed Elasticsearch first?\n"
              "  python seed_elasticsearch.py --log-file <path> --recreate-index\n")
        return 2

    rak_metadata = derive_rak_metadata_from_events(events)
    log.info("rak_metadata", rak_id=rak_metadata.request_access_key,
             actor=rak_metadata.actor, sessions=len(rak_metadata.session_ids),
             events=len(events))

    # ─── Load use case configs + catalogs ───────────────────────────────
    use_case_configs = {name: load_use_case(name) for name in list_use_cases()}
    tcode_catalog = load_tcode_catalog()
    table_catalog = load_table_catalog()
    custom_overrides = tcode_catalog.custom_overrides() + table_catalog.custom_overrides()

    # ─── Run pipeline ───────────────────────────────────────────────────
    report = run_pipeline(
        rak_metadata=rak_metadata,
        parsed_events=events,
        event_store=event_store,
        use_case_configs=use_case_configs,
        custom_overrides=custom_overrides,
        register_tools_fn=register_sap_pass2_tools,
    )

    # ─── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"RAK {report.rak_id} — Threat Analysis Report")
    print(f"Actor: {report.metadata.actor} | "
          f"{len(report.metadata.session_ids)} sessions | "
          f"{report.metadata.rak_start.isoformat()} → {report.metadata.rak_end.isoformat()}")
    print(f"Requested scope: {', '.join(report.metadata.requested_operations) or '(none)'}")
    print("=" * 70)

    for use_case, findings in report.findings_by_use_case.items():
        print(f"\n{use_case.upper()} FINDINGS ({len(findings)})")
        print("-" * 70)
        if not findings:
            print("(no findings)")
            continue
        for f in findings:
            tag = f"[{f.severity} conf {f.confidence:.2f}]"
            print(f"{tag} {f.title}")
            print(f"  Sessions: {', '.join(f.affected_session_ids)}")
            print(f"  Evidence: {', '.join(f.evidence_event_ids[:5])}"
                  + (" ..." if len(f.evidence_event_ids) > 5 else ""))
            print(f"  Reasoning: {f.reasoning}")
            print()

    print("=" * 70)
    print(f"Pipeline: {report.report_metadata.pipeline_latency_seconds}s | "
          f"ReAct sessions: {report.report_metadata.pass1_invocations} | "
          f"Manual review: {report.report_metadata.manual_review_count}")
    print(f"Report saved to: data/reports/{report.rak_id}.json")
    print(f"Audit log:       data/llm_audit/{report.rak_id}/")

    _print_cost_summary(report.rak_id)
    print("=" * 70)

    return 0


def _print_cost_summary(rak_id: str) -> None:
    """Estimate tokens and cost from audit logs."""
    import json
    from pathlib import Path
    from config import LLM_AUDIT_DIR, KIRO_MODEL

    audit_dir = LLM_AUDIT_DIR / rak_id
    if not audit_dir.exists():
        return

    PRICING = {
        "claude-opus-4.6": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    }
    prices = PRICING.get(KIRO_MODEL, {"input": 15.0, "output": 75.0})

    total_input_chars = 0
    total_output_chars = 0
    call_count = 0

    for f in audit_dir.glob("*.json"):
        with open(f) as fh:
            d = json.load(fh)
        req = d.get("request", {})
        resp = d.get("response", {})
        total_input_chars += len(req.get("content", "") or req.get("system_prompt", "") or "")
        total_output_chars += len(resp.get("text", "") or resp.get("stdout", "") or "")
        call_count += 1

    input_tokens = total_input_chars // 4
    output_tokens = total_output_chars // 4
    total_tokens = input_tokens + output_tokens
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000

    print(f"\nToken estimate: ~{input_tokens:,} input + ~{output_tokens:,} output = ~{total_tokens:,} total")
    print(f"Cost estimate:  ${cost:.3f} ({call_count} LLM turns, {KIRO_MODEL} pricing)")


if __name__ == "__main__":
    sys.exit(main())
