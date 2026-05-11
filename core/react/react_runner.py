"""Stateful ReAct runner — single ACP session per use case.

Architecture (v1.5):
  - One stateful Kiro ACP session per use case
  - LLM receives scoped events + tool definitions upfront
  - LLM autonomously decides when to call tools during analysis
  - Bounded Autonomy: max 7 iterations, max 4 calls per tool, wall-clock cap
  - 8th forced "finalize" turn if iterations exhausted
  - Tool cap exceeded → inject error message (not counted as iteration)
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from config import (
    KIRO_MODEL,
    PROMPT_VERSIONS,
    REACT_MAX_ITERATIONS,
    REACT_MAX_PER_TOOL,
    REACT_WALL_CLOCK_SECONDS,
)
from core.contracts import (
    ConfidenceFactors,
    Finding,
    LogEvent,
    RAKMetadata,
)
from core.formatting.pipe_formatter import format_events
from core.logging_setup import log
from core.analyzers.acp_client import KiroAcpSession
from core.analyzers.kiro_client import extract_json
from core.analyzers.prompt_loader import render_pass1_prompt
from core.pass2 import tool_registry


def _render_tool_catalog() -> str:
    tools = tool_registry.list_tools()
    if not tools:
        return "(no tools available)"
    parts = []
    for t in tools:
        params = t.input_schema.get("properties") or {}
        param_names = list(params.keys())
        parts.append(f"- {t.name}({', '.join(param_names)}): {t.description}")
    return "\n".join(parts)


SYSTEM_PROMPT = """\
You are a meticulous SAP security analyst acting as a Level-1 SOC analyst.
You analyze Firefighter (emergency access) audit logs to detect insider threats.

You have read-only Elasticsearch query tools available. Use them proactively
to verify hypotheses and gather deeper context before committing to findings.

## INTERACTION PROTOCOL

Each turn, respond with ONLY a single JSON object (no prose, no markdown fences).

Choose ONE of:

OPTION A — call a tool to gather more evidence:
{{"action": "tool_call", "tool": "<tool_name>", "args": {{...}}}}

OPTION B — finalize your analysis with findings:
{{
  "action": "final",
  "findings": [
    {{
      "title": "<short specific title>",
      "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
      "confidence": <0.0 to 1.0>,
      "confidence_factors": {{
        "sufficient_context": <bool>,
        "unambiguous_evidence": <bool>,
        "pattern_clear": <bool>,
        "scope_unambiguous": <bool>
      }},
      "evidence_event_ids": ["<event_id from input or tool results>", ...],
      "affected_session_ids": ["<session_id>", ...],
      "reasoning": "<concrete reasoning citing tcodes, tables, sessions>"
    }}
  ]
}}

If no threats detected, output: {{"action": "final", "findings": []}}

## RULES
- You MUST cite only real event_ids from the scoped events or tool results.
- Use tools to verify before committing to a finding.
- You never speculate beyond cited evidence.
- Be thorough: scan ALL events for ALL patterns before finalizing.
- Report EVERY distinct pattern you find, no matter how minor. Even single-event
  deviations from scope should be reported as LOW findings.
- Be deterministic: if you see evidence, always report it. Never skip a finding
  because it seems insignificant.
"""


def _build_initial_prompt(
    *,
    use_case: str,
    rak_metadata: RAKMetadata,
    scoped_events: list[LogEvent],
    custom_overrides: list[dict[str, Any]],
) -> str:
    """Build the first message: use-case prompt + events + tool catalog."""
    template_name = f"{use_case}_v1"
    events_table = format_events(scoped_events)

    use_case_prompt = render_pass1_prompt(
        template_name=template_name,
        rak_metadata=rak_metadata,
        custom_overrides=custom_overrides,
        events_table=events_table,
        event_count=len(scoped_events),
    )

    tool_catalog = _render_tool_catalog()

    return f"""{use_case_prompt}

## AVAILABLE TOOLS (read-only Elasticsearch queries)

{tool_catalog}

## INTERACTION PROTOCOL

You have a budget of multiple tool calls to investigate before finalizing.
Use them to verify hypotheses, check for related events, and confirm fraud
chains. Do NOT finalize on your first turn unless the scoped events are
trivially small. Investigate thoroughly — query tables, tcodes, and sessions
to confirm patterns before committing findings.

Respond with ONLY a JSON object per turn:
- {{"action": "tool_call", "tool": "<name>", "args": {{...}}}} to query ES
- {{"action": "final", "findings": [...]}} when ready to commit

Begin your analysis now.
"""


def _findings_from_payload(
    raw_findings: list[dict[str, Any]],
    *,
    rak_id: str,
    use_case: str,
) -> list[Finding]:
    out: list[Finding] = []
    for raw in raw_findings:
        try:
            cf = raw.get("confidence_factors") or {}
            out.append(
                Finding(
                    rak_id=rak_id,
                    use_case=use_case,
                    title=raw["title"],
                    severity=raw["severity"],
                    confidence=float(raw["confidence"]),
                    confidence_factors=ConfidenceFactors(**cf),
                    evidence_event_ids=list(raw.get("evidence_event_ids") or []),
                    affected_session_ids=list(raw.get("affected_session_ids") or []),
                    reasoning=raw["reasoning"],
                    pass_label="pass_1",
                    refined_from=None,
                    prompt_version=PROMPT_VERSIONS.get(use_case, "v1"),
                    model_id=KIRO_MODEL,
                    created_at=datetime.utcnow(),
                )
            )
        except (KeyError, TypeError, ValueError) as e:
            log.warning("react.skipped_malformed_finding", error=str(e), raw=str(raw)[:200])
    return out


def _execute_tool_call(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool = tool_registry.get_tool(tool_name)
    return tool.fn(**args)


def run_react_session(
    *,
    use_case: str,
    rak_metadata: RAKMetadata,
    scoped_events: list[LogEvent],
    custom_overrides: list[dict[str, Any]],
) -> list[Finding]:
    """Run a single stateful ReAct session for one use case."""
    rak_id = rak_metadata.request_access_key

    if not scoped_events:
        log.info("react.skip_empty_scope", use_case=use_case, rak_id=rak_id)
        return []

    log.info("react.start", use_case=use_case, rak_id=rak_id, event_count=len(scoped_events))

    # Per-tool call counters
    tool_call_counts: dict[str, int] = {}
    start_time = time.time()

    with KiroAcpSession(rak_id=rak_id, use_case=use_case) as session:
        # Turn 1: inject system prompt + scoped context + tool catalog
        initial_prompt = SYSTEM_PROMPT + "\n\n---\n\n" + _build_initial_prompt(
            use_case=use_case,
            rak_metadata=rak_metadata,
            scoped_events=scoped_events,
            custom_overrides=custom_overrides,
        )
        raw_response = session.send_message(initial_prompt, purpose=f"react.{use_case}.init", timeout=180)

        iteration = 0
        while iteration < REACT_MAX_ITERATIONS:
            # Check wall-clock
            elapsed = time.time() - start_time
            if elapsed > REACT_WALL_CLOCK_SECONDS:
                log.warning("react.wall_clock_hit", use_case=use_case, rak_id=rak_id, elapsed=elapsed)
                break

            # Parse response
            try:
                payload = extract_json(raw_response)
            except ValueError as e:
                log.warning("react.parse_error", use_case=use_case, error=str(e)[:200])
                # Ask LLM to fix — not counted as iteration
                raw_response = session.send_message(
                    f"Your previous response could not be parsed as JSON: {str(e)[:200]}\n"
                    "Respond with ONLY a valid JSON object with an 'action' field.",
                    purpose=f"react.{use_case}.parse_fix",
                )
                continue

            action = payload.get("action")

            if action == "final":
                findings_list = payload.get("findings") or []
                log.info("react.final", use_case=use_case, rak_id=rak_id,
                         iteration=iteration, finding_count=len(findings_list))
                return _findings_from_payload(findings_list, rak_id=rak_id, use_case=use_case)

            elif action == "tool_call":
                iteration += 1
                tool_name = payload.get("tool", "")
                args = payload.get("args") or {}

                # Check per-tool cap
                current_count = tool_call_counts.get(tool_name, 0)
                if current_count >= REACT_MAX_PER_TOOL:
                    # Inject error — NOT counted as iteration (undo the increment)
                    iteration -= 1
                    raw_response = session.send_message(
                        json.dumps({
                            "observation": f"TOOL BUDGET EXHAUSTED: You have already called '{tool_name}' "
                            f"{REACT_MAX_PER_TOOL} times (maximum). Use a different tool or finalize."
                        }),
                        purpose=f"react.{use_case}.tool_cap",
                    )
                    continue

                # Execute tool
                try:
                    result = _execute_tool_call(tool_name, args)
                    tool_call_counts[tool_name] = current_count + 1
                    log.info("react.tool_call", use_case=use_case, tool=tool_name,
                             iteration=iteration, args=args)
                    raw_response = session.send_message(
                        json.dumps({"observation": result}),
                        purpose=f"react.{use_case}.tool_result",
                    )
                except Exception as e:
                    tool_call_counts[tool_name] = current_count + 1
                    log.warning("react.tool_error", tool=tool_name, error=str(e))
                    raw_response = session.send_message(
                        json.dumps({"observation": f"TOOL ERROR: {e}"}),
                        purpose=f"react.{use_case}.tool_error",
                    )
            else:
                log.warning("react.unknown_action", action=action, use_case=use_case)
                break

        # 8th forced finalize turn
        log.info("react.forcing_finalize", use_case=use_case, rak_id=rak_id)
        raw_response = session.send_message(
            "You have exhausted your investigation budget. You MUST finalize NOW. "
            "Output your best findings based on everything you have gathered so far. "
            'Respond with: {"action": "final", "findings": [...]}',
            purpose=f"react.{use_case}.forced_final",
            timeout=180,
        )

        try:
            payload = extract_json(raw_response)
            findings_list = payload.get("findings") or []
        except ValueError:
            log.error("react.forced_final_parse_failed", use_case=use_case, rak_id=rak_id)
            return []

    elapsed_total = time.time() - start_time
    log.info("react.complete", use_case=use_case, rak_id=rak_id,
             elapsed_seconds=round(elapsed_total, 1),
             finding_count=len(findings_list),
             tool_calls=sum(tool_call_counts.values()))

    return _findings_from_payload(findings_list, rak_id=rak_id, use_case=use_case)
