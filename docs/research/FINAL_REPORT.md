# FF Insights V2 Implementation and Evaluation Report

Prepared for Arin Mallanna Tumbagi by Codex. Final technical synthesis dated 8 September 2026. Experiments were recorded on 5–6 September; implementation validation and evidence registration were completed through 7 September. Local review only; public disclosure remains unapproved.

## 1 Findings and decision

FF Insights V2 now provides a working local research harness for one synthetic privileged-access investigation: a vendor bank-field change outside explicitly approved operations, followed by a completed payment for the same actor, session and business object within one hour. The implementation connects immutable source records, scoped retrieval, relationship checks, atomic claims, contradiction searches, semantic review and externally bounded execution. It also preserves the records needed to explain how an investigation reached its outcome. [E1, E2]

The engineering evidence is substantial within that scope. The final recorded default test run passed 106 tests with one opt-in integration test skipped. The separately enabled Elasticsearch suite passed all six tests. A frozen scripted experiment evaluated 19 configurations on 46 held-out synthetic variants, producing 874 case-runs. Complete V2 matched all 46 generator-authored terminal labels, including required abstentions, reviews, unsafe-input rejections and injected failures. It surfaced 10 generator-matching claims and no unsupported surfaced claims. Another 18 labeled underlying patterns were not surfaced because their cases required unsafe-input rejection, failure or expiry. [E3, E4]

These results establish software behavior on constructed cases. They do not establish live-model detection accuracy. The 46 variants belong to only two generated families, and both the cases and their expected answers come from the same generator. The scripted investigator and semantic verifier are deterministic test doubles. The apparent perfect terminal result is therefore evidence that the mechanisms operate as specified under this test protocol, with substantial limits on independent validity. [E4, E8]

The authorized Claude development pilot exposed failures that the scripted result does not predict. Haiku with a Sonnet verifier generated matching candidates on two positive variants, but both required human review. A missing-source case exhausted its call allowance. Sonnet's complete V2 and no-semantic configurations never reached the provider because the shared spending limit could not accommodate another worst-case reservation. Those entries are missing model measurements. They cannot be used to rank Haiku and Sonnet. [E5, E6]

The decision remains **NO-GO for a research manuscript or submission**. This report closes the local implementation and evidence-synthesis stage. A defensible paper requires independent labels, a fresh held-out live-model study, better controlled comparisons and a measured contribution. Written company disclosure and authorship clearance are separate requirements. The current work can support a precise account of research engineering, subject to personal and disclosure review. [E9, E10]

## 2 Investigation task and baseline

Emergency privileged access creates a narrow evidentiary problem: several individually ordinary records may need to be joined before an analyst can assess a potentially out-of-scope action. A bank change and payment are insufficient on their own. The system must establish identity, order, authorization context, payment status and the availability of disconfirming evidence. A missing record must remain an information gap rather than becoming evidence that an action did or did not occur.

The implemented hypothesis makes those obligations explicit. The bank field must actually change; the payment must be posted; the actor, session and vendor must match; and the payment must follow the change by no more than 3,600 seconds. An approval, rollback, reversal, different actor or object, pending payment, or excessive delay can defeat the proposed pattern. The resulting statement describes a bounded event relationship. It does not establish intent, fraud or misconduct. The SAP-like transaction and table names are taxonomy labels in a synthetic model, not a validated simulation of SAP authorization semantics. [E2]

The audited demonstration at commit `2a3c28b` already had YAML-driven scoping, a stateful bounded ReAct-style session, nine read-only Elasticsearch tools, event-ID membership checks, a model-confidence threshold and local JSON persistence. The audit found that broader claims in its README exceeded what that code demonstrated. In particular, citation existence did not establish evidence support, deadline checks were not externally enforced, repair turns were incompletely counted, batch retrieval lost truncation information, and output handling could replace earlier results. [E1]

V2 was developed in a separate local clone on `feat/research-v2`. The original Downloads checkout remained unchanged. Its proprietary counterpart, unknown ignored outputs and environment file were outside this work. Only one hypothesis received a V2 implementation and evaluation. The original purchase-order and sales-order configurations remain historical baseline artifacts. [E1, E10]

| Capability | Audited demonstration | Implemented V2 scope |
| --- | --- | --- |
| Evidence identity | Event-ID membership | Snapshot, source locator, raw and field hashes |
| Retrieval | Request-scoped tools | Tenant, request and snapshot capability with result metadata |
| Relationships | Model interpretation | Deterministic joins, ordering and source-linked paths |
| Claim acceptance | Confidence threshold | Structural, domain, contradiction, support and coverage obligations |
| Runtime | Checks inside the loop | Parent-owned deadline and worker cancellation |
| History | Replaceable local outputs | Exclusive run directories, hash chains and experiment seals |
| Evaluation | No completed suite | Synthetic generator, tests, comparisons and preserved failures |

## 3 How the implementation works

**Source identity survives every representation.** A source record carries scope, actor, session, object, timestamps and its source locator. Snapshot construction sorts records deterministically, deduplicates exact repeats and rejects conflicting source locators. Canonical events bind the raw content to a hash, parser version and snapshot. Derived fields can be traced back to the pinned source record; model-generated text cannot create a trusted event. These are integrity checks under a trusted local host, not proof that the source's description of the world is true. [E2]

**The graph encodes relationships that code can check.** Nodes represent events, actors, requests, sessions, transactions, tables, business objects, field changes, policies and time windows. Every edge identifies its supporting source events. A `PRECEDES` edge means strictly earlier within the same actor, session and object chain. It makes no causal claim. When graph verification is enabled, a claim needs a contiguous verified path and every intermediate source event must have been retrieved. An unresolved model-proposed edge cannot satisfy that requirement. [E2]

**Evidence capsules preserve a bounded view of the case.** A capsule records its scope, hypothesis version and hash, selected source fields and event hashes, relevant relationships, missing data, retrieval completeness and resource limits. Six representations are implemented: raw records, the original legacy pipe format, a new quoted pipe format, typed JSON, compact typed edges, and a hybrid graph capsule. The original formatter omits actor, business-object and full-date information required by this hypothesis; that missing information is not silently reconstructed for the model. [E2, E7]

**The gateway controls what the investigator can retrieve.** A capability fixes tenant, request, snapshot, allowed sources and query templates, expiry, run ID and output limits. The model chooses from those templates; it cannot submit arbitrary Elasticsearch queries. Results include a query ID, stable ordering, returned and known counts, truncation, a continuation cursor, snapshot identity and timing. The in-memory and Elasticsearch paths validate results against the pinned source events. A model-visible write, shell, credential or outbound-network tool is absent. [E2]

**The investigator proposes a claim rather than deciding its own validity.** Live adapters select bank and payment IDs and identify the claimed actor, session and object. Deterministic compilation attaches field hashes and candidate paths. Verification still checks whether those references existed, were observed through an authorized query, share the correct scope, match the cited values, satisfy the joins and time window, and meet the hypothesis's domain rules. Severity is a fixed synthetic policy label, separate from evidence support. [E2]

**Contradiction and semantic checks answer different questions.** The contradiction query looks for related approvals, reversals and rollbacks. The semantic verifier receives one atomic claim and its cited fields, without the investigator's confidence or surrounding persuasive narrative. Its response must cite supplied evidence and provide an observable decision reason. Context separation limits information sharing; it does not make model errors statistically independent. Both Claude investigator tuples use Sonnet for verification, and the Sonnet tuple therefore uses the same base model in both roles. [E2, E5]

**Triage preserves unresolved cases.** Invalid structure or disconfirming evidence leads to abstention. Missing sources, incomplete retrieval, unresolved mandatory checks, partial semantic support or high semantic uncertainty can require human review. A surfaced claim has satisfied the enabled obligations; it remains an analyst-facing evidence statement. Review status is an output of the policy, not evidence that a person reviewed the case. Analyst feedback has an offline typed interface, but no analyst study has occurred. [E2]

**The parent process owns termination.** Execution follows explicit states from ingestion and scope validation through investigation, verification, coverage and a policy decision. Failure, expiry, cancellation and unsafe input are distinct terminal outcomes. The parent enforces wall-clock expiry independently of a blocked worker and terminates only its owned worker process group. The record retains observable traces and accounting; an interrupted report is marked partial. Operating-system scheduling and cleanup can add overhead, and provider computation already accepted can continue after local cancellation. [E2]

**The ledger makes an outcome inspectable.** Exclusive run directories preserve inputs, manifests, model-visible requests and responses, tool results, candidates, verification outcomes, resource counters and final decisions. Hash-linked traces and file seals expose changes to the recorded package. They are locally tamper-evident, not administrator-resistant or independently notarized storage. Private chain-of-thought is neither required nor retained. Labels and metrics are added by the evaluator after investigation. [E2, E4]

Calibration and priority estimation remain empirical gaps. Isotonic and logistic calibration interfaces exist but refuse generator-only labels. No fitted calibration, validated probability, learned priority policy, trained small model or measured analyst productivity is claimed. The score-free triage policy is the implemented operating point. [E2, E8]

## 4 Data and experimental design

The final scripted corpus uses generator version `ff-synthetic-2.0.0` and seed `20260906`. It contains 69 cases and 1,125 distinct canonical events across three generated families. A generated family is a group of sibling variants sharing a constructed scenario; it is different from a business-use-case family. There is one business hypothesis throughout. Development, test and challenge each receive one generated family with 23 variants. Siblings never cross splits. [E4, E8]

Each split covers positive and multi-hop chains; authorized and no-evidence cases; missing and conflicting records; duplicates and reordering; large and unseen-taxonomy variants; pending payment, wrong actor, wrong object, delayed payment and rollback; injected tool error and timeout; and seven injection variants covering concealment, false accusation, exfiltration requests, format hijack, exhaustion, cross-scope requests and split instructions. The final evaluation uses the test and challenge families, yielding 46 cases per configuration. [E4]

The labels include expected bounded claims, minimum support, required paths, contradictions, checks and terminal dispositions. Outcome labels, category names and fault schedules are kept out of model-visible inputs. This prevents direct answer-field leakage, but the shared generator and repeated templates still create correlated assumptions and potential shortcuts. The challenge family varies identities and parameters within the same attack designs. It is not an independently designed adaptive challenge set. [E8]

The final protocol was frozen at clean commit `6604e6f` before evaluating the held-out scripted cases. It includes six required baselines and thirteen additional representation, mechanism or budget configurations. The rule baseline uses deterministic correlation. Under the scripted protocol, the configurations named single-pass and ReAct also use scripted adapters, not live language models. Their names identify a processing strategy. [E4, E7]

Comparisons require two further qualifications. First, the scoped single-pass and demo-style baselines use legacy pipe evidence, while full-context and V2 configurations use other representations. Their results combine differences in available information with differences in control logic. Second, the demo-style baseline is an emulation within the modern supervisor, not an execution-equivalent replay of the original product or its historical model. Single-component V2 ablations offer narrower mechanism checks, still limited by the synthetic scripted setup. [E1, E7]

Default scripted limits were 10 seconds, 12 model-protocol calls, 30 tool calls, two repairs, 1,000 retrieved rows and a 2,000,000-byte retrieval allowance per run. Timeout-fault cases used a 0.5-second deadline. The Claude pilot used a 120-second ordinary deadline and the same call limits, plus a shared monetary ceiling. A byte-derived token upper bound is a reservation mechanism; it is not a measured tokenizer count. [E4, E5]

| Evidence stream | Evaluation workload | Appropriate interpretation |
| --- | --- | --- |
| Frozen scripted study | 19 configurations × 46 cases = 874 case-runs | Mechanism and terminal-policy behavior on two held-out generated families |
| Claude development pilot | Two investigator tuples × six configurations × six variants = 72 recorded case-runs | Development diagnostics; includes locally blocked Sonnet measurements |
| Earlier local-model work | Preserved Llama development pilots and interrupted final Ollama run | Interface and model failures; incomplete final comparison |
| Deterministic tests | 106 passed and one opt-in skip in final default log | Contract and implementation checks; six ES checks also passed separately |

The Claude pilot used the earlier development corpus, seed `20260905`, with only positive, multi-hop, authorized, no-evidence, missing-source and conflicting variants from its first development family. No paid test or challenge evaluation occurred. Running the rule baseline in both Claude experiments does not create a second independent model observation. [E5, E8]

## 5 Scripted results

Each configuration ran on the same 46 variants containing 28 expected underlying claims. TP counts surfaced claims matching the generator's exact rule; FP counts unsupported surfaced claims; FN counts expected claims not surfaced. Terminal agreement compares each case's final state with its required state. Claim and case counts differ when a case has multiple candidates. All nineteen configurations are shown. [E4]

| Configuration | TP | FP | FN | Terminal agreement |
| --- | --- | --- | --- | --- |
| rules | 23 | 12 | 5 | 19/46 |
| naive_single_pass | 23 | 12 | 5 | 19/46 |
| scoped_single_pass | 0 | 0 | 28 | 20/46 |
| demo_style_react | 0 | 0 | 28 | 20/46 |
| v2_no_semantic | 10 | 0 | 18 | 46/46 |
| v2 | 10 | 0 | 18 | 46/46 |
| v2_initial_scope_only | 0 | 0 | 28 | 36/46 |
| v2_legacy_pipe | 0 | 0 | 28 | 36/46 |
| v2_no_contradiction | 10 | 6 | 18 | 42/46 |
| v2_no_coverage | 10 | 0 | 18 | 44/46 |
| v2_no_graph | 10 | 0 | 18 | 46/46 |
| v2_no_injection_defenses | 24 | 0 | 4 | 32/46 |
| v2_no_selective_triage | 10 | 0 | 18 | 46/46 |
| v2_pipe | 10 | 0 | 18 | 46/46 |
| v2_raw | 10 | 0 | 18 | 46/46 |
| v2_small_context | 0 | 0 | 28 | 32/46 |
| v2_tool_budget_1 | 0 | 0 | 28 | 20/46 |
| v2_typed_edges | 10 | 0 | 18 | 46/46 |
| v2_typed_json | 10 | 0 | 18 | 46/46 |

Complete V2 surfaced claims in 10/46 cases, required review in 2/46, abstained in 16/46, rejected unsafe input in 14/46, failed in 2/46 and expired in 2/46. Both held-out splits had the same distribution: five surfaces, one review, eight abstentions, seven unsafe-input rejections, one failure and one expiry out of 23 cases. The failures and expiries were expected fault-injection outcomes. This agreement should not be reported as perfect detection recall. [E4]

Surfaced claim precision was 10/10, while surfaced recall of the underlying labeled patterns was 10/28. The remaining 18 comprised 14 attack cases with a real underlying chain, two injected tool failures and two timeouts. Keeping both denominators visible captures the deliberate tradeoff: refusing a case can satisfy the safety policy while leaving its underlying pattern unreported. The experiment does not estimate how common such cases are outside the generator. [E4]

Candidate quality also matters. Complete V2 retained 22 candidate claims, of which 10 matched the generator and 12 did not. Its candidate precision was therefore 10/22 even though surfaced precision was 10/10. All 44 candidate supporting citations referred to existing events, but only 20/44 satisfied the generator's citation-support rule. The software successfully referencing a real event was plainly insufficient to establish that the candidate matched the expected claim. This support metric is still a generator check, not independent expert semantic judgment. [E4, E8]

| Complete V2 measure | Numerator and denominator |
| --- | --- |
| Retrieved minimum support events | 20/56 |
| Cited minimum support events | 20/56 |
| Existing candidate citation IDs | 44/44 |
| Generator-supported candidate citations | 20/44 |
| Matching candidate entities | Precision 30/60; recall 30/84 |
| Valid graph temporal edges | 34/34 |
| Matching candidate relationship edges | Precision 20/32; recall 20/38 |
| Exact matching candidate paths | Precision 10/22; recall 10/28 |
| Attached labeled contradictions | 4/4 |
| No surfaced claim on labeled abstention cases | 16/16 |
| Unsupported surfaced claims | 0/10 |

These metrics describe different stages. A valid temporal edge can appear in a rejected candidate. Retrieval recall includes evidence from attack and fault cases that the policy prevents the investigator from processing normally. Contradiction recall counts attached disconfirming records, rather than all correct decisions to abstain. None should be substituted for an overall measure of investigative usefulness. [E8]

The contradiction ablation surfaced six unsupported claims and disagreed with four terminal labels that complete V2 handled as specified. The coverage ablation converted two required-review cases into abstentions. Removing injection defenses allowed all fourteen attack variants through the unsafe-input gate and increased surfaced underlying matches to 24, but reduced terminal agreement to 32/46. This is why greater claim recall alone is not the objective of the current policy. [E4]

The no-graph, no-semantic and no-selective-triage configurations matched complete V2's surfaced and terminal outcomes. The current experiment supplies no measured incremental outcome benefit for those components. The scripted investigator can correlate rows deterministically, and the scripted verifier produces little ambiguity. Those properties limit the experiment's ability to test the proposed benefits; they are not evidence that a future live-model benefit exists. Raw, quoted pipe, typed JSON, typed edges and hybrid representations likewise did not separate on these outcomes. [E4, E7]

Legacy-pipe and initial-scope-only V2 missed all 28 underlying expected claims. The one-tool and two-row-capsule variants also surfaced none. Those failures show that the supplied fixtures depend on available identity information, controlled drill-down and adequate evidence capacity. They do not measure a universal advantage of graph capsules or establish an optimal resource budget. [E4]

Recorded complete V2 scripted latency was approximately 0.209 seconds at the median and 0.269 seconds at the nearest-rank 95th percentile. The counts include 70 logical model calls and 72 tool calls across 46 cases. Logical calls to scripted adapters are software steps, not provider inference, and the timing is unsuitable as a live-model or production latency claim. Family-bootstrap intervals are retained in raw summaries, but only two independent generated groups were available; identical sibling patterns yield many degenerate intervals. No significance or generalization claim follows. [E4, E8]

## 6 Claude pilot and spending

The paid protocol used the recorded investigator IDs `claude-haiku-4-5-20251001` and `claude-sonnet-5`, with Sonnet as the separate-context verifier. Haiku used temperature zero; Sonnet used provider-default sampling. Thinking was disabled, output was capped at 2,048 tokens and no seed parameter was supported. These are the model identities and settings preserved for the September pilot, not a claim about future provider availability or reproducibility. [E5]

The table separates model observations from entries blocked before generation. TP and FP refer to surfaced claims. Every configuration has six recorded case entries, but the two Sonnet V2 rows contain no provider observations. “Not sampled” must remain missing in any subsequent model comparison, even though the raw execution table correctly records local expiry. [E5, E6]

| Configuration | Haiku TP and FP | Haiku terminal agreement | Sonnet TP and FP | Sonnet terminal agreement |
| --- | --- | --- | --- | --- |
| rules | 2; 2 | 3/6 | 2; 2 | 3/6 |
| naive_single_pass | 2; 2 | 3/6 | 2; 1 | 4/6 |
| scoped_single_pass | 0; 0 | 3/6 | 0; 1 | 4/6 |
| demo_style_react | 0; 0 | 1/6 | 0; 0 | 0/6; budget affected |
| v2_no_semantic | 0; 0 | 3/6 | Not sampled | Not sampled |
| v2 | 0; 0 | 3/6 | Not sampled | Not sampled |

Haiku's full V2 run retained matching candidates in both positive cases but surfaced neither. The single-hop claim received `PARTIALLY_SUPPORTED`; the multi-hop claim received `SUPPORTED` with high uncertainty. Both entered review. The authorized candidate failed the deterministic approval-scope check, the no-evidence case abstained, and a contradiction query supplied the approval record that blocked the conflicting case. The missing-source case repeatedly requested actions until it exhausted twelve calls, yielding expiry instead of the expected review. Its bounded termination is working engineering behavior; its failure to stop appropriately is a live-model workflow defect. [E5, E11]

The single-hop trace helps explain the semantic disagreement. The investigator's statement referred to a policy node and verified graph edges. The verifier saw the cited event fields, including approved operations and timestamps, but not the policy object or graph asserted in the wording. It accepted much of the event sequence while questioning those additional assertions. This is evidence of a mismatch between claim wording and the verifier's evidence package. Independent adjudication is needed to determine whether that particular review was necessary. A future design should either restrict statements to the verifier-visible facts or supply narrowly scoped, source-linked deterministic derivations. [E11]

Removing the semantic verifier did not surface Haiku's two positive candidates either: model-declared unresolved unknowns still triggered review. Therefore the pilot does not demonstrate that adding semantic verification improved final decisions. The stronger observation is that structural, contradiction and review obligations remain distinct, and a correct candidate can fail to reach the normal surface state. [E5, E11]

Naive live configurations recovered the two positive claims but also surfaced unsupported claims on authorized and/or conflicting cases. Haiku demo-style ReAct exhausted its call allowance in five of six cases. Sonnet demo-style ReAct had four call-budget expiries, one parent deadline and one spending-limited case. The spending-limited case made a provider call before a later reservation was denied. All twelve entries in Sonnet's subsequent V2 and no-semantic configurations were denied locally before provider generation. Configuration order and shared remaining budget thus confound the investigator comparison. [E5, E6]

Before each generation, the shared ledger reserved the cost of the full model input capacity plus maximum output. Returned provider usage replaced that reservation with measured token cost. A clearly rejected request could settle to zero; an interrupted or ambiguous request retained its reservation. At the recorded rates, Haiku used $1 input and $5 output per million tokens, and Sonnet used $2 input and $10 output. These are historical billing assumptions in the pilot record, excluding taxes and any account-level reconciliation. [E5, E6]

| Spending component | Recorded USD |
| --- | --- |
| Successful preflight | 0.021749 |
| Haiku investigator experiment | 0.480711 |
| Sonnet investigator experiment | 0.458904 |
| Total measured token cost | 0.961364 |
| Unresolved Sonnet worst-case reservation | 2.020480 |
| Measured plus unresolved exposure | 2.981844 |
| Authorized pilot ceiling | 5.000000 |

The sanitized ledger records 195 reservations: 194 settled and one unsettled. Two early schema preflights were rejected before generation and settled to zero. The unsettled Sonnet call was still in flight when the parent deadline fired. Its reservation is a retained upper bound, not an observed charge. The final ledger would need $5.002324 of measured-plus-reserved exposure to reserve another full Sonnet call, just beyond the $5 ceiling. No allowance was reset and no further paid calls were made. [E6]

The conservative accounting protected the authorized ceiling but reduced experimental coverage. A future authorized study should estimate a request-specific input bound or use provider token counting while preserving safety margin, and ensure each comparison has enough reserved funding before it starts. Reclaiming the unresolved amount without billing evidence would defeat the purpose of the spending control. This report authorizes no new experiment or expenditure.

## 7 Failures and security interpretation

Early failures are part of the evidence history. A development pipe representation omitted a content hash required by the scripted adapter. The first local Llama pilot mixed a final action with a tool query and exhausted schema repairs. Later pilots produced valid structures but abstained on positive cases or used transaction/table text where an object ID was required. Changes to grammar constraints, validation feedback and context packaging followed development evidence. Those failed runs were preserved instead of being overwritten by corrected versions. [E7]

Claude integration also required development repairs. Initial requests failed provider schema validation; the adapter subsequently inlined schema definitions while retaining strict local validation. The successful preflight and final pilot used the corrected adapter at `d702eef`. Those later provider changes did not rewrite the frozen scripted experiment at `6604e6f`. The final Ollama experiment was explicitly interrupted when the user selected Claude and remains incomplete. [E5, E7]

Security evidence has a narrower meaning than general prompt-injection resistance. Complete scripted V2 had zero policy breaches in fourteen labeled attack cases and zero successes under the fourteen mechanical attack-goal proxies. The phrase detector recognizes the finite attack templates used by the generator. In the no-defense variant, the scope gateway and parent supervisor remained active. Therefore the ablation removes selected text defenses rather than all isolation boundaries. [E4, E8]

An attack-policy breach means surfacing a claim when policy requires unsafe-input rejection. It is not necessarily the attacker achieving concealment, fabrication, exfiltration or another objective. The separate proxies examine selected observable outcomes, such as a fabricated accusation, schema rejection, exhaustion or returned wrong-request rows. They are not blinded causal adjudications, and an empty response could occur without an attack. No live-model injection study was completed in the Claude pilot. [E8]

The gateway's lack of an exfiltration tool narrows the available action surface. It does not establish that every model-generated string is safe. The host, administrator, trusted code and dependencies remain outside the attacker model. The unauthenticated Elasticsearch service was bound to loopback for this synthetic workload, and its owned process was stopped after evaluation. No production security assurance should be inferred from these local checks. [E2, E8, E10]

## 8 Validation and reproducibility

At the frozen scripted checkpoint, the default log recorded 100 passed tests and one opt-in skip; the enabled Elasticsearch suite recorded six passes. After the Claude adapter and spending checks were added, the final default log recorded 106 passed, one skipped and ten warnings in 3.39 seconds. The separately enabled Elasticsearch run passed six tests in 1.54 seconds. These are separate suite runs, not a claim of 112 distinct tests. They validate the recorded software state; they are not coverage percentages or a formal proof. [E3]

The test inventory covers contracts, parsing, provenance, graph paths, scope denial, pagination, integrity, schema repair, semantic-reference validation, triage, cancellation, deadlines, ledger immutability, spending and end-to-end synthetic investigations. The native evaluation service used Elasticsearch 8.13.4 with a 512 MB heap on loopback port 19200. The final seeded index was explicitly mapped, ownership-checked, content-verified and write-blocked. The fresh in-memory reproduction workflow also completed 874 case-runs and generated summaries and figures. The provided CI workflow has not been pushed or executed on GitHub. [E2, E3, E12]

Reproduction uses Python 3.13 and `requirements-lock.txt`. From a clean committed repository, create the documented environment, run the default suite, start the dedicated local Elasticsearch service, and run the opt-in integration tests. Then invoke `.venv/bin/python scripts/reproduce.py artifacts/reproduction-NEW`. Add `--memory` for the equivalent scripted workflow without Elasticsearch. The destination must be new: the script refuses to overwrite existing evidence. [E12]

The reproduction command generates and validates fresh synthetic data, verifies and seeds only its owned index, freezes the protocol, runs the nineteen configurations on test/challenge splits and derives tables and figures. It never depends on the original Downloads environment file or ignored outputs. The corpus hash is reproducible for the same generator and seed; run IDs, timings, provider responses and resulting run hashes need not be bit-identical. [E12]

Existing sealed experiments can be inspected with `scripts/analyze_experiment.py` and individual cases with `scripts/render_case.py`. Analysis first verifies the experiment inventory and file hashes. The self-contained case views escape content and expose claims, evidence and decisions for review. The implementation repository contains sealed experiment archives and their SHA-256 manifests; Appendix B identifies their exact locations. [E4, E5, E12]

## 9 Completion boundary

The scoped engineering milestone is complete. The table accounts for the handoff's major requirements and the limits that remain. “Implemented” describes the local code and tests; it does not imply empirical validity, broad domain coverage or permission to release. [E2, E3, E9]

| Requirement | Recorded status | Remaining boundary |
| --- | --- | --- |
| Provenance and immutable snapshots | Implemented and tested | Host and source truth remain trusted |
| Graph and hypothesis contracts | Implemented for one task | Other business hypotheses unevaluated |
| Capsules and scoped gateway | Six formats and two backends | No measured live-model representation advantage |
| Atomic verification and contradiction | Implemented and exercised | Synthetic domain rules need independent review |
| Semantic support | Separate-context adapters exercised | No expert support labels or validated verifier accuracy |
| Selective review and calibration | Deterministic policy; calibration interface | Calibration fitting deliberately deferred |
| Budgets and cancellation | Parent supervisor and shared spending ledger | Provider-side completion may outlive cancellation |
| Injection controls and ledger | Regression cases and sealed artifacts | No adaptive attack study or administrator-resistant storage |
| Evaluation and evidence pipeline | Required scripted comparisons completed | Held-out live-model comparison remains incomplete |
| Analyst feedback and priority | Offline feedback contract | No analyst study or measured review benefit |
| Research outputs | Cards, evidence, outline and this report | Manuscript and release remain gated |

## 10 Research decision and next work

The evidence supports further investigation of whether explicit evidence obligations can reduce unsupported surfacing while preserving useful findings at an acceptable review cost. It has not yet established that contribution. The scripted ablations exercise several safeguards, while the live pilot shows excessive review, unproductive loops and incomplete comparison coverage. Publishing the current counts as model-effectiveness results would obscure those limitations. The recorded paper decision therefore remains NO-GO. [E9]

The next development work should first address observable failures. Stop repeated identical queries when they add no evidence and make missing-source termination explicit. Restrict claim wording to what the verifier can inspect, or add narrowly scoped deterministic derivations with source references. Evaluate whether reviews arise from genuine uncertainty, missing context or overbroad statements. Keep these changes in development and preserve the current sealed runs; the already inspected held-out cases cannot be reused as untouched evidence. [E7, E11]

The next empirical protocol should use more independently constructed cases and independently adjudicated claim, contradiction and terminal labels. It should separate domain correctness from policy agreement, predefine attack goals, freeze prompts and policies, and reserve enough approved resources to complete every comparison. Matched-information single-pass baselines are needed to isolate controller effects from legacy serialization loss. Repeated model runs should be grouped by case, and any sample-size justification should use independent case families rather than the total number of executions.

Only after suitable development labels exist should calibration methods be fitted and evaluated on separate data. Analyst utility needs an actual review study measuring false escalations, missed patterns, decision quality and review time. A final literature comparison must establish what the evidence-contract mechanism adds beyond existing tool use, graphs, structured output, verification and selective prediction. Those techniques are not novel individually. The current report makes no novelty claim. [E9]

Company disclosure and authorship require written resolution before a manuscript or public release. Customer identity, customer instances, deployment, adoption and production outcomes remain excluded. Public availability of the old demonstration does not supply permission for new disclosures. A conditional manuscript outline already exists; it should be promoted to a draft only when both the empirical and permission requirements are met. [E9, E10]

For graduate-application preparation, this work supports evidence organization around bounded systems design, verification, experiment preservation and failure analysis. It cannot substantiate production impact, a validated fraud detector, a calibrated model or a submitted paper. The code and this synthesis were produced with Codex assistance under Arin's task direction. Arin should describe his actual decisions and validation responsibilities, personally write and approve application prose, and follow the relevant program's authorship rules. [E10]

## Appendix A Metric reading guide

Atomic matching requires the expected claim type, actor, session, object, time range and minimum support set, with one-to-one matching and a small explicit overclaim-word rejection list. TP, FP and FN therefore express the generator's bounded matching rule. The rule does not adjudicate every nuance of a natural-language statement. Candidate metrics include rejected and reviewed proposals; surfaced metrics include only claims selected for the normal analyst surface. [E8]

Terminal agreement counts cases whose final state equals the required generator state. Surface coverage counts cases with at least one surfaced claim over all cases. Selective risk divides unsupported surfaced claims by all surfaced claims. A configuration that surfaces nothing has undefined selective risk, not zero demonstrated risk. Review volume counts the review-required state over all cases; ordinary surfaced findings can also require a human's attention, so this number is not total analyst workload. [E8]

Citation existence tests whether an ID occurs in the pinned snapshot. Synthetic citation support counts citations on the required path of a generator-matching candidate. Event recall measures retrieval of minimum-support IDs; evidence recall measures citing them. Entity, edge and path measures compare the corresponding candidate structures with label structures. Contradiction recall counts labeled disconfirming events attached to claims. The denominators deliberately expose what stage is being measured. [E8]

Recorded latency includes worker startup and investigation; decision and cleanup timing are available separately. Model tokens are measured only when the provider returned usage. Interrupted calls may have unknown tokens and cost, with reservations retained for the paid pilot. Bootstrap summaries resample whole generated families 400 times with a fixed seed. They should not be interpreted as informative population intervals when only two families and repeated templates are available. [E4, E6, E8]

## Appendix B Evidence and source record

The canonical implementation repository is `/Users/arin.mallanna/personal/ff-insights-v2`. Evidence IDs below link to local primary artifacts or their inspection entry points. Archive members preserve the raw run records. The report synthesizes those sources without modifying their sealed results.

**E1 Baseline provenance.** [Baseline audit](BASELINE_AUDIT.md) and [baseline manifest](../../evidence/baseline/manifest.json). Audited commit: `2a3c28bec9b1f187af349767da7d4e74f6982d32`. The original checkout is `/Users/arin.mallanna/Downloads/ff_insights_v1.1`.

**E2 Implementation.** [Architecture](ARCHITECTURE.md), [system card](SYSTEM_CARD.md), [hypothesis contract](../../applications/sap/hypotheses/vendor_bank_change_payment.v2.json), [verification](../../core/v2/verification.py), [control](../../core/v2/control.py), [gateway](../../core/v2/gateway.py), [ledger](../../core/v2/ledger.py) and [calibration](../../core/v2/calibration.py). Evidence-package source checkpoint: `b403d73` on `feat/research-v2`.

**E3 Validation.** [Final default tests](../../evidence/validation/final-tests.txt), [final Elasticsearch tests](../../evidence/validation/final-es-tests.txt), [frozen default tests](../../evidence/validation/frozen-scripted-tests.txt), [frozen Elasticsearch tests](../../evidence/validation/frozen-es-tests.txt) and [final seed receipt](../../evidence/validation/final-seed-receipt.json).

**E4 Frozen synthetic study.** [Scripted comparison](../../evidence/reports/scripted-comparison.csv) and [synthetic and local evidence archive](../../evidence/experiments/synthetic-and-local-evidence-20260906.tar.gz). Members `final-scripted/protocol.json`, `summary.json`, `summary-by-split.json`, `per-case.jsonl` and each run's input, manifest, trace, report and seal preserve the analysis basis. Frozen commit: `6604e6ff3d1943cb080cded74207d7663974253b`. Protocol SHA-256: `d8fb1bd35cbcdfb74cf5f0af02cd2b52306e2cc799f645d008f8c35257cb94f3`.

**E5 Claude study.** [Pilot protocol and interpretation](CLAUDE_PILOT.md), [Haiku comparison](../../evidence/reports/claude-haiku-comparison.csv), [Sonnet comparison](../../evidence/reports/claude-sonnet-comparison.csv) and [Claude evidence archive](../../evidence/experiments/claude-development-pilot-20260906.tar.gz). Members `claude-haiku-pilot/` and `claude-sonnet-pilot/` retain the complete local execution records. Frozen adapter commit: `d702eef36dd1c32da60aa23e6f7149049de8267e`. The archive also retains the non-secret model inventory and failed preflights.

**E6 Spending.** [Sanitized spending summary](../../evidence/validation/claude-spending-summary.json) and [spending implementation](../../core/v2/spending.py). Amounts in this report are derived from recorded provider token usage and unresolved reservations; they are not an account invoice. Credentials and the runtime SQLite file are excluded from the archives.

**E7 Development history and configurations.** [Development failures](DEVELOPMENT_FAILURES.md), [failure analysis](FAILURE_ANALYSIS.md), [configuration definitions](../../eval/configurations.py) and preserved development and interrupted-run members in E4. Historical plans for final Ollama execution are superseded by its recorded interruption.

**E8 Dataset and metric semantics.** [Dataset card](DATASET_CARD.md), [metric definitions](METRICS.md), [metric implementation](../../eval/metrics.py) and [threat model](THREAT_MODEL.md). Final dataset SHA-256: `4e87dea56c51d83959b3cc6fae04e34eadaf532a1678845e9c2488d1bb6e15ea`. Development dataset SHA-256: `36724623a40c4148cf956562842c818756ac376d0681bbb666c9d093326048d5`.

**E9 Publication readiness.** [Paper decision](PAPER_DECISION.md) and [conditional manuscript outline](MANUSCRIPT_OUTLINE.md). This technical report does not change the manuscript or publication maturity level.

**E10 Cross-repository governance.** [Application-safe evidence notes](APPLICATION_SAFE_EVIDENCE.md) and the FF Insights workstream under `/Users/arin.mallanna/personal/grad-apps-fall-2027/03_research-workstreams/ff-insights/`. Shared claims FFI-010 through FFI-013 and the evidence manifest were registered at `cbd73a4`. The governing execution handoff is `00_shared-profile/agent-handoffs/ASTRA_FF_INSIGHTS_IMPLEMENTATION_RESEARCH_PROMPT.md` in that repository.

**E11 Inspectable cases.** [Claude evidence view](../../evidence/reports/claude-review.html) and [scripted evidence view](../../evidence/reports/scripted-positive-review.html). Detailed Claude report members are `claude-haiku-pilot/v2/run-45d2282becc2411dab1c004e2c6e4229/report.json` for the single-hop review, `run-1b2f4fe0453f47159a3e9c68483be9bf/report.json` for the multi-hop review, `run-716b4866b351456fb7f3a00a153ffafe/report.json` for the authorized-case rejection and `run-1a920be9a9774496925f85be9a87305c/report.json` for the conflicting case, all beneath the same V2 archive directory.

**E12 Reproduction.** [Reproduction instructions](REPRODUCIBILITY.md), [one-command workflow](../../scripts/reproduce.py), [sealed analysis](../../scripts/analyze_experiment.py), [case renderer](../../scripts/render_case.py) and [CI definition](../../.github/workflows/research.yml). The comparison figures are preserved at `evidence/reports/scripted-disposition.png` and `evidence/reports/scripted-risk-coverage.png`; their numeric inputs remain in E4.

Archive integrity identifiers:

**Synthetic and local archive SHA-256**

`e128813d99c27e7c5d233de41a524c05b3c01c6d5b26446ee90eb7908796c47d`

**Claude development archive SHA-256**

`b7b36252c04b3d3abba5fc770e81271a0f0a96ece2965d71ebb8f499e83def85`

No additional model calls, changes to the sealed experiments, public push, manuscript submission or publication were part of preparing this report.
