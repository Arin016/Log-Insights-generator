"""Minimal Flask frontend for FF Insights findings viewer.

Run: python frontend.py
Open: http://localhost:5001
"""

from __future__ import annotations

import json
import glob
from pathlib import Path
from flask import Flask, render_template_string

from config import DATA_DIR
from core.pass2.event_store import ElasticsearchEventStore

app = Flask(__name__)


def _fetch_evidence_events(rak_id: str, event_ids: list[str]) -> list[dict]:
    """Fetch actual log events from ES for the given event_ids."""
    store = ElasticsearchEventStore(rak_id=rak_id)
    results = []
    body = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"request_access_key": rak_id}},
                    {"terms": {"event_id": event_ids}},
                ]
            }
        },
        "size": len(event_ids),
        "sort": [{"timestamp_utc": "asc"}],
    }
    try:
        res = store.client.search(index=store.index, body=body)
        for hit in res["hits"]["hits"]:
            src = hit["_source"]
            results.append({
                "event_id": src.get("event_id"),
                "timestamp": src.get("timestamp_utc", "")[:19],
                "tcode": src.get("operation") or "",
                "table": src.get("entity_accessed") or "",
                "action": src.get("action_type") or "",
                "field": (src.get("attributes") or {}).get("field") or "",
                "old_val": (src.get("attributes") or {}).get("old_val") or "",
                "new_val": (src.get("attributes") or {}).get("new_val") or "",
                "detail": (src.get("attributes") or {}).get("raw_details") or "",
                "program": (src.get("attributes") or {}).get("program_name") or "",
                "terminal": (src.get("attributes") or {}).get("terminal") or "",
                "log_type": (src.get("attributes") or {}).get("log_type") or "",
            })
    except Exception:
        pass
    return results

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FF Insights — {{ rak_id }}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1419; color: #e7e9ea; line-height: 1.5; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
header { background: #1a1f2e; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid #2d3748; }
header h1 { font-size: 1.5rem; color: #fff; margin-bottom: 8px; }
.meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }
.meta-item { background: #232b3b; border-radius: 8px; padding: 12px; }
.meta-item label { font-size: 0.7rem; text-transform: uppercase; color: #8899a6; letter-spacing: 0.5px; }
.meta-item .value { font-size: 1.1rem; font-weight: 600; color: #fff; margin-top: 2px; }
.tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.tab { padding: 10px 20px; border-radius: 8px; cursor: pointer; background: #1a1f2e; border: 1px solid #2d3748; color: #8899a6; font-weight: 500; transition: all 0.2s; }
.tab:hover { border-color: #4a5568; color: #fff; }
.tab.active { background: #2563eb; border-color: #2563eb; color: #fff; }
.tab.manual { background: #92400e; border-color: #92400e; color: #fff; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.finding { background: #1a1f2e; border-radius: 12px; padding: 20px; margin-bottom: 16px; border-left: 4px solid #4a5568; }
.finding.CRITICAL { border-left-color: #dc2626; }
.finding.HIGH { border-left-color: #f59e0b; }
.finding.MEDIUM { border-left-color: #3b82f6; }
.finding.LOW { border-left-color: #6b7280; }
.finding-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.badge { padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
.badge.CRITICAL { background: #dc2626; color: #fff; }
.badge.HIGH { background: #f59e0b; color: #000; }
.badge.MEDIUM { background: #3b82f6; color: #fff; }
.badge.LOW { background: #6b7280; color: #fff; }
.confidence { font-size: 0.85rem; color: #8899a6; }
.finding-title { font-size: 1rem; font-weight: 600; color: #fff; }
.finding-reasoning { color: #b0b8c4; font-size: 0.9rem; margin: 12px 0; }
.evidence-toggle { cursor: pointer; color: #60a5fa; font-size: 0.85rem; margin-top: 8px; user-select: none; }
.evidence-toggle:hover { text-decoration: underline; }
.evidence-list { display: none; margin-top: 12px; background: #111827; border-radius: 8px; padding: 12px; max-height: 300px; overflow-y: auto; }
.evidence-list.open { display: block; }
.evidence-list code { font-size: 0.8rem; color: #a5f3fc; }
.log-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.log-table th { text-align: left; color: #6b7280; padding: 4px 8px; border-bottom: 1px solid #2d3748; }
.log-table td { padding: 4px 8px; border-bottom: 1px solid #1f2937; color: #d1d5db; white-space: nowrap; }
.log-table tr:hover td { background: #1f2937; }
.detail-cell { white-space: normal; max-width: 200px; color: #fbbf24; font-size: 0.7rem; }
.finding-meta { display: flex; gap: 16px; margin-top: 12px; font-size: 0.8rem; color: #6b7280; }
.mr-reason { background: #78350f; color: #fbbf24; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-left: 8px; }
.pass2-badge { background: #1e3a5f; color: #60a5fa; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; }
.section-count { background: #232b3b; color: #8899a6; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; margin-left: 6px; }
</style>
</head>
<body>
<div class="container">
<header>
  <h1>🔍 FF Insights — RAK {{ rak_id }}</h1>
  <div class="meta-grid">
    <div class="meta-item"><label>Actor</label><div class="value">{{ metadata.actor }}</div></div>
    <div class="meta-item"><label>Sessions</label><div class="value">{{ metadata.session_ids|length }}</div></div>
    <div class="meta-item"><label>Events</label><div class="value">{{ metadata.total_event_count }}</div></div>
    <div class="meta-item"><label>Scope</label><div class="value">{{ metadata.requested_operations|join(', ') }}</div></div>
    <div class="meta-item"><label>Time Window</label><div class="value">{{ metadata.rak_start[:10] }}</div></div>
    <div class="meta-item"><label>Pipeline</label><div class="value">{{ report_meta.pipeline_latency_seconds }}s</div></div>
    <div class="meta-item"><label>LLM Calls</label><div class="value">{{ report_meta.pass1_invocations + report_meta.pass2_invocations }}</div></div>
    <div class="meta-item"><label>Model</label><div class="value">{{ report_meta.model_id }}</div></div>
  </div>
</header>

<div class="tabs">
  {% for uc in use_cases %}
  <div class="tab {% if loop.first %}active{% endif %}" onclick="showTab('{{ uc }}')">
    {{ uc.replace('_', ' ').title() }}<span class="section-count">{{ findings_by_uc[uc]|length }}</span>
  </div>
  {% endfor %}
  {% if manual_review %}
  <div class="tab" onclick="showTab('manual_review')">
    Manual Review<span class="section-count" style="background:#78350f;color:#fbbf24">{{ manual_review|length }}</span>
  </div>
  {% endif %}
</div>

{% for uc in use_cases %}
<div class="tab-content {% if loop.first %}active{% endif %}" id="tab-{{ uc }}">
  {% for f in findings_by_uc[uc] %}
  <div class="finding {{ f.severity }}">
    <div class="finding-header">
      <span class="badge {{ f.severity }}">{{ f.severity }}</span>
      <span class="confidence">{{ "%.0f"|format(f.confidence * 100) }}%</span>

    </div>
    <div class="finding-title">{{ f.title }}</div>
    <div class="finding-reasoning">{{ f.reasoning }}</div>
    <div class="evidence-toggle" onclick="toggleEvidence(this)">▶ Evidence ({{ f.evidence_event_ids|length }} events)</div>
    <div class="evidence-list">
      <table class="log-table">
        <tr><th>ID</th><th>Time</th><th>Tcode</th><th>Table</th><th>Action</th><th>Field</th><th>Old→New</th><th>Detail</th></tr>
        {% for e in f.evidence_logs %}
        <tr>
          <td>{{ e.event_id }}</td>
          <td>{{ e.timestamp[11:] }}</td>
          <td>{{ e.tcode }}</td>
          <td>{{ e.table }}</td>
          <td>{{ e.action }}</td>
          <td>{{ e.field }}</td>
          <td>{{ e.old_val[:20] }}{% if e.old_val %}→{% endif %}{{ e.new_val[:20] }}</td>
          <td class="detail-cell">{{ e.detail[:80] }}</td>
        </tr>
        {% endfor %}
        {% if f.evidence_event_ids|length > 20 %}<tr><td colspan="8" style="color:#6b7280">... and {{ f.evidence_event_ids|length - 20 }} more events</td></tr>{% endif %}
      </table>
    </div>
    <div class="finding-meta">
      <span>Sessions: {{ f.affected_session_ids|join(', ') }}</span>
    </div>
  </div>
  {% endfor %}
</div>
{% endfor %}

{% if manual_review %}
<div class="tab-content" id="tab-manual_review">
  {% for m in manual_review %}
  <div class="finding MEDIUM">
    <div class="finding-header">
      <span class="badge {{ m.pass1_finding.severity }}">{{ m.pass1_finding.severity }}</span>
      <span class="confidence">{{ "%.0f"|format(m.pass1_finding.confidence * 100) }}%</span>
      <span class="mr-reason">{{ m.reason }}</span>
    </div>
    <div class="finding-title">{{ m.pass1_finding.title }}</div>
    <div class="finding-reasoning">{{ m.pass1_finding.reasoning }}</div>
    <div class="evidence-toggle" onclick="toggleEvidence(this)">▶ Evidence ({{ m.pass1_finding.evidence_event_ids|length }} events)</div>
    <div class="evidence-list">
      <table class="log-table">
        <tr><th>ID</th><th>Time</th><th>Tcode</th><th>Table</th><th>Action</th><th>Field</th><th>Old→New</th><th>Detail</th></tr>
        {% for e in m.evidence_logs %}
        <tr>
          <td>{{ e.event_id }}</td>
          <td>{{ e.timestamp[11:] }}</td>
          <td>{{ e.tcode }}</td>
          <td>{{ e.table }}</td>
          <td>{{ e.action }}</td>
          <td>{{ e.field }}</td>
          <td>{{ e.old_val[:20] }}{% if e.old_val %}→{% endif %}{{ e.new_val[:20] }}</td>
          <td class="detail-cell">{{ e.detail[:80] }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}

</div>
<script>
function showTab(id) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
}
function toggleEvidence(el) {
  const list = el.nextElementSibling;
  list.classList.toggle('open');
  el.textContent = list.classList.contains('open')
    ? '▼ Evidence (' + list.textContent.split(',').length + ' events)'
    : '▶ Evidence (' + list.textContent.split(',').length + ' events)';
}
</script>
</body>
</html>
"""


@app.route("/")
@app.route("/<rak_id>")
def view_report(rak_id: str = "RQ1234"):
    report_path = DATA_DIR / "reports" / f"{rak_id}.json"
    if not report_path.exists():
        return f"<h1>No report found for RAK {rak_id}</h1>", 404

    with open(report_path) as f:
        report = json.load(f)

    # Load manual review
    mr_files = sorted(glob.glob(str(DATA_DIR / "manual_review" / f"{rak_id}__*.json")))
    manual_review = []
    for mf in mr_files:
        with open(mf) as f:
            manual_review.append(json.load(f))

    # Structure findings by use case
    findings_by_uc = report.get("findings_by_use_case", {})

    # Convert finding dicts to objects with attribute access
    class DotDict(dict):
        __getattr__ = dict.__getitem__

    structured = {}
    for uc, fs in findings_by_uc.items():
        enriched = []
        for f in fs:
            d = DotDict(f)
            d["evidence_logs"] = _fetch_evidence_events(rak_id, f.get("evidence_event_ids", [])[:20])
            enriched.append(d)
        structured[uc] = enriched

    mr_structured = []
    for m in manual_review:
        mr_structured.append({
            "reason": m["reason"],
            "pass1_finding": DotDict(m["pass1_finding"]),
            "pass2_finding": DotDict(m["pass2_finding"]) if m.get("pass2_finding") else None,
            "evidence_logs": _fetch_evidence_events(rak_id, m["pass1_finding"].get("evidence_event_ids", [])[:20]),
        })

    return render_template_string(
        HTML,
        rak_id=rak_id,
        metadata=DotDict(report["metadata"]),
        report_meta=DotDict(report["report_metadata"]),
        use_cases=list(structured.keys()),
        findings_by_uc=structured,
        manual_review=mr_structured,
    )


if __name__ == "__main__":
    print("FF Insights Frontend: http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
