"""Synthetic corpus and local Elasticsearch lifecycle; never loads a .env."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from eval.synthetic import generate
from core.v2.elasticsearch import wait_ready,seed_dataset,reset_index


def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["generate","health","seed","reset"])
    p.add_argument("--dataset",default="artifacts/dataset-v2")
    p.add_argument("--seed",type=int,default=20260905)
    p.add_argument("--groups",type=int,default=18)
    p.add_argument("--url",default="http://127.0.0.1:19200")
    p.add_argument("--index")
    p.add_argument("--dataset-hash")
    args=p.parse_args()
    if args.command=="generate":
        m=generate(args.dataset,args.seed,args.groups)
        result={"dataset_hash":m["dataset_hash"],"cases":len(m["cases"]),"path":args.dataset}
    elif args.command=="health": result=wait_ready(args.url)
    elif args.command=="seed":result=seed_dataset(args.dataset,args.url)
    else:
        if not args.index or not args.dataset_hash:p.error("reset requires exact --index and --dataset-hash")
        reset_index(args.url,args.index,args.dataset_hash);result={"deleted":args.index}
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
