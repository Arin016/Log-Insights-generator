"""Validate reviewer annotations and derive agreement without promoting them to truth."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.v2.contracts import canonical_json, digest
from core.v2.review import ReviewAnnotation


def validate(package: Path, annotations: Path, output: Path, *, minimum_reviewers: int) -> dict:
    if minimum_reviewers < 1:
        raise ValueError("minimum_reviewers must be positive")
    manifest = json.loads((package / "manifest.json").read_text())
    package_id = manifest["package_id"]
    cases = {item["case_id"]: item for item in manifest["cases"]}
    event_ids = {}
    for case_id, entry in cases.items():
        payload = json.loads((package / case_id / "case.json").read_text())
        if digest(payload) != entry["case_hash"]:
            raise ValueError("review case hash mismatch")
        event_ids[case_id] = {event["event_id"] for event in payload["events"]}
    grouped = defaultdict(list)
    seen = set()
    for path in sorted(annotations.glob("*.json")):
        review = ReviewAnnotation.model_validate_json(path.read_text())
        if review.package_id != package_id or review.case_id not in cases:
            raise ValueError("annotation belongs to another package or case")
        identity = (review.case_id, review.reviewer_id)
        if identity in seen:
            raise ValueError("duplicate reviewer/case annotation")
        seen.add(identity)
        cited = set(review.supporting_event_ids) | set(review.contradicting_event_ids)
        if not cited <= event_ids[review.case_id]:
            raise ValueError("annotation cites an event outside its case")
        grouped[review.case_id].append(review)
    rows = []
    complete = True
    for case_id in sorted(cases):
        reviews = grouped[case_id]
        enough = len(reviews) >= minimum_reviewers
        complete &= enough
        pattern = {review.pattern_present for review in reviews}
        disposition = {review.recommended_disposition for review in reviews}
        rows.append({
            "case_id": case_id, "reviewer_count": len(reviews), "minimum_met": enough,
            "pattern_agreement": next(iter(pattern)) if len(pattern) == 1 and reviews else "DISAGREEMENT",
            "disposition_agreement": next(iter(disposition)) if len(disposition) == 1 and reviews else "DISAGREEMENT",
            "median_review_seconds": median(r.review_seconds for r in reviews) if reviews else None,
        })
    report = {
        "schema_version": "ff-blinded-review-summary-v1", "package_id": package_id,
        "status": "COMPLETE" if complete else "INCOMPLETE", "minimum_reviewers": minimum_reviewers,
        "annotation_count": sum(len(value) for value in grouped.values()), "cases": rows,
        "provenance": "blinded-review-attested",
        "calibration_eligible": False,
        "claim_boundary": "Agreement on synthetic generator cases is analyst-study evidence, not independent real-world ground truth.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(canonical_json(report) + "\n")
    file_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(file_hash + "  " + output.name + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--minimum-reviewers", type=int, default=2)
    args = parser.parse_args()
    report = validate(args.package, args.annotations, args.output, minimum_reviewers=args.minimum_reviewers)
    print(f"{report['status']}: {report['annotation_count']} validated annotations")


if __name__ == "__main__":
    main()
