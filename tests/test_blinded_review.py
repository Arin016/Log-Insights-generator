import json
from pathlib import Path

import pytest

from core.v2.review import ATTESTATION, ReviewAnnotation
from eval.synthetic import case
from scripts.export_blinded_review import export
from scripts.validate_blinded_review import validate


def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"; root.mkdir()
    for category in ("positive", "missing_source"):
        source, label, intervention = case(101, 0, category, "development")
        folder = root / source["case_id"]; folder.mkdir()
        (folder / "input.json").write_text(json.dumps(source))
        (folder / "label.json").write_text(json.dumps(label))
        (folder / "intervention.json").write_text(json.dumps(intervention))
    return root


def annotation(package, case_id, reviewer, event_id):
    return {
        "schema_version":"ff-blinded-review-v1", "package_id":package,
        "case_id":case_id, "reviewer_id":reviewer, "reviewer_role":"domain analyst",
        "pattern_present":"YES", "recommended_disposition":"SURFACE_TO_ANALYST",
        "supporting_event_ids":[event_id], "contradicting_event_ids":[],
        "missing_information":[], "confidence":"HIGH", "review_seconds":60,
        "notes":"synthetic review", "reviewed_at":"2026-09-09T10:00:00+00:00",
        "reviewer_attestation":ATTESTATION,
    }


def test_review_contract_requires_evidence_and_timezone():
    raw=annotation("review-"+"0"*16,"case-x","reviewer-a","evt-x")
    ReviewAnnotation.model_validate(raw)
    raw["supporting_event_ids"]=[]
    with pytest.raises(ValueError): ReviewAnnotation.model_validate(raw)


def test_export_excludes_answers_and_validates_two_reviewers(tmp_path):
    package_dir=tmp_path/"package"
    manifest=export(corpus(tmp_path),package_dir,limit=1,seed=7)
    instructions=(package_dir/"REVIEW_INSTRUCTIONS.md").read_text()
    assert "SURFACE_TO_ANALYST" in instructions and "generator labels" in instructions
    case_id=manifest["cases"][0]["case_id"]
    case_payload=json.loads((package_dir/case_id/"case.json").read_text())
    assert "category" not in manifest["cases"][0] and "expected_terminal" not in case_payload
    event_id=case_payload["events"][0]["event_id"]
    annotations=tmp_path/"annotations";annotations.mkdir()
    for reviewer in ("reviewer-a","reviewer-b"):
        (annotations/f"{reviewer}.json").write_text(json.dumps(annotation(manifest["package_id"],case_id,reviewer,event_id)))
    report=validate(package_dir,annotations,tmp_path/"summary.json",minimum_reviewers=2)
    assert report["status"]=="COMPLETE"
    assert report["cases"][0]["pattern_agreement"]=="YES"
    assert not report["human_review_claim_allowed"]
    assert not report["calibration_eligible"]
