# Audited baseline versus research V2

Baseline commit: `2a3c28bec9b1f187af349767da7d4e74f6982d32`. All 68 tracked files read. Original working tree clean; ignored files inventoried by name only. Local clone contains no original ignored files.

| Component | Baseline | V2 acceptance |
|---|---|---|
| Parsing/scoping | SAP pipe parser, catalogs, three active families | Immutable synthetic provenance and one explicitly labeled family |
| Queries | Request-scoped ES, nine tools, batch loses truncation | Tenant/request/snapshot capability, typed templates, complete pagination metadata |
| Agent | Stateful ACP; repair turns uncounted, soft deadline | Isolated model adapter; external cancellation and complete accounting |
| Evidence | Event-ID membership only | Field hashes, deterministic joins/paths, domain/semantic/contradiction checks |
| Triage | Model-provided score at 0.70 | Separate severity/support/coverage; interpretable selective policy |
| Persistence | Deletes prior report/findings; truncated audit | Exclusive creation, content manifests and append-only run IDs |
| Evaluation | Empty package | Synthetic generator, labels, split registry, baselines and ablations |

Additional audit findings: `session_id.keyword` aggregation conflicts with keyword mapping; parser accepts JSON arrays/scalars then calls `.get`; scope rules can short-circuit before validating an unknown key; no tenant in legacy event contract; Flask dependency absent from requirements. Legacy README's hard-cap/full-audit/evidence claims overstate the code. The old paper-plan production-case-study outline conflicts with the governing disclosure boundary and is rejected.

Legacy execution is preserved in Git and exercised using `scripts/baseline_smoke.py`, a scripted investigator and generated pipe row. No actual model behavior is measured by that smoke. V2 uses a separate entry point and carries no effectiveness claims for the legacy PO/SO families.
