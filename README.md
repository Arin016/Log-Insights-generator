# Log Insights Generator

AI-powered threat detection engine for SAP Firefighter (emergency access) audit logs. Uses stateful LLM agents to detect insider threats, fraud patterns, and policy violations.

## What It Does

Analyzes SAP Firefighter sessions to detect:
- **Vendor Master Manipulation** — fictitious vendors, bank detail fraud, payment redirection
- **Purchase Order Manipulation** — unauthorized PO changes, price manipulation  
- **Sales Order Manipulation** — revenue fraud, unauthorized discounts
- **Financial Fraud** — journal entry manipulation, account tampering
- **Data Exfiltration** — bulk data access, sensitive table reads
- **Logistics Fraud** — goods movement manipulation, inventory fraud

## Architecture

```
[SAP Logs in Elasticsearch]
        ↓
[Scope Filter] ← YAML use-case configs
        ↓
[Parallel Stateful ReAct Sessions]
  • LLM receives scoped events + tool catalog
  • LLM autonomously queries ES to verify hypotheses
  • Bounded: max 7 iterations, max 4 calls/tool, 120s timeout
        ↓
[Evidence Verification] — drops hallucinated event_ids
        ↓
[Confidence Gate] — ≥0.70 → emit, <0.70 → manual review
        ↓
[Persist: findings, audit logs, reports]
```

## Key Features

- **Stateful AI Agent**: Single conversation thread per use case, tools available upfront
- **Bounded Autonomy**: Hard caps on iterations, tool calls, and wall-clock time
- **Zero Hallucination Tolerance**: Every cited event_id verified against source data
- **YAML-Driven Extensibility**: Add new use cases with 1 YAML + 1 prompt file, zero code changes
- **Full Audit Trail**: Every LLM turn and tool call logged for compliance

## Setup

```bash
# 1. Start Elasticsearch
docker compose up -d

# 2. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 3. Seed logs
python seed_elasticsearch.py --log-file /path/to/rak_logs.txt --recreate-index

# 4. Run analysis
python run_local.py --rak-id <RAK_ID>
```

## Project Structure

```
├── core/
│   ├── orchestrator/pipeline.py    # Main 7-step pipeline
│   ├── react/react_runner.py       # Stateful ReAct loop
│   ├── analyzers/acp_client.py     # Kiro ACP session client
│   ├── scoping/filter_engine.py    # YAML-driven event filtering
│   ├── verification/               # Evidence verification
│   └── pass2/event_store.py        # Elasticsearch queries
├── applications/sap/
│   ├── use_cases/                  # YAML scope configs
│   ├── prompts/                    # LLM prompt templates
│   ├── tools/sap_tools.py          # 9 read-only ES query tools
│   └── catalogs.py                 # T-code & table catalogs
├── data/                           # Output: findings, reports, audit logs
└── run_local.py                    # Entry point
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `KIRO_MODEL` | claude-opus-4.6 | LLM model |
| `REACT_MAX_ITERATIONS` | 7 | Max investigation rounds |
| `REACT_MAX_PER_TOOL` | 4 | Max calls per tool |
| `REACT_WALL_CLOCK_SECONDS` | 120 | Timeout per use case |
| `CONFIDENCE_THRESHOLD` | 0.70 | Min confidence to emit |

## Sample Output

```
[HIGH conf 0.85] Vendor Bank Detail Manipulation Prior to Payment Run

Sessions: FF_SESSION_001, FF_SESSION_002
Evidence: evt_00142, evt_00156, evt_00189, evt_00201

Reasoning: Actor JSMITH modified vendor 100234's bank details (LFBK table) 
at 14:32 UTC, changing BANKN from ***4521 to ***7890. Within 23 minutes, 
invoice FB60 posted for $47,500 against this vendor, followed by F110 
payment run at 15:18 UTC.
```

## Tech Stack

- Python 3.10+
- Elasticsearch (log storage & queries)
- Claude LLM via Kiro CLI (stateful ACP sessions)
- YAML (use-case configuration)
