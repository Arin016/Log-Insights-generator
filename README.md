# FF Insights research testbed

For a short reviewer-oriented path through the problem, design, evidence and
limitations, start with the [engineering evidence brief](docs/research/ENGINEERING_EVIDENCE_BRIEF.md).
The [post-study fix record](docs/research/POST_STUDY_FIXES.md) separates later
engineering corrections from the frozen experiments that exposed them.

The [final implementation and evaluation report](docs/research/FINAL_REPORT.md) connects the architecture, all frozen comparisons, Claude pilot failures, spending, limitations and next research steps. An [editable Word version](docs/research/FF_Insights_V2_Final_Report.docx) is available for local review.

This repository contains two clearly separated systems:

- the audited public demonstration baseline at commit `2a3c28b`, retained for provenance; and
- a V2 local research harness for one narrowly specified synthetic vendor-bank-change/payment investigation.

The baseline code uses YAML scoping, a bounded ReAct-style loop, read-only Elasticsearch tools, event-ID existence checks and local JSON outputs. Its original README made broader threat-detection, timeout and hallucination claims that the audit did not establish. See `docs/research/BASELINE_AUDIT.md` before interpreting it.

V2 adds immutable source attribution, content-addressed snapshots, a typed case graph, evidence capsules, scope-bound query capabilities, atomic claims, structural/domain validation, contradiction searches, a separate-context semantic verifier, explicit coverage checks, review/abstention policy, parent-enforced deadlines and hash-sealed run ledgers. It currently implements one synthetic hypothesis. It is not a production system or a validated fraud detector.

## Evidence status

At frozen commit `6604e6f`, 100 deterministic tests passed and 6 dedicated Elasticsearch integration tests passed. A frozen scripted comparison ran 19 configurations on 46 held-out synthetic variants, for 874 case-runs from only two generated families. The complete V2 scripted path matched the generator's expected terminal disposition in 46/46 cases, surfaced 10 generator-matching claims with 0 unsupported surfaced claims, and did not surface the other 18 underlying positive patterns because their correct terminal behavior was unsafe-input rejection, injected failure or timeout. These results test deterministic protocol and policy behavior; they do not measure LLM or real-world effectiveness.

Development-only Llama, Claude Haiku and Claude Sonnet pilots are preserved separately. The Claude study was explicitly capped at $5 and was not run on held-out test/challenge data. It does not support model-ranking claims. `docs/research/PAPER_DECISION.md` records a paper **NO-GO**.

## Quick verification

Use Python 3.13. The default workflow never loads the legacy `.env` and uses only newly generated synthetic records.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
```

For the real Elasticsearch suite, start the dedicated loopback service using `compose.research.yml` or `scripts/start_native_es.sh`, then run:

```bash
FF_ES_INTEGRATION=1 .venv/bin/python -m pytest tests/test_elasticsearch.py -q
.venv/bin/python scripts/reproduce.py artifacts/reproduction-NEW
```

The reproduction command creates a fresh corpus, validates and seeds only its owned index, freezes a protocol, evaluates all 19 scripted configurations on test/challenge splits and derives figures from sealed raw results. Use `--memory` when Elasticsearch is unavailable. Destinations are exclusive and are never overwritten.

## Research layout

- `core/v2/`: provenance, graph, capsules, gateway, verification, control, ledgers and model adapters
- `applications/sap/hypotheses/`: the explicit V2 hypothesis contract
- `eval/`: deterministic generator, configurations, runner, oracle metrics and calibration interfaces
- `tests/`: unit, security, deadline, reproducibility and Elasticsearch integration checks
- `scripts/research.py`: synthetic generation and guarded Elasticsearch lifecycle
- `scripts/analyze_experiment.py`: sealed-result tables, plots and failure catalog
- `scripts/render_case.py`: escaped self-contained analyst evidence view
- `docs/research/`: audit, architecture, threat model, cards, metrics, reproduction and publication decision
- `evidence/`: baseline manifests, validation logs and versioned synthetic experiment archives

Calibration code is implemented but refuses generator-only labels. No probability is reported as calibrated. Semantic-verifier outputs are separate from citation existence, but the current labels have no independent expert adjudication. Analyst feedback has a typed offline contract; no analyst study has been conducted.

## Security and disclosure

V2 accepts only synthetic sources in this workflow. It does not read the original ignored findings, logs, reports, audits, customer data or `.env`. Model-visible tools cannot issue arbitrary Elasticsearch DSL, writes, shell commands or outbound requests. The local Elasticsearch setup is unauthenticated on loopback for synthetic data only.

Do not describe this work as deployed, production-proven, customer-used, independently validated, calibrated, submitted or published. Customer instances, deployment, adoption and production outcomes are outside the permitted disclosure boundary. External release, manuscript submission, public blog content and pushes require the user's explicit approval and applicable company/authorship clearance.

See `docs/research/REPRODUCIBILITY.md` for exact workflows and `docs/research/METRICS.md` for denominator-level definitions.
