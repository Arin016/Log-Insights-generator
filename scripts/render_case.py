"""Render a verified run as an escaped, self-contained analyst evidence report."""
import argparse
from html import escape
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.v2.ledger import verify_ledger
from core.v2.provenance import Snapshot
from core.v2.contracts import SourceRecord,Scope


def render(run,output):
    run=Path(run);verify_ledger(run)
    report=json.loads((run/'report.json').read_text());manifest=json.loads((run/'manifest.json').read_text())
    source=json.loads((run/'input.json').read_text())
    snapshot=Snapshot([SourceRecord.model_validate(r) for r in source['records']],Scope.model_validate(source['scope']),source['missing_sources'])
    def e(value):return escape(str(value),quote=True)
    def pre(value):return '<pre>'+e(json.dumps(value,indent=2))+'</pre>'
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">',
        '<title>FF Insights — synthetic evidence review</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#16313b;background:#fafbfc}h1{font-size:32px}h2{margin-top:32px}h3{margin-top:0}section{background:white;border:1px solid #ccd7dd;border-radius:10px;padding:22px;margin:18px 0}pre{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f4f7;padding:14px}a{color:#076b7b}code{overflow-wrap:anywhere}dl{display:grid;grid-template-columns:160px 1fr;gap:8px}dt{font-weight:600}dd{margin:0;overflow-wrap:anywhere}.state{display:inline-block;padding:7px 12px;background:#e4eef0;border-radius:6px;font-weight:700}.muted{color:#49646f}footer{font-size:13px;margin:32px 0}</style>',
        '<h1>Synthetic evidence review</h1><p class="state">'+e(report['state'])+'</p>',
        '<p class="muted">Local research record. Source data and model statements are untrusted. Severity and support are separate.</p>',
        '<section><dl><dt>Run</dt><dd>'+e(run.name)+'</dd><dt>Model</dt><dd>'+e(manifest['config']['model'])+'</dd><dt>Configuration</dt><dd>'+e(manifest['config']['name'])+'</dd><dt>Partial result</dt><dd>'+e(report.get('partial'))+'</dd><dt>Scope</dt><dd>'+e(source['scope'])+'</dd><dt>Code commit</dt><dd>'+e(manifest['code']['commit'])+'</dd></dl></section>']
    if report.get('failure'):parts.append('<section><h2>Failure</h2><p>'+e(report['failure'])+'</p></section>')
    decisions={d['claim_id']:d for d in report.get('decisions',[])}
    parts.append('<h2>Claims and review decisions</h2>')
    if not report.get('claims'):parts.append('<p>No candidate claims were retained. This does not establish that the underlying case is benign.</p>')
    for claim in report.get('claims',[]):
        parts.append('<section><h3>'+e(claim['statement'])+'</h3>'+pre(decisions.get(claim['claim_id'],{})))
        parts.append('<p>Severity: <strong>'+e(claim['severity'])+'</strong></p><p>Unknowns: '+e(claim['unknowns'])+'</p>')
        for kind in ('supporting_evidence','contradicting_evidence'):
            parts.append('<h4>'+e(kind.replace('_',' ').title())+'</h4>')
            for ref in claim[kind]:
                parts.append('<p><a href="#'+e(ref['event_id'])+'">'+e(ref['event_id'])+'</a> · query '+e(ref['retrieved_by_query'])+'</p>'+pre(ref))
        parts.append('<details><summary>Relationship path and required checks</summary>'+pre({'path':claim['relationship_path'],'checks':claim['mandatory_checks']})+'</details></section>')
    parts.append('<h2>Exact synthetic source events</h2>')
    for event in snapshot.events:
        parts.append('<section id="'+e(event.event_id)+'"><h3>'+e(event.event_type)+' · '+e(event.occurred_at)+'</h3><p><code>'+e(event.event_id)+'</code></p><dl>')
        for key in ('actor','session','object_id','tcode','table','field','old_value','new_value','status'):
            parts.append('<dt>'+e(key)+'</dt><dd>'+e(getattr(event,key))+'</dd>')
        parts.append('</dl><details><summary>Raw source, immutable locator and hash</summary>'+pre({'raw_source':json.loads(event.raw_json),'source_locator':event.source_record_locator,'hash':event.raw_content_hash,'snapshot':event.source_snapshot_id})+'</details></section>')
    parts.append('<h2>Execution and validation</h2>'+pre({k:report.get(k) for k in ('counts','supervisor','structural','semantic')})+
        '<footer>Verified local hash chain before rendering. This is not external notarization. Analyst feedback has not been collected.</footer></html>')
    with Path(output).open('x') as f:f.write(''.join(parts))
    print(output)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('output');a=p.parse_args();render(a.run,a.output)
