"""Deterministic per-case relationships; time ordering never implies causation."""
from collections import defaultdict, deque
from typing import Literal

from .contracts import StrictModel, digest


class Node(StrictModel):
    node_id: str
    kind: str
    value: str
    source_events: tuple[str, ...]


class Edge(StrictModel):
    edge_id: str
    kind: str
    source: str
    target: str
    source_events: tuple[str, ...]
    status: Literal["VERIFIED", "HYPOTHESIS_ONLY"] = "VERIFIED"


class CaseGraph(StrictModel):
    snapshot: str
    version: str = "2.0.0"
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    def path(self, first_event, last_event):
        adjacency = defaultdict(list)
        for edge in self.edges:
            if edge.kind == "PRECEDES" and edge.status == "VERIFIED":
                adjacency[edge.source].append(edge)
        start, end = node_id(self.snapshot, "Event", first_event), node_id(self.snapshot, "Event", last_event)
        queue, seen = deque([(start, ())]), {start}
        while queue:
            node, path = queue.popleft()
            if node == end: return path
            for edge in adjacency[node]:
                if edge.target not in seen:
                    seen.add(edge.target)
                    queue.append((edge.target, path+(edge.edge_id,)))
        return ()

    def verified_path(self, path, first_event, last_event):
        if not path: return False
        lookup = {e.edge_id: e for e in self.edges}
        node = node_id(self.snapshot, "Event", first_event)
        for eid in path:
            e = lookup.get(eid)
            if e is None or e.status != "VERIFIED" or e.kind != "PRECEDES" or e.source != node:
                return False
            node = e.target
        return node == node_id(self.snapshot, "Event", last_event)


def node_id(snapshot, kind, value):
    return "node-" + digest([snapshot, kind, value])[:24]


def build_graph(snapshot, events=None):
    events = tuple(snapshot.events if events is None else events)
    nodes, edges, chains = {}, {}, defaultdict(list)
    def node(kind, value, evid):
        key = node_id(snapshot.id, kind, value)
        if key not in nodes: nodes[key] = [kind, value, set()]
        nodes[key][2].add(evid)
        return key
    def edge(kind, a, b, evids):
        eid = "edge-" + digest([snapshot.id, kind, a, b])[:24]
        edges[eid] = Edge(edge_id=eid, kind=kind, source=a, target=b, source_events=tuple(sorted(evids)))
    for event in sorted(events, key=lambda e: (e.occurred_at, e.event_id)):
        if snapshot.by_id.get(event.event_id) != event:
            raise ValueError("graph event outside pinned snapshot")
        eid = event.event_id
        event_node = node("Event", eid, eid)
        for kind, value, relation in [
            ("Actor", event.actor, "PERFORMED_BY"),
            ("AccessRequest", event.request, "BELONGS_TO"),
            ("Session", event.session, "OCCURRED_IN"),
            ("TransactionCode", event.tcode, "USES_TCODE"),
            ("Table", event.table, "TOUCHES_TABLE"),
            ("BusinessObject", event.object_id, "AFFECTS_OBJECT"),
            ("TimeWindow", event.occurred_at[:13], "OCCURRED_DURING"),
            ("PolicyRule", digest(event.approved_operations),
             "WITHIN_APPROVED_SCOPE" if event.tcode in event.approved_operations else "OUTSIDE_APPROVED_SCOPE"),
        ]:
            edge(relation, event_node, node(kind, value, eid), [eid])
        if event.field:
            edge("CHANGES_FIELD", event_node, node("FieldChange", eid+":"+event.field, eid), [eid])
        chains[(event.actor, event.session, event.object_id)].append(event)
    for chain in chains.values():
        for a, b in zip(chain, chain[1:]):
            x, y = node_id(snapshot.id, "Event", a.event_id), node_id(snapshot.id, "Event", b.event_id)
            edge("SAME_OBJECT_AS", x, y, [a.event_id, b.event_id])
            edge("SAME_SESSION_AS", x, y, [a.event_id, b.event_id])
            if a.occurred_at < b.occurred_at:
                edge("PRECEDES", x, y, [a.event_id, b.event_id])
    return CaseGraph(snapshot=snapshot.id, nodes=tuple(Node(node_id=k, kind=v[0], value=v[1],
        source_events=tuple(sorted(v[2]))) for k,v in sorted(nodes.items())),
        edges=tuple(edges[k] for k in sorted(edges)))
