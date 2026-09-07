"""One-command fresh synthetic reproduction; no credential loading in default mode."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from eval.synthetic import generate
from eval.runner import freeze,evaluate
from core.v2.elasticsearch import seed_dataset


def main():
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--memory',action='store_true')
    p.add_argument('--seed',type=int,default=20260906);p.add_argument('--groups',type=int,default=3)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    data=out/'dataset';generate(data,seed=a.seed,groups=a.groups)
    es=None
    if not a.memory:
        seeded=seed_dataset(data);es={k:seeded[k] for k in ('url','index')}
    freeze(data,out/'protocol.json')
    evaluate(data,out/'protocol.json',out/'experiment',splits=('test','challenge'),es=es,workers=2)
    from scripts.analyze_experiment import analyze
    analyze(out/'experiment',out/'analysis')


if __name__=='__main__':main()
