"""Freeze protocol, execute real harness variants, and preserve every case result."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import csv
import hashlib
import json
from pathlib import Path
import subprocess

from core.v2.contracts import canonical_json,digest,utcnow
from core.v2.engine import HarnessConfig,run_case
from core.v2.ledger import code_identity,verify_ledger
from .configurations import configurations
from .synthetic import load_case
from .metrics import case_metrics,aggregate

ROOT=Path(__file__).resolve().parents[1]


def source_hashes():
    files=subprocess.check_output(["git","ls-files"],cwd=ROOT).decode().splitlines()
    selected=[f for f in files if f.startswith(("core/v2/","eval/","applications/sap/hypotheses/")) or f=="requirements-lock.txt"]
    return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in selected}


def checked_manifest(dataset):
    dataset=Path(dataset)
    manifest=json.loads((dataset/"manifest.json").read_text())
    if digest({k:v for k,v in manifest.items() if k!="dataset_hash"})!=manifest["dataset_hash"]:
        raise ValueError("dataset manifest changed")
    for rel,expected in manifest["files"].items():
        path=Path(rel)
        if path.is_absolute() or ".." in path.parts:raise ValueError("dataset path escape")
        if digest(json.loads((dataset/path).read_text()))!=expected:raise ValueError("dataset file changed: "+rel)
    return manifest


def freeze(dataset,destination,*,live_model=None,model_digest=None,wall_seconds=60):
    manifest=checked_manifest(dataset)
    configs=[c.model_dump(mode="json") for c in configurations()]
    if live_model:
        if not model_digest:raise ValueError("live local model requires its installed digest")
        for config in configs:
            if config["adapter"]=="rules":continue
            config.update(adapter="ollama",model=live_model,verifier_model=live_model,
                          model_digest=model_digest,verifier_digest=model_digest)
            config["budgets"]["wall_seconds"]=wall_seconds
    protocol={"version":"2.0.0","created_at":utcnow(),"code":code_identity(),"source_hashes":source_hashes(),
        "dataset_hash":manifest["dataset_hash"],"configurations":configs,
        "split_policy":"Complete generated sibling families stay together. Challenge consumed once after protocol freeze.",
        "label_provenance":"Generator-authored, no independent domain experts or real logs.",
        "metric_version":"synthetic-oracle-2.0","bootstrap":"400 resamples of complete generated families",
        "model_evaluation":"LOCAL_OLLAMA_SYNTHETIC" if live_model else "SCRIPTED_HARNESS_ONLY; not LLM effectiveness",
        "fault_deadline_seconds":.5,
        "primary_metrics":["atomic_claim_precision","atomic_claim_recall","disposition_accuracy","review_volume","selective_risk"],
        "change_policy":"Do not tune against test/challenge failures. Preserve failure runs; a changed protocol requires a new corpus."}
    protocol["protocol_hash"]=digest(protocol)
    with Path(destination).open("x") as f:f.write(canonical_json(protocol)+"\n")
    return protocol


def evaluate(dataset,protocol_path,output,*,splits=("development",),names=None,es=None,workers=2,limit=None):
    dataset=Path(dataset);manifest=checked_manifest(dataset)
    protocol=json.loads(Path(protocol_path).read_text())
    if digest({k:v for k,v in protocol.items() if k!="protocol_hash"})!=protocol["protocol_hash"]:
        raise ValueError("protocol integrity failure")
    if manifest["dataset_hash"]!=protocol["dataset_hash"] or source_hashes()!=protocol["source_hashes"]:
        raise ValueError("dataset/code changed after freeze; create a new versioned protocol")
    identity=code_identity()
    if identity["dirty"]:raise ValueError("commit tracked changes before evaluation")
    cases=[c for c in manifest["cases"] if c["split"] in splits]
    if limit is not None:
        if set(splits)!={"development"}:raise ValueError("case limits allowed only for development")
        cases=cases[:limit]
    configs=[HarnessConfig.model_validate(c) for c in protocol["configurations"] if not names or c["name"] in names]
    if not cases or not configs:raise ValueError("empty experiment")
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    (out/"protocol.json").write_text(canonical_json(protocol)+"\n")
    experiment={"created_at":utcnow(),"code":identity,"protocol_hash":protocol["protocol_hash"],
        "dataset_hash":manifest["dataset_hash"],"splits":splits,"configs":[c.name for c in configs],"cases":len(cases),
        "workers":workers,"backend":es or "memory","status":"started"}
    (out/"experiment-start.json").write_text(canonical_json(experiment)+"\n")
    summaries={};allrows=[]
    with (out/"per-case.jsonl").open("x") as raw:
        for config in configs:
            rows=[]
            def work(item):
                snapshot=load_case(dataset,item["case_id"])
                intervention=json.loads((dataset/item["case_id"]/"intervention.json").read_text())
                # Avoid spending the normal 10s budget waiting for a deliberate timeout.
                # The same declared fault deadline applies to every harness variant.
                used=config
                if intervention.get("fault")=="timeout":
                    values=config.model_dump();values["budgets"]["wall_seconds"]=protocol["fault_deadline_seconds"]
                    used=HarnessConfig.model_validate(values)
                result,path=run_case(snapshot,used,out/config.name,dataset_hash=manifest["dataset_hash"],
                    intervention=intervention,es=es,identity=identity)
                verify_ledger(path)
                # Ground truth is first loaded in the evaluator, after the investigation completed.
                label=json.loads((dataset/item["case_id"]/"label.json").read_text())
                row=case_metrics(result,label,snapshot)
                row.update({"configuration":config.name,"run_path":str(path.relative_to(out)),"run_id":path.name})
                return row
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures={pool.submit(work,item):item for item in cases}
                for future in as_completed(futures):
                    row=future.result();rows.append(row);allrows.append(row)
                    raw.write(canonical_json(row)+"\n");raw.flush()
            summaries[config.name]=aggregate(rows)
            print(canonical_json({"configuration":config.name,"cases":len(rows),"states":summaries[config.name]["states"]}),flush=True)
    (out/"summary.json").write_text(canonical_json(summaries)+"\n")
    with (out/"table.csv").open("x",newline="") as f:
        writer=csv.writer(f);writer.writerow(["configuration","metric","numerator","denominator","value","family_bootstrap_95_interval"])
        for config,summary in summaries.items():
            for name,m in summary["metrics"].items():
                writer.writerow([config,name,m["numerator"],m["denominator"],m["value"],m.get("family_bootstrap_95_interval")])
    failures=[r for r in allrows if r["state"]!=r["expected_terminal"] or r["fp"] or r["fn"]]
    (out/"failures.json").write_text(canonical_json(failures)+"\n")
    experiment.update({"status":"completed","case_runs":len(allrows),"failure_catalog_entries":len(failures)})
    (out/"experiment-complete.json").write_text(canonical_json(experiment)+"\n")
    files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob("*")) if p.is_file()}
    (out/"experiment-seal.json").write_text(canonical_json({"files":files})+"\n")
    for p in out.rglob("*"):
        if p.is_file():p.chmod(0o444)
    return summaries


def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["freeze","evaluate"])
    p.add_argument("--dataset",required=True);p.add_argument("--protocol",required=True)
    p.add_argument("--output");p.add_argument("--splits",default="development")
    p.add_argument("--configs");p.add_argument("--workers",type=int,default=2);p.add_argument("--limit",type=int)
    p.add_argument("--es-index");p.add_argument("--es-url",default="http://127.0.0.1:19200")
    p.add_argument("--live-local-model");p.add_argument("--model-digest");p.add_argument("--wall-seconds",type=float,default=60)
    a=p.parse_args()
    if a.command=="freeze":print(freeze(a.dataset,a.protocol,live_model=a.live_local_model,model_digest=a.model_digest,wall_seconds=a.wall_seconds)["protocol_hash"])
    else:
        if not a.output:p.error("--output required")
        if not 1<=a.workers<=4:p.error("workers must be 1..4")
        evaluate(a.dataset,a.protocol,a.output,splits=tuple(a.splits.split(",")),names=a.configs.split(",") if a.configs else None,
            es={"url":a.es_url,"index":a.es_index} if a.es_index else None,workers=a.workers,limit=a.limit)


if __name__=="__main__":main()
