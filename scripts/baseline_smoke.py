"""Execute legacy orchestrator with new synthetic input and a scripted investigator.

Never starts ACP, loads .env, queries ES or reads prior outputs.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
safe = tempfile.mkdtemp(prefix="ff-baseline-")
os.environ["DATA_DIR"] = safe + "/data"
os.environ["LOG_DIR"] = safe + "/logs"

from applications.sap.parser import parse_log_line
from applications.sap.catalogs import load_use_case
from tests.test_baseline import synthetic_line
from core.orchestrator.pipeline import run_pipeline
from core.contracts import Finding, ConfidenceFactors
from run_local import derive_rak_metadata_from_events


def main():
    event = parse_log_line(synthetic_line())
    def scripted(**_):
        return [Finding(rak_id=event.request_access_key, use_case="vendor_master_manipulation",
            title="Synthetic bank field changed", severity="MEDIUM", confidence=.8,
            confidence_factors=ConfidenceFactors(sufficient_context=True,
                unambiguous_evidence=True, pattern_clear=True, scope_unambiguous=True),
            evidence_event_ids=[event.event_id], affected_session_ids=[event.session_id],
            reasoning="Synthetic bank field changed from SYNTH-A to SYNTH-B.")]
    report = run_pipeline(rak_metadata=derive_rak_metadata_from_events([event]),
        parsed_events=[event], event_store=None,
        use_case_configs={"vendor_master_manipulation": load_use_case("vendor_master_manipulation")},
        custom_overrides=[], register_tools_fn=lambda _: None, react_runner_fn=scripted)
    out = ROOT / "evidence/baseline/smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as f:
        json.dump({"synthetic": True, "model": "scripted-not-an-LLM",
            "baseline_commit": "2a3c28bec9b1f187af349767da7d4e74f6982d32",
            "report": report.model_dump(mode="json"),
            "limitations": "Legacy call/cost metadata is not trustworthy; this is control-flow smoke only."}, f, indent=2)
    print(out)


if __name__ == "__main__":
    main()
