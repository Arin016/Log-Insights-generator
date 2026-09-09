# Multi-agent blinded review study

Status: development evidence, September 9, 2026. This is an AI-only review study,
not human expert adjudication and not calibration data.

## Question

Can multiple isolated reviewers reach the intended bounded interpretation of
label-free synthetic evidence packages, and can the review workflow expose
ambiguity in its own instructions?

## Reviewers and isolation

Three isolated `gpt-5.6-sol` reviewers used high reasoning effort with distinct
roles: audit/compliance, security/adversarial and systems/reliability. Each was
instructed to read only its label-free package, not the corpus, generator,
`label.json`, repository history or another reviewer's annotations. All judgments
cited event IDs from the assigned case. This is role-prompt diversity within one
model family, not independent human or cross-model validation.

## Development round: interface defect

The first twelve-case package omitted the explicit hypothesis and allowed enum
rubric. Although all 36 annotations validated mechanically, the reviewers agreed
on the pattern for only six cases and on disposition for only one. Each reviewer
independently identified missing decision rules around the time bound, identity,
authorization, rollback and source completeness.

This round is retained as failure analysis. It is not an effectiveness result.
The exporter was corrected to include `REVIEW_INSTRUCTIONS.md`, which defines the
bounded hypothesis and allowed outputs while still excluding case answers,
categories, groups, splits and fault schedules.

## Fresh corrected-rubric round

A new corpus seed (`20260911`) and a new twelve-case sample were used after the
interface correction. Package ID: `review-463145323acddcfb`.
The label-free package, 36 annotations and validator summary are preserved in
`evidence/experiments/ai-blinded-review-20260909.tar.gz`; its adjacent manifest
records SHA-256 `2db4464130a4243325acd32f04a4693900e755b8a39ac9f26f0a9aaa6ea8822c`.

- 36/36 annotations passed schema, package identity, attestation and in-case
  evidence-reference validation.
- All three reviewers agreed on `pattern_present` for 12/12 cases.
- All three reviewers agreed on the recommended disposition for 12/12 cases.
- After unblinding, consensus matched the generator disposition on 11/12 cases.
- The remaining case had a hidden evaluator-side `tool_error` schedule. Because
  fault schedules were intentionally excluded from the human-visible package,
  reviewers could assess the evidence pattern but could not infer the runtime
  `FAILED` outcome. On the eleven cases whose expected disposition was observable
  from the review package, consensus matched 11/11.

The selected cases included ordinary positive evidence, duplicate/reordered and
schema-variant positives, no-evidence, pending, conflicting, rollback,
missing-source and three instruction-injection variants. The missing-source case
was unanimously routed to review, and all three visible injection cases were
unanimously routed to unsafe input after the rubric correction.

## Interpretation

This study supports three narrow engineering statements:

1. The blinded-review tooling can enforce case/package identity and evidence-ID
   validity across multiple isolated annotations.
2. An underspecified review interface produced observable disagreement, and a
   predeclared rubric correction removed that ambiguity on a fresh synthetic
   sample.
3. Runtime fault outcomes must be evaluated separately from evidence-package
   interpretation when the fault schedule is intentionally hidden.

It does not establish model accuracy, real-world threat detection, SAP fidelity,
human analyst utility, reviewer independence, calibrated confidence or paper
readiness. Reported `review_seconds` were reviewer-entered rather than captured by
an external timing harness and must not be presented as analyst-time measurement.

## Next gate

The next non-duplicative step is human review or externally constructed cases.
Repeating more reviewers from the same model family on the same generator would
increase execution count without adding an independent evidence source.
