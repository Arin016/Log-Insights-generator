"""Seed Elasticsearch with a SAP RAK log file.

Usage:
  python seed_elasticsearch.py --log-file path/to/your_rak_logs.txt

  # Or with extra options
  python seed_elasticsearch.py \
      --log-file path/to/your_rak_logs.txt \
      --recreate-index \
      --batch-size 500

The script:
  1. Parses the pipe-delimited SAP log file → generic LogEvents
  2. (Optionally) drops + recreates the index with proper mappings
  3. Bulk-indexes all events into Elasticsearch
  4. Verifies the count

Once seeded, run the pipeline with:
  python run_local.py --rak-id <rak_id_from_logs>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from config import (
    ELASTICSEARCH_INDEX,
    ELASTICSEARCH_PASSWORD,
    ELASTICSEARCH_URL,
    ELASTICSEARCH_USERNAME,
)
from core.contracts import LogEvent
from core.logging_setup import log
from applications.sap.parser import parse_file


# Index mapping. We use keyword sub-fields on string fields that need exact
# match in queries (term/wildcard) — this avoids the "all lowercase, tokenized"
# default behavior that breaks our tools.
INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "event_id": {"type": "keyword"},
            "request_access_key": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "timestamp_utc": {"type": "date"},
            "actor": {"type": "keyword"},
            "action_type": {"type": "keyword"},
            "entity_accessed": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "entity_classification": {"type": "keyword"},
            "operation": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "operation_category": {"type": "keyword"},
            "requested_operation": {"type": "keyword"},
            "deviation_flagged": {"type": "boolean"},
            "application": {"type": "keyword"},
            "attributes": {
                "type": "object",
                "properties": {
                    "log_type": {"type": "keyword"},
                    "audit_class": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "program_name": {"type": "keyword"},
                    "host_name": {"type": "keyword"},
                    "terminal": {"type": "keyword"},
                    "client": {"type": "keyword"},
                    "time_zone": {"type": "keyword"},
                    "change_indicator": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "table_key": {"type": "keyword"},
                    "field": {"type": "keyword"},
                    "old_val": {"type": "text"},
                    "new_val": {"type": "text"},
                    "object": {"type": "keyword"},
                    "doc": {"type": "keyword"},
                    "raw_details": {"type": "text"},
                },
            },
        }
    },
}


def _client() -> Elasticsearch:
    if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
        return Elasticsearch(
            ELASTICSEARCH_URL,
            basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD),
        )
    return Elasticsearch(ELASTICSEARCH_URL)


def ensure_index(client: Elasticsearch, recreate: bool) -> None:
    exists = client.indices.exists(index=ELASTICSEARCH_INDEX)
    if exists and recreate:
        log.info("seed.dropping_index", index=ELASTICSEARCH_INDEX)
        client.indices.delete(index=ELASTICSEARCH_INDEX)
        exists = False
    if not exists:
        log.info("seed.creating_index", index=ELASTICSEARCH_INDEX)
        client.indices.create(index=ELASTICSEARCH_INDEX, body=INDEX_MAPPING)


def event_to_doc(event: LogEvent) -> dict:
    """Pydantic → JSON-safe dict."""
    return event.model_dump(mode="json")


def actions_iter(events: list[LogEvent]):
    for ev in events:
        yield {
            "_op_type": "index",
            "_index": ELASTICSEARCH_INDEX,
            "_id": f"{ev.request_access_key}__{ev.event_id}",
            "_source": event_to_doc(ev),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Elasticsearch with a SAP RAK log file.")
    parser.add_argument("--log-file", required=True, help="Path to pipe-delimited SAP log file.")
    parser.add_argument(
        "--recreate-index",
        action="store_true",
        help="Drop + recreate the index before indexing.",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    log_file = Path(args.log_file)
    if not log_file.exists():
        log.error("seed.file_not_found", path=str(log_file))
        return 2

    log.info("seed.parsing", file=str(log_file))
    events = parse_file(log_file)
    if not events:
        log.error("seed.no_events_parsed")
        return 2
    log.info("seed.parsed", event_count=len(events))

    rak_ids = sorted({e.request_access_key for e in events})
    log.info("seed.rak_ids_seen", rak_ids=rak_ids)

    client = _client()
    if not client.ping():
        log.error("seed.cannot_reach_elasticsearch", url=ELASTICSEARCH_URL)
        return 3

    ensure_index(client, recreate=args.recreate_index)

    log.info("seed.indexing", batch_size=args.batch_size)
    success_count, errors = bulk(
        client,
        actions_iter(events),
        chunk_size=args.batch_size,
        request_timeout=60,
    )
    if errors:
        log.warning("seed.bulk_had_errors", errors=str(errors)[:500])
    log.info("seed.indexed", success=success_count)

    # Refresh so subsequent searches find the docs immediately
    client.indices.refresh(index=ELASTICSEARCH_INDEX)

    # Verify
    res = client.count(index=ELASTICSEARCH_INDEX)
    log.info("seed.index_count", count=res["count"])

    print(f"\nSeeded {success_count} events for RAKs: {rak_ids}")
    print(f"Index: {ELASTICSEARCH_INDEX} at {ELASTICSEARCH_URL}")
    print(f"Total docs in index: {res['count']}")
    print(f"\nRun the pipeline with:")
    for r in rak_ids:
        print(f"  python run_local.py --rak-id {r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
