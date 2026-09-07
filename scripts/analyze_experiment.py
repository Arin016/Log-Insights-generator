"""Verify sealed experiment and derive standalone research tables/figures."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.runtime/matplotlib'))
from core.v2.contracts import canonical_json


def analyze(source,destination):
    source=Path(source);out=Path(destination)
    seal=json.loads((source/'experiment-seal.json').read_text())
    actual={str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}
    if actual!=set(seal['files'])|{'experiment-seal.json'}:raise ValueError('experiment inventory differs')
    for rel,expected in seal['files'].items():
        p=Path(rel)
        if p.is_absolute() or '..' in p.parts:raise ValueError('invalid seal path')
        if hashlib.sha256((source/p).read_bytes()).hexdigest()!=expected:raise ValueError('experiment integrity failure')
    rows=[json.loads(line) for line in (source/'per-case.jsonl').read_text().splitlines()]
    summary=json.loads((source/'summary.json').read_text())
    experiment=json.loads((source/'experiment-complete.json').read_text())
    out.mkdir(parents=True,exist_ok=False)
    baseline=['rules','naive_single_pass','scoped_single_pass','demo_style_react','v2_no_semantic','v2']
    names=[n for n in baseline if n in summary]+[n for n in summary if n not in baseline]
    with (out/'comparison.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['configuration','case_runs','tp','fp','fn','disposition_correct','disposition_total','surfaced_claims','median_seconds','p95_seconds','reported_cost_usd'])
        for name in names:
            s=summary[name];m=s['metrics']['disposition_accuracy'];c=s['confusion']
            writer.writerow([name,s['cases'],c['tp'],c['fp'],c['fn'],m['numerator'],m['denominator'],c['tp']+c['fp'],s['latency_seconds']['median'],s['latency_seconds']['p95'],s['monetary_cost_usd']])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
    fig,ax=plt.subplots(figsize=(10,max(5,len(names)*.33)))
    nums=[summary[n]['metrics']['disposition_accuracy'] for n in names]
    ys=list(range(len(names)))
    ax.barh(ys,[m['value'] or 0 for m in nums],color=['#156e73' if n=='v2' else '#8faab8' for n in names])
    ax.set_yticks(ys,names);ax.invert_yaxis();ax.set_xlim(0,1.16)
    ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Correct terminal disposition / all case-runs')
    for y,m in zip(ys,nums):ax.text((m['value'] or 0)+.015,y,f"{m['numerator']}/{m['denominator']}",va='center',fontsize=9)
    mode=json.loads((source/'protocol.json').read_text())['model_evaluation']
    fig.suptitle('Synthetic feasibility study — terminal decisions',x=.02,ha='left',weight='bold',fontsize=15)
    fig.text(.02,.015,f"{mode}\n{experiment['cases']} cases per configuration; generated families are dependent within each group. No real-world inference.",fontsize=8)
    fig.tight_layout(rect=(0,.08,1,.95));fig.savefig(out/'disposition.png',dpi=170);fig.savefig(out/'disposition.svg');plt.close(fig)
    import textwrap
    from collections import defaultdict
    grouped=defaultdict(list)
    for name in names:
        s=summary[name];coverage=s['metrics']['surface_coverage'];risk=s['metrics']['selective_risk']
        if risk['value'] is not None:grouped[(coverage['value'],risk['value'])].append(name)
    fig,ax=plt.subplots(figsize=(12,6))
    for i,((coverage,risk),members) in enumerate(sorted(grouped.items()),1):
        ax.scatter(coverage,risk,s=80);ax.annotate(str(i),(coverage,risk),xytext=(6,7),textcoords='offset points')
        first=summary[members[0]]['metrics'];c=first['surface_coverage'];r=first['selective_risk']
        label=f"{i}. "+', '.join(members)+f"\nCoverage {c['numerator']}/{c['denominator']}; risk {r['numerator']}/{r['denominator']}"
        label='\n'.join(textwrap.fill(line,47) for line in label.splitlines())
        fig.text(.62,.84-(i-1)*.19,label,va='top',fontsize=8)
    ax.set_xlim(-.02,1.02);ax.set_ylim(-.02,1.02);ax.xaxis.set_major_formatter(PercentFormatter(1));ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlabel('Cases with a surfaced claim / all cases');ax.set_ylabel('Unsupported surfaced claims / all surfaced claims')
    fig.suptitle('Risk and coverage at frozen policies',fontsize=14,x=.02,ha='left')
    fig.text(.02,.015,'No calibrated threshold sweep. Configurations with no surfaced claims have undefined risk and are omitted.',fontsize=8)
    fig.subplots_adjust(right=.58,bottom=.15,top=.9,left=.08);fig.savefig(out/'risk-coverage.png',dpi=170);plt.close(fig)
    failures={}
    for row in rows:
        if row['state']!=row['expected_terminal'] or row['fp'] or row['fn']:
            key=row['configuration']+' / '+row['category']+' / '+row['state']
            failures.setdefault(key,[]).append({'case_id':row['case_id'],'run_path':row['run_path'],'fp':row['fp'],'fn':row['fn'],'failure':row.get('failure')})
    (out/'failure-catalog.json').write_text(canonical_json(failures)+'\n')
    manifest={'source_experiment':str(source.resolve()),'source_seal_sha256':hashlib.sha256((source/'experiment-seal.json').read_bytes()).hexdigest(),
              'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'case_runs':len(rows),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())}}
    (out/'analysis-manifest.json').write_text(canonical_json(manifest)+'\n')
    print(json.dumps({'case_runs':len(rows),'configurations':len(summary),'output':str(out)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args();analyze(a.source,a.destination)
