# Failure analysis catalog

This catalog interprets only sealed synthetic runs. Exact per-case entries and paths are in generated `failure-catalog.json` files. Labels are generator-authored, and model failures are development-only observations.

## Frozen scripted study

The complete V2 scripted configuration matched the expected terminal disposition on 46/46 held-out variants. It surfaced 10/28 underlying expected claims with 0 unsupported surfaced claims. The 18 missed underlying patterns were intentional terminal behavior: 14 prompt-injection variants were blocked as unsafe input, two tool-error cases failed and two tool-timeout cases expired. Reporting only claim recall would therefore hide the safety objective; reporting only disposition accuracy would hide unsurfaced patterns.

The deterministic rule and naive single-pass configurations surfaced 23 matching and 12 unsupported claims, and missed five expected claims. They matched 19/46 terminal labels. Their lack of contradiction, coverage and attack policy explains the false positives; they are protocol controls, not learned-model baselines.

Original legacy pipe emulations produced no claims because the original formatter omits actor, business object and full date fields required by this V2 hypothesis. Scoped single-pass and demo-style ReAct each matched 20/46 dispositions, mostly by abstaining. This measures representation incompatibility inside the research harness, not the efficacy of the historical product.

Removing contradiction search surfaced 6 unsupported claims and reduced terminal agreement to 42/46. Removing injection detection allowed 14 attack cases to pass the unsafe-input gate; it surfaced 24 matching underlying patterns but matched only 32/46 policy labels. Removing coverage produced 44/46 agreement because incomplete cases no longer required review. A one-tool budget and two-row context each produced no surfaced claims and only 20/46 and 32/46 terminal agreement. Initial-scope-only and legacy-pipe V2 each matched 36/46 while missing all 28 expected underlying claims. These differences demonstrate that the synthetic fixtures exercise the intended mechanisms; they are not population effect sizes.

No-graph and no-selective-triage matched the complete scripted terminal outcomes. This does not show those components are useless: the scripted investigator uses deterministic row matching, semantic uncertainty is low in its fake verifier, and claim construction can proceed without graph paths when the graph obligation is disabled. A live or independently labeled study is needed to measure those factors.

## Development interface failures

The first scripted comparison failed for the new pipe representation because its rows omitted a content hash used by the scripted adapter. The first local Llama pilot repeatedly mixed a final action with a non-null tool query. These were interface defects and the sealed runs are excluded from effectiveness comparisons. Corrections and reasons are recorded in `DEVELOPMENT_FAILURES.md`.

Later Llama pilots produced valid structured outputs but abstained on positive development cases or issued object queries using table/transaction strings. The run was stopped when the user requested Claude. It remains an incomplete model study.

## Claude development pilot

Haiku's complete V2 generated correct candidates for both positive variants, but one received PARTIALLY_SUPPORTED from Sonnet and one SUPPORTED with high uncertainty. The policy routed both to review. The authorized case was rejected because the change was inside approved scope, the no-evidence case abstained, and the conflict case attached contradiction evidence and abstained. The missing-source case repeated model calls until the 12-call limit rather than stopping on missing data. This is a termination/prompt failure; the hard budget prevented an unbounded loop.

The Claude demo-style ReAct configurations also looped until call exhaustion in most cases. One Sonnet call crossed the 120-second parent deadline. Its provider usage was unavailable, so the shared ledger retained the full $2.020480 reservation. Subsequent Sonnet V2 calls were denied before network access because another worst-case reservation would have exceeded the approved $5 ceiling. These are correctly recorded as budget-limited missing results.

Naive live baselines recovered the two positive cases but surfaced unsupported authorized and/or conflicting cases. Sonnet scoped single-pass also created an unsupported positive-case claim under the generator's exact matching rule. Schema validity and existing event citations did not establish domain correctness.

## Remaining investigation gaps

The experiment has no independent domain labels, adaptive attackers, production distribution, analyst outcome study, alternate live-model repetitions, calibrated score or completed held-out live-model tuple. Test and challenge each contain one generated family, so the bootstrap intervals are descriptive and often degenerate. The next empirical protocol must increase independent families, blind adjudicators to configuration, pre-register attack goals and termination criteria, and freeze a spending method that uses provider token counting while retaining a hard total ceiling.
