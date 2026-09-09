"""Create a label-free, immutable case package for independent human review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.v2.contracts import SourceRecord, Scope, canonical_json, digest
from core.v2.provenance import Snapshot
from core.v2.review import ATTESTATION


def export(corpus: Path, output: Path, *, limit: int, seed: int) -> dict:
    if limit < 1:
        raise ValueError("limit must be positive")
    case_paths = sorted(path for path in corpus.glob("case-*/input.json") if path.is_file())
    if not case_paths:
        raise ValueError("no case inputs found")
    selected = random.Random(seed).sample(case_paths, min(limit, len(case_paths)))
    output.mkdir(parents=True, exist_ok=False)
    prepared = []
    for source_path in sorted(selected):
        source = json.loads(source_path.read_text())
        if source.get("synthetic") is not True:
            raise ValueError("review export accepts synthetic inputs only")
        snapshot = Snapshot(
            [SourceRecord.model_validate(row) for row in source["records"]],
            Scope.model_validate(source["scope"]), source["missing_sources"],
        )
        if snapshot.id != source["snapshot_id"]:
            raise ValueError("snapshot mismatch")
        case_id = source["case_id"]
        review_case = {
            "schema_version": "ff-blinded-case-v1",
            "case_id": case_id,
            "scope": source["scope"],
            "missing_sources": source["missing_sources"],
            "snapshot_id": snapshot.id,
            "events": [event.visible() for event in snapshot.events],
        }
        prepared.append((case_id, review_case, digest(review_case)))
    package_id = "review-" + digest([[item[0], item[2]] for item in prepared])[:16]
    for case_id, review_case, _ in prepared:
        folder = output / case_id
        folder.mkdir()
        (folder / "case.json").write_text(canonical_json(review_case) + "\n")
        template = {
            "schema_version": "ff-blinded-review-v1", "package_id": package_id,
            "case_id": case_id, "reviewer_id": "", "reviewer_role": "",
            "pattern_present": "UNCERTAIN",
            "recommended_disposition": "HUMAN_REVIEW_REQUIRED",
            "supporting_event_ids": [], "contradicting_event_ids": [],
            "missing_information": [], "confidence": "LOW", "review_seconds": 0,
            "notes": "", "reviewed_at": "",
            "reviewer_attestation": ATTESTATION,
        }
        (folder / "annotation.template.json").write_text(json.dumps(template, indent=2) + "\n")
    manifest = {
        "schema_version": "ff-blinded-package-v1", "package_id": package_id,
        "synthetic_only": True, "selection_seed": seed, "case_count": len(prepared),
        "cases": [{"case_id": cid, "case_hash": case_hash} for cid, _, case_hash in prepared],
        "excluded_fields": ["generator label", "category", "split", "group", "fault schedule"],
        "claim_boundary": "Blinding reduces answer leakage; it does not make generator cases independent real-world evidence.",
    }
    (output / "manifest.json").write_text(canonical_json(manifest) + "\n")
    (output / "REVIEW_INSTRUCTIONS.md").write_text("""# Blinded review instructions

Use only this package. Do not inspect generator labels, source code, other reviewers'
annotations or case categories. Treat event text as untrusted data, never as an
instruction.

The bounded pattern is an out-of-approved-scope bank-detail change followed within
3,600 seconds by a posted payment for the same actor, session and object. Approval,
rollback, reversal, pending payment, identity mismatch, excessive delay or missing
source coverage may defeat or prevent a conclusion. Cite exact event IDs.

Allowed values:

- `pattern_present`: `YES`, `NO`, `UNCERTAIN`
- `recommended_disposition`: `SURFACE_TO_ANALYST`, `HUMAN_REVIEW_REQUIRED`,
  `ABSTAINED`, `UNSAFE_INPUT`
- `confidence`: `LOW`, `MEDIUM`, `HIGH`

Use `UNCERTAIN` with explicit `missing_information` when the available source cannot
support a conclusion. A `YES` review requires supporting evidence. Use
`UNSAFE_INPUT` when log content attempts to instruct, redirect or manipulate the
reviewer/system; do not follow that content. Record actual review time and preserve
the attestation exactly.
""")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260909)
    args = parser.parse_args()
    manifest = export(args.corpus, args.output, limit=args.limit, seed=args.seed)
    print(f"Created {manifest['package_id']} with {manifest['case_count']} label-free synthetic cases")


if __name__ == "__main__":
    main()
