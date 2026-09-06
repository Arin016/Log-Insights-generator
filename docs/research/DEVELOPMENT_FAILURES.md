# Development pilots retained — 2026-09-06

At commit a9579c3, development-only runs `dev-memory-1` (414 case-runs) and `dev-local-model-1` (4 case-runs) revealed interface defects. Their sealed artifacts remain unchanged under `artifacts/` and will be archived with final evidence. Neither run supports an effectiveness comparison.

- The new quoted pipe omitted raw_content_hash. The scripted adapter attempted to reconstruct a full source record from missing identity metadata and failed. Corrected by including the hash and adding full-investigation tests across representations.
- Local Llama 3.2 produced action=final together with a non-null query; all four runs exhausted the two-repair allowance. Cross-field grammar constraints now distinguish final and tool branches. Structured validation errors are preserved and returned for repair. Invalid outputs are never silently converted into valid claims.
- Original demo pipe formatting differs from the new quoted pipe. The original formatter is now executed as legacy_pipe, retaining its actual omission of actor/object/full date. Scripted investigation explicitly abstains when these business fields are unavailable. No efficacy claim against the original deployed product follows from this constrained emulation.
- No-graph previously still built an unused full graph. It now skips that construction. The coverage ablation now removes the final completeness gate as well as claim checklist obligations. Hard supervisor and scope boundaries remain active for every variant.
- Typed edges now use compact source-linked tuples; hybrid preserves full node/edge objects. Token totals are reported only for provider-returned usage, with usage coverage across attempted calls.

All changes were motivated by development evidence. Final test and challenge runs have not been inspected or used for tuning at this checkpoint.
