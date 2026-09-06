"""Cross-process spending reservations survive worker timeout and ambiguous responses."""
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from .control import Exhausted
from .contracts import utcnow


class SpendingLedger:
    @classmethod
    def initialize(cls,path,limit_microusd):
        if not isinstance(limit_microusd,int) or limit_microusd<=0:raise ValueError("positive explicit spending limit required")
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE budget (limit_microusd INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.execute("INSERT INTO budget VALUES (?,?)",(limit_microusd,utcnow()))
            db.execute("CREATE TABLE calls (id TEXT PRIMARY KEY, run_id TEXT, model TEXT, reserved INTEGER, actual INTEGER, usage TEXT, created_at TEXT)")
        return cls(path)

    def __init__(self,path):
        self.path=Path(path).resolve()
        if not self.path.is_file():raise ValueError("initialize an explicitly approved spending ledger first")

    def connect(self):return sqlite3.connect(self.path.as_uri()+"?mode=rw",uri=True,timeout=10)

    def reserve(self,amount,run_id,model):
        if not isinstance(amount,int) or amount<=0:raise ValueError("positive reservation required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            limit=db.execute("SELECT limit_microusd FROM budget").fetchone()[0]
            used=db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM calls").fetchone()[0]
            if used+amount>limit:raise Exhausted("approved_api_spending_limit")
            ident=uuid4().hex
            db.execute("INSERT INTO calls VALUES (?,?,?,?,NULL,NULL,?)",(ident,run_id,model,amount,utcnow()))
        return ident

    def settle(self,ident,amount,usage):
        if not isinstance(amount,int) or amount<0:raise ValueError("nonnegative measured cost required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT reserved,actual FROM calls WHERE id=?",(ident,)).fetchone()
            if not row or row[1] is not None:raise ValueError("unknown or settled reservation")
            if amount>row[0]:raise ValueError("provider usage exceeds conservative reservation; retain reservation and stop")
            db.execute("UPDATE calls SET actual=?,usage=? WHERE id=?",(amount,json.dumps(usage,sort_keys=True),ident))

    def snapshot(self):
        with self.connect() as db:
            limit,created=db.execute("SELECT * FROM budget").fetchone()
            rows=db.execute("SELECT id,run_id,model,reserved,actual,usage,created_at FROM calls ORDER BY created_at,id").fetchall()
        calls=[dict(zip(("id","run_id","model","reserved_microusd","actual_microusd","usage_json","created_at"),r)) for r in rows]
        return {"limit_microusd":limit,"created_at":created,"calls":calls,
                "measured_microusd":sum(r[4] for r in rows if r[4] is not None),
                "unresolved_reserved_microusd":sum(r[3] for r in rows if r[4] is None)}
