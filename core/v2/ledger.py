"""Exclusive run creation and hash-chained observable traces, without hidden reasoning."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from .contracts import canonical_json, digest, utcnow


def code_identity():
    root=Path(__file__).resolve().parents[2]
    return {"commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=root).decode().strip(),
        "dirty":bool(subprocess.check_output(["git","status","--porcelain","--untracked-files=no"],cwd=root)),
        "python":sys.version.split()[0]}


class RunLedger:
    def __init__(self,root,manifest,run_id=None):
        self.run_id=run_id or "run-"+uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",self.run_id): raise ValueError("invalid run id")
        self.path=Path(root)/self.run_id
        self.path.mkdir(parents=True,exist_ok=False)
        self.closed=False; self.previous="0"*64; self.sequence=0
        self.write("manifest.json",manifest|{"run_id":self.run_id,"created_at":utcnow()})
        self.trace=(self.path/"trace.jsonl").open("x",encoding="utf-8")

    def write(self,name,value):
        if self.closed: raise ValueError("ledger closed")
        path=self.path/name
        if path.parent!=self.path or name in {"trace.jsonl","seal.json"}: raise ValueError("invalid artifact path")
        with path.open("x",encoding="utf-8") as f:
            f.write(canonical_json(value)+"\n"); f.flush(); os.fsync(f.fileno())

    def append(self,event):
        if self.closed: raise ValueError("ledger closed")
        record={"sequence":self.sequence,"previous":self.previous,"event":event}
        record["hash"]=digest(record)
        self.trace.write(canonical_json(record)+"\n"); self.trace.flush()
        self.previous=record["hash"]; self.sequence+=1

    def seal(self):
        if self.closed: raise ValueError("ledger already sealed")
        self.trace.flush(); os.fsync(self.trace.fileno()); self.trace.close()
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.path.iterdir()) if p.is_file()}
        with (self.path/"seal.json").open("x") as f:
            f.write(canonical_json({"files":hashes,"last_trace_hash":self.previous,"events":self.sequence})+"\n")
        self.closed=True
        for p in self.path.iterdir(): p.chmod(0o444)


def verify_ledger(path):
    path=Path(path); seal=json.loads((path/"seal.json").read_text())
    if {p.name for p in path.iterdir()} != set(seal["files"])|{"seal.json"}: raise ValueError("artifact inventory changed")
    for name,expected in seal["files"].items():
        if Path(name).name != name or hashlib.sha256((path/name).read_bytes()).hexdigest()!=expected:
            raise ValueError("artifact integrity failure")
    previous="0"*64; count=0
    for line in (path/"trace.jsonl").read_text().splitlines():
        record=json.loads(line); recorded_hash=record.pop("hash")
        if record["sequence"]!=count or record["previous"]!=previous or digest(record)!=recorded_hash:
            raise ValueError("trace chain failure")
        previous=recorded_hash; count+=1
    if previous!=seal["last_trace_hash"] or count!=seal["events"]: raise ValueError("trace completeness failure")
    return True
