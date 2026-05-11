# Implementation Plan — v1 (Kiro + Elasticsearch)

## What's already in this skeleton

- ✅ Project structure (`core/` engine + `applications/sap/` config)
- ✅ Pydantic contracts (LogEvent, Finding, RAK, PipelineState)
- ✅ SAP parser (pipe-delimited → generic LogEvents) with CHANGE LOG JSON parsing
- ✅ Lean YAML catalogs (tcode + table) with custom Z_*/Y_* pattern matching
- ✅ Use case YAMLs (data_exfiltration + financial_fraud)
- ✅ Generic scope filter engine
- ✅ Pipe-delimited formatter for LLM input
- ✅ **Kiro CLI client** (subprocess wrapper with ANSI strip + JSON extraction)
- ✅ Pass 1 analyzer runner (one Kiro call per use case, prompt-instructed JSON)
- ✅ Pass 1 prompts (data_exfiltration_v1, financial_fraud_v1)
- ✅ Evidence verifier + retry handler (hallucination kill-switch)
- ✅ Confidence gate (bundled per analyzer)
- ✅ Outcome gate (PASS / MANUAL_REVIEW / FALLBACK rules)
- ✅ **Pass 2 ReAct runner** (hand-rolled JSON-protocol loop for Kiro)
- ✅ Pass 2 prompt template
- ✅ SAP Pass 2 tools (7 tools backed by ElasticsearchEventStore)
- ✅ Tool registry (generic interface)
- ✅ **Elasticsearch event store** (replaces InMemoryEventStore)
- ✅ Pipeline orchestrator
- ✅ Local file persistence
- ✅ **`docker-compose.yml`** for local Elasticsearch
- ✅ **`seed_elasticsearch.py`** to load RAK logs from your file
- ✅ `run_local.py --rak-id <id>` entry point

## Setup checklist (Day 1)

```bash
# 1. Start Elasticsearch
docker compose up -d

# 2. Wait ~30s for ES to be ready
curl http://localhost:9200

# 3. Install Python deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 4. Verify Kiro is on your PATH
which kiro-cli
kiro-cli chat --model claude-opus-4.6 --no-interactive --trust-all-tools "Output exactly: {\"hello\": \"world\"}"

# 5. Seed your RAK logs (replace path with your actual log file)
python seed_elasticsearch.py --log-file /path/to/your_rak.txt --recreate-index

# 6. Run the pipeline
python run_local.py --rak-id <rak_id_printed_by_seed_step>
```

## Day 2-7 work plan

| Day | Task |
|-----|------|
| 2   | First real run; iterate Pass 1 prompts until findings are correct |
| 3   | Get 2-3 more RAKs into ES (seed script handles each); compare results |
| 4   | Build minimal `eval/run_eval.py` that runs all RAKs and compares to expected output |
| 5   | Iterate confidence calibration — are the right things uncertain vs confident? |
| 6   | Iterate Pass 2 prompt and tool catalog — does the agent investigate efficiently? |
| 7   | Demo to mentor / DoE |

## Things to know about the Kiro path

### JSON parsing is the new failure surface

Without Bedrock's forced tool-use, the model sometimes returns prose around its
JSON. The kiro_client extractor handles:
- ANSI color escape codes
- Markdown ```json fences
- Preamble/postamble prose around `{...}`

If Pass 1 reports parse failures in `logs/pipeline.log`, look at the raw
output in `data/llm_audit/<rak_id>/<call_id>.json` — that's the ground truth.

### Pass 2 is more verbose than Bedrock-native

Each iteration is a full subprocess call with the entire conversation history
re-sent. Slower and more tokens, but completely deterministic — every iteration
has its own audit log entry.

### Evidence verification matters more

Hallucinated event_ids are the same risk as before, but JSON-parse failures
are a NEW risk. Both are bounded by the retry handler. After max retries,
that finding gets dropped (logged) rather than emitted with bad data.

## Files I deferred

- Real eval suite — Day 4-5 work
- More fixture RAKs — you provide these via seed script
- Manual review dashboard — files land in `data/manual_review/` for now;
  basic dashboard later

## What to do when something breaks

| Symptom | Where to look |
|---------|---------------|
| ES connection error | Is `docker compose ps` showing ES healthy? curl `http://localhost:9200` |
| Kiro subprocess error | `which kiro-cli`, run a manual test invocation |
| JSON parse failures | `data/llm_audit/<rak_id>/<latest>.json` shows raw model output |
| Empty Pass 1 findings | Check scope filter is producing events: look at `pipeline.log` for `scoping.complete` line |
| Pass 2 not firing | Confidence threshold too low? Check `data/findings/<rak_id>.json` for confidence values |
