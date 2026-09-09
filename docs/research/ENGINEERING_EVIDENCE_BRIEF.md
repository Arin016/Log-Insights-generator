# Engineering evidence brief

This page is the shortest defensible review path through FF Insights V2. It is
not a paper abstract and does not add claims beyond the repository's sealed
evidence.

## Problem framed

Long audit-event histories create two distinct risks for an AI investigation:
putting everything in one prompt is costly and can bury relevant evidence, while
retrieval can omit decisive context. The engineering question here is therefore
not merely whether a model can write a plausible insight. It is whether a bounded
system can preserve provenance, retrieve additional evidence, reject unsupported
claims, search for contradictions and expose incomplete coverage.

The implemented testbed deliberately narrows that question to one synthetic
vendor-bank-change/payment hypothesis. It is not presented as a general fraud
detector.

## System contribution

The V2 path combines:

- content-addressed immutable source snapshots;
- a typed case graph and bounded evidence capsules;
- scope-bound, read-only query capabilities instead of arbitrary search;
- atomic claims whose evidence references are checked against retrieved source
  records and fields;
- separate structural and semantic verification;
- deterministic contradiction and coverage checks;
- review, abstention and unsafe-input outcomes rather than forced answers;
- parent-process deadlines, resource accounting and hash-sealed run ledgers.

The important design boundary is that model output is a proposal. Deterministic
code controls scope, evidence eligibility, budgets and final policy state.

## Evidence available

The frozen scripted comparison at commit `6604e6f` contains 19 configurations,
46 held-out synthetic variants and 874 case-runs from two generated families.
Those results support protocol and policy regression claims only. They do not
establish real-world or LLM effectiveness. See the
[final report](FINAL_REPORT.md), [metrics definitions](METRICS.md),
[reproduction protocol](REPRODUCIBILITY.md) and sealed material under
`evidence/`.

The small development-only Claude pilot is valuable chiefly because it found
failures hidden by the scripted adapter: overbroad claims entered review and one
missing-source investigation consumed its call allowance. The latter produced a
concrete harness correction recorded in [POST_STUDY_FIXES.md](POST_STUDY_FIXES.md).
The pilot is not held-out evidence and cannot rank models.

## Fast verification

```bash
.venv/bin/python -m pytest -q
```

As of September 9, 2026, the local suite passes 108 tests with one gated
Elasticsearch test skipped when its service is absent. A full synthetic
reproduction is documented in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

## What this artifact demonstrates

The repository provides inspectable evidence of AI-systems engineering:
requirements narrowing, threat modeling, provenance, bounded agent-tool
interaction, selective prediction, failure analysis, reproducible experiments
and explicit publication gates. The strongest signal is not a headline accuracy
number; it is the traceable path from a failed live-model behavior to a tested
control-layer correction.

## What it does not demonstrate

It does not demonstrate customer deployment, production adoption, calibrated
probabilities, independent expert labels, analyst utility, broad threat coverage,
real-world fraud performance, manuscript submission or publication. The
[paper decision](PAPER_DECISION.md) remains **NO-GO** until its listed evidence
gates are met.
