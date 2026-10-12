# Atomic memory retrieval: expanded study

**Draft: scored collection and analysis are still pending.** Study date: October 11, 2026; execution receipts use UTC. The methods below were fixed before scored collection. No retrieval winner, downstream accuracy result or final latency claim is available in this draft. Results will be inserted only after all scheduled receipts and the analysis checks are complete.

This study asks whether small, independently switchable changes recover the complete evidence needed for a decision, and whether a reader then uses that evidence correctly. It compares deterministic retrieval with two locally executed encoder scorers and learned branch selection. Accuracy and context completeness take priority over reducing returned tokens. A short packet that omits a correction or prerequisite is a failure even when its remaining documents look relevant.

The expanded experiment is separate from the [frozen October 9 pilot](../study-2026-10-09/REPORT.md). That pilot exposed a concrete failure: a reader received a governing correction but wrote the older value, while structural checks passed. Its later convention audit also showed why literal scoring must be described precisely. The new study keeps evidence recovery, exact answer agreement, citation agreement, artifact production and clean completion as distinct measurements. It does not pool the pilot's cases, retries or audited scores with these rounds.

## Questions, comparisons and scope

The experiment has three connected rounds. Round 1 crosses three atomic interventions in a deterministic retrieval baseline. Round 2 repeats that factorial with six fixed retrieval engines, including local decision-only models and hierarchical pruning. Round 3 supplies selected packets to a fresh decision reader and separately tests discovery through a fictional virtual filesystem. Each round can expose a different failure stage: eligibility, candidate generation, packing, source use or task completion.

A decision-only model here means an encoder that scores a query paired with a document or branch description. It does not generate an answer or conduct a conversational filesystem search. Cross-encoder reranking after first-stage retrieval is an established arrangement, but every candidate pair still requires tokenization and inference. Relevance scores are not calibrated probabilities of current authority, correct facts or safe action. [Sentence Transformers retrieval and reranking documentation](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)

The motivating literature is broader than these fixtures. LongMemEval separates memory indexing, retrieval and reading, and tests updates, temporal reasoning and abstention; its conversational benchmark does not certify this experiment's artifact workflow. The [model research note](MODEL-RESEARCH.md) records sixteen primary sources, candidate licenses and the reasoning behind the local comparisons. Those sources motivate mechanisms to test, rather than supply expected results for the fictional bank. [LongMemEval paper](https://arxiv.org/abs/2410.10813)

No production capture CLI, personal PARA corpus or folder structure is changed. All public records, names, tasks and artifacts are newly authored fiction. Original records remain retained in every arm. The experiment evaluates the use of metadata and retrieval policies over this bank; it does not establish reliable automatic extraction of aliases, dependencies, source-version ledgers or authority from arbitrary prose.

## Corpus, authorship and held-out units

Two isolated LLM authors each produced 24 semantic families, each containing two task queries and ten retained records. The final bank therefore contains 48 family histories, 96 tasks and 480 records. The protocol allowed ten to fourteen records, but the realized shape is uniformly ten. The exact source/derived counts differ by author:

| Corpus | Families | Tasks | Original records | Derived views | Total records |
|---|---:|---:|---:|---:|---:|
| Author A | 24 | 48 | 192 | 48 | 240 |
| Author B | 24 | 48 | 216 | 24 | 240 |
| Combined | 48 | 96 | 408 | 72 | 480 |

The authors worked separately, but shared documentary framing and causal templates. Repeated record roles, provenance cues and domain framing constrain the diversity; changing names or numbers does not turn related templates into independent population draws. Author A and B label bank provenance, not independently sampled author populations or interchangeable counts of released model versions. Peer LLM reviews checked the declared answers against original bodies and corrected an adoption-evidence omission and an ambiguous internal courier handoff before collection. No human gold adjudication occurred.

Each author includes three families in each of eight strata: late correction, scope exception, unresolved conflict, missing prerequisite, Unicode/alias, late import, missing edge and wrong incorporation ledger. Ground truth declares `ready` or `hold`, answer keys, critical values and a sufficient-original evidence set. Every task currently has one authored sufficient set. These sets are neither exhaustively adjudicated alternatives nor proven minimal bundles; a different valid evidence combination may exist outside the scoring declaration.

The development split takes the lowest-ID family in six predeclared strata per author. Author A contributes correction, scope, conflict, prerequisite, Unicode and import development families; Author B contributes conflict, prerequisite, Unicode, import, missing-edge and wrong-ledger families. This yields 12 development and 36 held-out families while preserving held-out examples of every stratum. The initial unexecuted 01–06 split could remove entire strata because authoring order grouped similar cases; its correction preceded scored outcomes. The exact split is in [family-split.json](family-split.json).

Both tasks, all factor cells, all distractor environments and all repeated measurements stay within their family split. **The primary held-out unit is 36 families, not 18,432 independent cases.** Development results are retained separately. Reader-family selection uses a predeclared hash of family identity and does not choose cases based on retrieval outcomes.

For each task, the collection includes every record from its own family plus deterministically selected cross-family distractors. The 48- and 144-document collections are nested, so the larger environment adds noise to the same underlying target records. The fixture builder uses target-family identity to construct that environment. Engines receive the query, retained collection documents and public metadata, with no target-family label or gold answers. Distractors are exposure conditions, not new tasks or new independent histories. [Author A bank](author-a.json), [Author B bank](author-b.json), [benchmark implementation](benchmark.py)

## Three atomic interventions

The three bits in a factor code always mean A, B and C in that order. Thus `000` has none enabled, `100` adds only index cues, and `111` enables the joint policy. All eight combinations are evaluated at both collection sizes and byte budgets, for every engine.

| Factor | Off | On | What the contrast includes |
|---|---|---|---|
| A: index cues | Generic record header | Add existing title, scope and workstream aliases | Cue quality and the added serialization bytes |
| B: dependency expansion | Pack ranked seeds | Traverse declared links, incorporation pointers and supersession edges | Bounded graph expansion within the same packet budget |
| C: derived-view version gate | All records eligible | Exclude derived views with stale, missing or inconsistent declared ledgers | Metadata consistency, without deleting original records |

The original body never changes with A. Public graph and ledger metadata appears in every rendered record, including A-off packets. Branch identity and aliases are available to hierarchical engines in both A settings; A-on additionally supplies record titles and scopes in branch descriptions. A therefore has a precisely implemented meaning, rather than removing every clue to workstream identity when off.

B expands breadth-first from each ranked seed to depth two, with at most sixteen newly appended records per seed. Expansion follows declared references, incorporation IDs, superseded predecessors and reverse supersession edges. Cycles are bounded by visited sets; missing references are recorded. These fixed limits prevent unbounded closure, but do not demonstrate recovery of arbitrarily long dependency chains. An expanded original can lie outside a reranker's initial candidates, so candidate completeness is a hard ceiling only when B is off.

C treats derived views as eligible only when their incorporation ledger is present, internally consistent and compatible with available declared source versions and supersession. Scope compatibility is literal equality or `all`; broad desk views use `all`. Natural-language scope equivalence is not inferred. Every original remains eligible, including obsolete originals that a reader must interpret in context. Filtering a derived view is neither a warning appended to it nor a repaired summary.

The gate checks declared metadata, not whether the view's prose truthfully reflects its ledger. A falsely current ledger can leave an incorrect body eligible. Missing or incorrect edges can likewise prevent expansion from finding necessary evidence. The stress strata make some such failures observable, but they are not a general adversarial validation of metadata extraction or semantic consistency. [Prospective plan](PLAN.md), [gate and expansion code](benchmark.py)

## Retrieval engines and fixed candidate policies

The engine comparison changes ranking and pruning while preserving the corpus, factors, tasks and packet budgets. No learned model is trained or tuned on this bank. Document BM25 uses Unicode normalization, case folding and deterministic ID tie-breaking. The six policies are:

| Engine | Candidate generation and scoring |
|---|---|
| Flat BM25 | Rank all eligible records lexically |
| Hierarchical BM25 | Rank branch descriptions; retain two branches; use document BM25 inside them |
| MiniLM rerank | Take global BM25 top 32; score and reorder those pairs with pinned MiniLM |
| Mixedbread rerank | Take global BM25 top 32; score and reorder with pinned Mixedbread |
| Learned branches | Score every branch with Mixedbread; retain two; score eligible records within them |
| Learned branches + rescue | Same routing, plus a fixed global BM25 top-eight candidate rescue before document scoring |

Branch descriptions retain workstream identity and aliases and, with A on, concatenate titles and scopes. They are not generated answer-bearing summaries. The rescue arm always uses the same rule; it is not switched on only after observing a failed route. Rankings preserve eligible IDs, candidate IDs and selected branches, allowing excluded evidence to be distinguished from evidence lost while fitting the packet.

Hierarchy can improve representation while pruning away an entire relevant branch. That distinction motivates the flat, routed and rescue comparisons. It should not be read as a claim that directory traversal is intrinsically superior. RAPTOR's published comparison, for example, finds collapsed retrieval preferable to layer-by-layer retrieval in a limited subset, illustrating that a useful hierarchical representation does not itself establish a winning pruning policy. [RAPTOR paper](https://arxiv.org/html/2401.18059v1)

Round 1 and Round 2 together schedule 96 tasks × 8 factor cells × 6 engines × 2 collection sizes × 2 budgets = **18,432 packet comparisons**. Ranking is reused across B and budget conditions, giving 4,608 stored rankings. The shuffled execution order is fixed by seed 1011. This volume permits paired mechanism comparisons; it does not inflate the number of independent families.

## Actual local model execution and cost boundaries

Both encoder checkpoints were acquired outside the repository, checksum-verified and actually loaded through ONNX Runtime on CPU. Preflight inference passed; these are executed artifacts, not merely models found in a catalog. The host is an Intel Core i5-12450H with approximately 16.9 GB installed memory. Each scorer uses two intra-op threads and batch size twelve. Public receipts retain hardware and package information without credentials or private host paths. [Preflight receipts](preflight.json), [model runtime](model_runtime.py)

| Executed scorer | Publisher parameter count and language | Pinned revision | Quantized artifact bytes |
|---|---|---|---:|
| MiniLM L6 v2 | 22.7M; English | `233902d25c440f23af6f7d6e94d2946bac0bee0a` | 23,200,716 |
| Mixedbread xsmall v1 | 70.8M; English | `b5c6e9da73abc3711f593f705371cdbe9e0fe422` | 87,245,802 |

Both publisher cards specify Apache-2.0. That permits these local weight comparisons, while complete reproducibility of training data and training procedures is a separate question. MiniLM's published throughput is measured on a V100 GPU and is not a desktop CPU estimate. Mixedbread's published evaluation is an aggregate across selected BEIR datasets, not this memory task. Results belong to the exact quantized exports, tokenizer files and backend recorded here; full-precision equivalence is not assumed. [MiniLM publisher card](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2), [Mixedbread publisher card](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1)

The selected MiniLM ONNX file has SHA-256 `c80a8b34256ea453093d612e3ac48d3d965a0c0a48c7906709af8b8e28461bf9`; Mixedbread has `15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30`. Configurations and tokenizers are also pinned in [freeze.json](freeze.json). The scorer cap is 512 combined query/document tokens, including special tokens. Truncations are counted. A model can rank the visible portion well while missing a later correction, so token-window coverage remains distinct from packet completeness.

Development rehearsals scored the same 32 pairs twice without caching and returned equal ranked IDs. MiniLM took about 12.7–15.6 seconds; Mixedbread about 22.6–30.0 seconds. These narrow setup measurements are excluded from scored accuracy and do not stand in for final performance. The final latency comparison uses a separate, uncached warm block: six development families, two queries, two repetitions and six engines, for 144 observations. Its elapsed cost includes index/rank/pack work, but excludes model acquisition and loading. Index and packing are not separately instrumented.

The large factorial reuses identical model scores across repeated cells. Its cached rank receipts therefore cannot support query-latency claims. Acquisition/checksum, loading, first scoring and uncached warm measurements remain separate. Three token quantities also remain separate: local scorer input tokens, returned reader context and provider-reported reader usage. A local classifier still consumes computation and input tokens; eliminating a generative selection call does not make retrieval free. [Sentence Transformers efficiency guidance](https://www.sbert.net/docs/cross_encoder/usage/efficiency.html)

## Whole-record context budgets and structural ceilings

Packets are capped at 4,096 or 8,192 UTF-8 bytes. The packer appends whole rendered records in policy order. A record that would exceed the remaining budget is skipped and recorded; it is never silently truncated into an apparently complete read. Oversized records do not disappear from retention. Byte budgets are exact serialization limits, not model-token allowances.

Prospective feasibility inspection found that the authored sufficient bundle often cannot fit the smaller budget. Among 72 held-out task queries, 49 bundles fit 4,096 bytes with A off, and only 32 fit with A on. All 72 fit 8,192 bytes in either cue condition.

| Held-out authored-bundle feasibility | A off | A on |
|---|---:|---:|
| 4,096 bytes | 49/72 (68.1%) | 32/72 (44.4%) |
| 8,192 bytes | 72/72 (100%) | 72/72 (100%) |

These are ceilings for complete recovery of the declared whole-record bundle, not semantic correctness ceilings. The authored sets are non-exhaustive, so a different sufficient combination or a smaller passage representation might support the task. Under this frozen score, however, a bundle that cannot fit cannot pass. A's fixed-budget contrast combines any ranking benefit with extra serialization cost. Zero recovery in an infeasible condition does not isolate poor ranking. The report retains the primary full-denominator outcome and separately describes recovery conditional on authored-bundle feasibility.

The analyzer reconstructs exact packet bytes and digests, then counts text-only tokens with both pinned local tokenizers without truncation or special tokens. Those counts permit reproducible context comparisons; they are not Muse billable input usage. Full-collection and oracle controls intentionally bypass the small packet budget and are not resource-matched policies.

## Downstream reader and fresh discovery

Before examining retrieval outcomes, twelve held-out families per author are selected by ascending SHA-256 of `family_id + ':reader-20261011'`. Query 1 from each is used at 144 documents and 4,096 bytes. Four fixed arms yield 96 main trials: BM25 `000`, BM25 `111`, Mixedbread rerank `111`, and learned routing with rescue `111`. This tests four candidate systems, not every downstream A/B/C interaction. Each main trial has one completion; there is no best-of-many scored retry.

For the first six selected families per author, full collection and sufficient-original oracle controls add 24 trials. The oracle supplies the authored evidence bundle and is an evaluation diagnostic, never a deployable retriever. The full collection supplies all 144 records and measures a different context resource. Either control can show a reading failure despite adequate supplied evidence; neither establishes retrieval efficacy.

The same twelve diagnostic families also receive raw-filesystem and filesystem-with-retriever discovery trials, adding 24 trials. The total schedule is **144: 96 main, 24 diagnostic and 24 discovery**. Blocks remain separate in summaries and denominators. [Reader schedule](reader-schedule.json), [reader harness](run_readers.py)

Discovery starts with a shallow listing of five fictional PARA-style root folders and no personal-vault conventions. Records and workstream hubs are principally under `1-Projects`. The model receives a neutral task and external JSON `list`, `read`, `search` and `write` protocol. The helper arm additionally advertises `retrieve`, which accepts only the exact original query and returns the fixed Mixedbread `111` packet. Query reformulation, general semantic tool search, real vault onboarding and external cold state are outside this test.

The host caps discovery at four reader responses, sixteen actions and 16,384 returned bytes. It reserves 256 bytes for bounded control errors and stops after reserve exhaustion. Oversized whole observations are refused. Search supplies at most forty matching lines and can return partial evidence; read supplies a complete record. Delivered source IDs count toward the citation receipt proxy only after their observations have been replayed in a later reader prompt before the final write. A read and write in one action batch do not prove that the model received the new source first.

All reader arms use Muse `muse-spark-1.3-contributor` at high effort through fresh rootless local processes and ephemeral sessions, with no supplied prior-trial history, workspace or personal skills. The virtual hierarchy never exposes the native host filesystem. The adapter checks observed upstream user-text digests, disabled capabilities, pinned runtime hashes, `store:false` and absent continuation associations. A development Unicode preflight recovered `青灯 λ é —` and verified caller-to-upstream text equality, addressing the earlier pilot's encoding defect. Remote provider erasure, account-wide history and hidden system-prefix contents remain uncertified; local freshness is the observed control boundary.

The host actually writes accepted JSON to `artifacts/result.json` and executes a structural checker. A structural pass does not check source-derived truth. A development oracle rehearsal wrote the right numbers and sufficient sources but returned `close passed opaque cover` instead of authored `close opaque cover`; it failed exact matching and remains development-only. This illustrates the frozen metric's wording sensitivity before scored collection, without replacing it with an improvised semantic scorer.

## Outcomes and family-level analysis

The primary retrieval metric is complete recovery of at least one declared sufficient **original-evidence** bundle. Governing-ID coverage is secondary. Eligible, candidate and selected IDs distinguish metadata exclusion, initial candidate loss and packing loss; B can recover outside initial candidates. Derived-view inclusion, flagged views, missing references, skipped records, packet bytes, document counts and tokenizer counts are also retained. Coverage does not establish correct source use.

Primary reader success is **exact authored value-and-source task completion**: accepted controls and JSON, correct declared status and every expected answer value, sufficient valid original citations from actually supplied or replayed sources, an actual write, passing host structure, clean completion and zero forbidden virtual attempts. Extra answer fields and valid citations are allowed. Critical-field agreement is shown separately from all-field agreement. Exact comparison includes free-form wording and list order; a plausible paraphrase or reordered unresolved list can fail without proving semantic disagreement.

Citation normalization accepts a bare original ID or `ID:S<number>` and tests original-ID membership. The section suffix is not validated against actual sections. For discovery, a replayed search excerpt can establish the source-ID proxy even without a full record read. These are limited grounding measures, not comprehension proofs. A separately labeled blinded mismatch review can identify plausible semantic false negatives while retaining every frozen score; it must disclose review scope and does not become human adjudication or a replacement primary endpoint.

Missing responses, infrastructure failures, invalid actions, incomplete discovery and no-write trials remain failures in their scheduled denominators. Missing usage stays unknown rather than fabricated zero. Provider input, output and reasoning fields are retained separately; reasoning is not added to output in a derived total that assumes fields do not overlap.

Within each retrieval cell, the two queries are averaged per family and families receive equal weight. A/B/C main effects are paired on–off differences averaged over the other factors. AB, AC and BC are paired differences-in-differences; ABC is the difference of an interaction across the third factor. Joint `111` minus `000` and engine comparisons are separate contrasts. Budgets and collection sizes remain separate, as do development, held-out and author-specific results.

Uncertainty uses 2,000 deterministic whole-family bootstrap replicates with seed 1011 and descriptive 95% percentile intervals. Both queries and all paired conditions stay together under resampling; reader comparisons use one selected query per family. Feasible-subset recovery resamples family success and feasible counts jointly. These intervals describe variation within this non-random authored bank, without multiplicity correction, population inference or a causal-generalization claim. Repetitions of a timing workload are measurements of the same development cases, not new families. [Analysis implementation](analyze.py)

## Frozen execution, visual evidence and outstanding results

The prospective public freeze is commit [`eb1ecd575a2d6d1e3bf9e9907a2bd7e3abe52085`](https://github.com/BlueRaddish/filesystem-agent-memory-research/commit/eb1ecd575a2d6d1e3bf9e9907a2bd7e3abe52085). [freeze.json](freeze.json) pins the corpus, protocol, split, schedules, benchmark, reader schema, tokenizer/model manifests and public-safe private-runtime hashes. The freeze's original status records that no scored collection had occurred at its creation; it is an immutable prospective receipt, not a live progress field. No held-out outcome tunes budgets, candidate limits, branch count, expansion depth, version gates or selected reader arms.

The first tool-managed execution stopped with 576 persisted comparisons; its exact bytes remain in [interrupted-results.json](interrupted-results.json). The [execution amendment](EXECUTION-AMENDMENT.md) added durable per-query checkpoints and four collection workers, with original model and scoring settings. After observed host memory pressure, a separately pinned [resource amendment](RESOURCE-AMENDMENT.md) preserves all sixteen completed checkpoints (3,072 packets) and caps remaining collection at two workers. Complete output acceptance still requires exact reproduction of all 576 original rows. The latency block remains serial and uncached; mixed collection scheduling is execution provenance, not engine latency. Scored reader failures retain their denominator and receive no replacement completion.

Runnable self-checks cover corpus constraints, metadata traversal, budget integrity, reader control rejection, artifact validation, family aggregation, finite-difference scaling, bootstrap determinism and discovery replay distinctions. Analysis requires all 18,432 scheduled packets, 4,608 rankings, 144 uncached timing observations and all 144 scheduled reader outcomes, with missing/duplicate conditions rejected. It rechecks frozen hashes and exact packet reconstruction. Post-collection corrections must be versioned amendments or labeled sensitivity analyses, never silent changes to the primary.

The final visual set will present factorial recovery, atomic effects and interactions, paired engine changes, evidence-loss stages, stratum and author heterogeneity, context/computation frontiers, downstream gates, controls and discovery/replay outcomes. Scientific PNG figures and matching SVGs will accompany the machine-readable analysis. These visuals must show the unit, resource condition and metric rather than implying independent evidence from thousands of repeated cells.

**Pending:** complete scored results, analysis validation, figure receipts, mismatch-review findings and a recommendation conditional on those observations. This draft establishes the protocol and its limits; it makes no engine ranking or production-adoption claim.
