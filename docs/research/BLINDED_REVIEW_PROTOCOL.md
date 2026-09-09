# Blinded synthetic review protocol

This workflow measures whether independent reviewers can understand and assess
the evidence packages. It does not transform synthetic cases into real-world
ground truth.

## Export

Use a newly generated corpus and an unused output directory:

```bash
.venv/bin/python scripts/export_blinded_review.py CORPUS REVIEW-PACKAGE \
  --limit 20 --seed 20260909
```

The exporter reads `input.json` only. The package excludes generator labels,
categories, splits, groups and fault schedules. Each reviewer receives a separate
copy and completes `annotation.template.json` without accessing labels or another
reviewer's work.

Ask at least two reviewers with relevant audit, access-governance or security
experience to record a pseudonymous ID, role, evidence IDs, disposition, missing
information, confidence and review time. Keep completed annotations outside the
public repository until disclosure has been reviewed.

## Validate and summarize

Place completed annotation files in one directory and run:

```bash
.venv/bin/python scripts/validate_blinded_review.py REVIEW-PACKAGE ANNOTATIONS summary.json \
  --minimum-reviewers 2
```

The validator rejects foreign cases, duplicate reviewer/case pairs, invalid event
citations and incomplete attestations. Its public-safe summary records reviewer
counts, agreement and median review time without copying reviewer notes.

## Interpretation boundary

The resulting provenance is `blinded-review-attested`, not
`independent-adjudicated`, and the output is deliberately ineligible for the
calibration interface. Agreement can support an analyst-usability statement for
these synthetic cases. It cannot support fraud-detection accuracy, SAP fidelity,
real-world prevalence, calibrated probabilities or publication novelty.

For stronger evidence, an external domain owner must construct cases independently
of this generator, define labels before model execution, and reserve untouched
development/test groups. That is a separate protocol and should retain the
reviewers' original signed or otherwise attributable records privately.
