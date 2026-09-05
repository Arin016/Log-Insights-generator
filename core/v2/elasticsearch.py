"""Dedicated loopback Elasticsearch, explicit mappings and sealed synthetic indices."""
from __future__ import annotations

import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk

from .contracts import CanonicalEvent, digest

VERSION="8.13.4"
CLUSTER="ff-insights-synthetic"
PREFIX="ff-insights-synthetic-v2-"
OWNER="ff-insights-v2-generator"


def client(url):
    parsed=urlparse(url)
    if parsed.scheme!="http" or parsed.hostname not in {"127.0.0.1","localhost","::1"} or parsed.username or parsed.password or parsed.path not in {"","/"}:
        raise ValueError("dedicated credential-free loopback ES only")
    return Elasticsearch(url,request_timeout=5,max_retries=0,retry_on_timeout=False)


def check_cluster(es):
    info=es.info()
    if info["cluster_name"]!=CLUSTER or info["version"]["number"]!=VERSION:
        raise PermissionError("unexpected Elasticsearch cluster/version")
    return dict(info)


def wait_ready(url,timeout=60):
    es=client(url);deadline=time.monotonic()+timeout;last=None
    while time.monotonic()<deadline:
        try:
            info=check_cluster(es)
            health=es.cluster.health(wait_for_status="yellow",timeout="2s")
            if not health.get("timed_out") and health["status"] in {"yellow","green"}:return info
        except PermissionError:raise
        except Exception as exc:last=type(exc).__name__
        time.sleep(min(.2,max(0,deadline-time.monotonic())))
    raise TimeoutError(f"synthetic ES readiness failed: {last}")


def validate_index_name(index):
    if not re.fullmatch(PREFIX+r"[a-f0-9]{16}",index):raise PermissionError("not a dedicated synthetic index")


def mappings(dataset_hash):
    properties={name:{"type":"keyword"} for name in CanonicalEvent.model_fields}
    for name in ("occurred_at","ingested_at"):properties[name]={"type":"date"}
    for name in ("text","raw_json"):properties[name]={"type":"text","index":False}
    return {"dynamic":"strict","_meta":{"owner":OWNER,"dataset_hash":dataset_hash,"synthetic":True},"properties":properties}


def check_index(es,index,dataset_hash=None):
    validate_index_name(index)
    mapping=es.indices.get_mapping(index=index)
    if set(mapping)!={index}:raise PermissionError("index aliases forbidden")
    meta=mapping[index]["mappings"].get("_meta",{})
    if meta.get("owner")!=OWNER or meta.get("synthetic") is not True:
        raise PermissionError("unknown index ownership")
    if dataset_hash and meta.get("dataset_hash")!=dataset_hash:raise PermissionError("different dataset")
    return meta


def seed_dataset(root,url="http://127.0.0.1:19200"):
    from eval.synthetic import load_case
    root=Path(root);manifest=json.loads((root/"manifest.json").read_text())
    recorded=manifest["dataset_hash"]
    if digest({k:v for k,v in manifest.items() if k!="dataset_hash"})!=recorded:raise ValueError("dataset manifest integrity")
    for path,expected in manifest["files"].items():
        if Path(path).is_absolute() or ".." in Path(path).parts:raise ValueError("manifest path escape")
        if digest(json.loads((root/path).read_text()))!=expected:raise ValueError("dataset file integrity")
    es=client(url);info=check_cluster(es);index=PREFIX+recorded[:16]
    events=[e for case in manifest["cases"] for e in load_case(root,case["case_id"]).events]
    if es.indices.exists(index=index):
        check_index(es,index,recorded)
    else:
        es.indices.create(index=index,mappings=mappings(recorded),settings={"number_of_shards":1,"number_of_replicas":0})
        bulk(es,({"_op_type":"create","_index":index,"_id":e.event_id,"_source":e.model_dump(mode="json")} for e in events),
             chunk_size=500,request_timeout=30)
        es.indices.refresh(index=index)
        es.indices.put_settings(index=index,settings={"index.blocks.write":True})
    # Idempotence is content-checked, not inferred from counts or the index name.
    if es.count(index=index)["count"]!=len(events):raise ValueError("seed count mismatch; explicit reset required")
    for offset in range(0,len(events),500):
        batch=events[offset:offset+500]
        docs=es.mget(index=index,ids=[e.event_id for e in batch])["docs"]
        for expected,doc in zip(batch,docs):
            if not doc.get("found") or CanonicalEvent.model_validate(doc["_source"])!=expected:
                raise ValueError("seed content mismatch")
    return {"index":index,"url":url,"dataset_hash":recorded,"events":len(events),"cases":len(manifest["cases"]),
            "elasticsearch_version":info["version"]["number"],"write_blocked":True}


def reset_index(url,index,dataset_hash):
    es=client(url);check_cluster(es);check_index(es,index,dataset_hash)
    es.indices.delete(index=index)


class ESBackend:
    def __init__(self,url,index):
        self.es=client(url);check_cluster(self.es);check_index(self.es,index)
        settings=self.es.indices.get_settings(index=index)[index]["settings"]["index"]
        if settings.get("blocks",{}).get("write")!="true":raise PermissionError("index must be write sealed")
        self.index=index

    def fetch(self,cap,query,after,size):
        filters=[{"term":{"tenant":cap.scope.tenant}},{"term":{"request":cap.scope.request}},
                 {"term":{"source_snapshot_id":cap.snapshot}},{"terms":{"source":list(cap.allowed_sources)}}]
        template=query.template
        if template=="seed_events":filters.append({"term":{"event_type":"BANK_CHANGE"}})
        elif template in {"events_by_object","contradictions_by_object"}:
            filters.append({"term":{"object_id":query.value}})
            if template=="contradictions_by_object":
                filters.append({"bool":{"minimum_should_match":1,"should":[
                    {"terms":{"event_type":["APPROVAL","REVERSAL","BANK_CHANGE"]}},
                    {"terms":{"status":["REVERSED","PENDING"]}}]}})
        elif template=="events_by_ids":filters.append({"terms":{"event_id":query.event_ids}})
        elif template=="events_by_tcode":filters.append({"term":{"tcode":query.value}})
        elif template=="events_by_session":filters.append({"term":{"session":query.value}})
        elif template=="events_in_time_window":filters.append({"range":{"occurred_at":{"gte":query.start,"lte":query.end}}})
        else:raise ValueError("unknown template")
        body={"query":{"bool":{"filter":filters}},"size":size,
              "sort":[{"occurred_at":{"order":"asc","format":"strict_date_optional_time"}},{"event_id":"asc"}],
              "track_total_hits":True}
        if after is not None:body["search_after"]=list(after)
        res=self.es.search(index=self.index,body=body)
        if res.get("timed_out") or res.get("_shards",{}).get("failed",0):raise TimeoutError("incomplete ES search")
        total=res["hits"]["total"]
        if total["relation"]!="eq":raise ValueError("exact count unavailable")
        return [CanonicalEvent.model_validate(hit["_source"]) for hit in res["hits"]["hits"]],total["value"]
