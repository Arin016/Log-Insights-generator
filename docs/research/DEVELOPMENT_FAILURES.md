# Development pilots retained — 2026-09-06

At commit a9579c3, development-only runs `dev-memory-1` (414 case-runs) and `dev-local-model-1` (4 case-runs) revealed interface defects. Their sealed artifacts remain unchanged under `artifacts/` and will be archived with final evidence. Neither run supports an effectiveness comparison.

- The new quoted pipe omitted raw_content_hash. The scripted adapter attempted to reconstruct a full source record from missing identity metadata and failed. Corrected by including the hash and adding full-investigation tests across representations.
- Local Llama 3.2 produced action=final together with a non-null query; all four runs exhausted the two-repair allowance. Cross-field grammar constraints now distinguish final and tool branches. Structured validation errors are preserved and returned for repair. Invalid outputs are never silently converted into valid claims.
- Original demo pipe formatting differs from the new quoted pipe. The original formatter is now executed as legacy_pipe, retaining its actual omission of actor/object/full date. Scripted investigation explicitly abstains when these business fields are unavailable. No efficacy claim against the original deployed product follows from this constrained emulation.
- No-graph previously still built an unused full graph. It now skips that construction. The coverage ablation now removes the final completeness gate as well as claim checklist obligations. Hard supervisor and scope boundaries remain active for every variant.
- Typed edges now use compact source-linked tuples; hybrid preserves full node/edge objects. Token totals are reported only for provider-returned usage, with usage coverage across attempted calls.

All changes were motivated by development evidence. Final test and challenge runs have not been inspected or used for tuning at this checkpoint.

The second live pilot (05b7872; six runs) produced valid JSON but no surfaced claims. It also attempted object lookups using table/transaction text instead of the observed object ID. The third pilot (9570975; six runs) removed duplicated schemas and JSON-string nesting from provider input, pinned a 32,768-token context, and enforced a conservative byte-based prompt/context limit. It still abstained in all six positive-case runs. This is a model/harness failure retained for reporting, not a reason to tune on held-out data.

The final protocol uses a fresh seed (20260906) and three independently generated sibling families: one development, one test and one challenge family, with 23 variants each. All 19 configurations run on both held-out families for each of the scripted and installed local-model tuples. This is deliberately a small local feasibility study; two held-out families cannot support a publishable effectiveness or generalization claim. Test/challenge summaries are reported separately as well as pooled. No policy or prompt changes will follow inspection of final outcomes.
