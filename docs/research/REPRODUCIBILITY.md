# Reproduction

Use Python 3.13 and the pinned dependency lock. All default commands use new synthetic data and deterministic adapters. They never read the original .env or original ignored outputs. Run commands from this repository root.

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
```

Start the dedicated service with either Docker Compose (`docker compose -f compose.research.yml up -d`) or the checksum-verifying native macOS launcher (`bash scripts/start_native_es.sh`). The native launcher runs in the foreground; stop it with Ctrl-C in that terminal. Docker shutdown is `docker compose -f compose.research.yml down`; omit `-v` to preserve synthetic data. Port 19200 is bound to loopback. The native experiment used Elasticsearch 8.13.4 and a 512 MB heap. Its dedicated data path is ignored .runtime/es-data.

```sh
.venv/bin/python scripts/research.py health
FF_ES_INTEGRATION=1 .venv/bin/python -m pytest tests/test_elasticsearch.py -q
.venv/bin/python scripts/reproduce.py artifacts/reproduction-NEW
```

The reproduction command requires a clean committed source tree, creates a new corpus, verifies/seeds its owned index, freezes the protocol, runs 19 configurations on test/challenge families and regenerates figures/tables. It refuses to overwrite its destination. `--memory` runs the same experiment without Elasticsearch. Same seed/version produces the same corpus hash. UUIDs, timings, provider outputs and run hashes may differ; no bit-identical live-model claim is made.

To inspect an existing sealed experiment or run:

```sh
.venv/bin/python scripts/analyze_experiment.py artifacts/final-scripted artifacts/analysis-NEW
.venv/bin/python scripts/render_case.py PATH_TO_RUN artifacts/review-NEW.html
```

Elasticsearch seeding is idempotent only after every document and ownership marker matches. Reset is explicit and destructive only for the named owned synthetic index: `scripts/research.py reset --index EXACT_INDEX --dataset-hash EXACT_FULL_HASH`. Unknown names, wildcards, aliases and ownership mismatch are refused. Do not delete original or unfamiliar indices.

The Claude adapter uses a private mode-600 key file at .runtime/anthropic_api_key or an explicitly chosen FF_CLAUDE_KEY_FILE path. The key is never a command-line argument or an experiment field. The approved pilot ledger is initialized once with 5,000,000 micro-USD; do not reset it, replace it or create another allowance under the same authorization. CLAUDE_PILOT.md defines paid scope. Frozen protocols and run manifests record model IDs, provider settings, prompt hashes and billing assumptions. Any broader paid evaluation requires new authorization.

All model calls pass through the same parent deadline. Provider compute may continue after client cancellation; unresolved paid reservations are retained. HTTP rejections, refusals and incomplete results remain visible. The original demo-style baseline is an emulation inside this modern supervisor using the original formatter, not a replay of the original proprietary product or external model configuration.

GitHub CI configuration is provided for deterministic and Elasticsearch tests. It has not been pushed or executed on GitHub; local test logs are the evidence available here. Exact frozen commits and archive checksums live in the experiment registry and evidence manifest. No push, deployment or publication is part of reproduction.
