import time

import pytest

from core.v2.gateway import Gateway, Capability, MemoryBackend
from tests.test_provenance import row, snapshot


def gateway(s=None, **overrides):
    s = s or snapshot()
    args = dict(scope=s.scope, snapshot=s.id, expires_monotonic=time.monotonic()+10, run_id="test")
    args.update(overrides)
    return Gateway(s, Capability(**args))


def test_pagination_and_batch_metadata():
    s = snapshot(*(row(locator=f"row-{i}") for i in range(9)))
    g = gateway(s, row_limit=2)
    query = {"template": "seed_events"}
    found = []
    while True:
        r = g.batch([query])["results"][0]
        found.extend(e["event_id"] for e in r["rows"])
        assert r["total_known_count"] == 9
        assert {"query_id", "executed_at", "duration_ms", "source_snapshot"} <= r.keys()
        if not r["truncated"]: break
        query["cursor"] = r["next_cursor"]
    assert len(found) == len(set(found)) == 9


@pytest.mark.parametrize("raw", [
    {"template":"seed_events", "tenant":"other"},
    {"template":"seed_events", "request":"other"},
    {"template":"delete_index"}, {"template":"seed_events", "dsl":{}},
    {"template":"seed_events", "cursor":"invented"},
])
def test_scope_and_tool_denial(raw):
    g = gateway()
    with pytest.raises((ValueError, PermissionError)): g.query(raw)
    assert "error" in g.trace[-1]


def test_cross_run_cursor_and_byte_no_progress():
    s = snapshot(row(), row(locator="second"))
    g = gateway(s, row_limit=1)
    r = g.query({"template":"seed_events"})
    with pytest.raises(PermissionError):
        gateway(s).query({"template":"seed_events", "cursor":r["next_cursor"]})
    b = gateway(s, byte_limit=1).query({"template":"seed_events"})
    assert b["truncated"] and b["next_cursor"] is None and b["returned_count"] == 0


def test_backend_cross_scope_and_expiry():
    s = snapshot()
    foreign = snapshot(row(new_value="SYNTH-C"))
    class BrokenBackend:
        def fetch(self, *_): return list(foreign.events), 1
    g = gateway(s)
    g.backend = BrokenBackend()
    with pytest.raises(PermissionError): g.query({"template":"seed_events"})
    with pytest.raises(TimeoutError): gateway(expires_monotonic=0).query({"template":"seed_events"})


def test_legacy_batch_preserves_fields():
    from applications.sap.tools.sap_tools import _batch_query_tcodes, _batch_query_tables
    class Store:
        def by_tcode(self, _): return {"total_count":3, "events":[], "truncated":True, "next_cursor":"c"}
        by_table = by_tcode
    for fn in (_batch_query_tcodes, _batch_query_tables):
        assert fn(Store(), ["x"])["results"]["x"]["truncated"] is True
