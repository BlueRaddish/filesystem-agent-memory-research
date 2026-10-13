# Research beyond a retrieval leaderboard

**Primary-source extension accessed October13,2026; the new local comparisons are specified in [PLAN.md](PLAN.md).** Literature findings below are the authors' results on their own workloads. They are neither reproduced results nor expected accuracy for this project. The [index](INDEX-RESEARCH.md) and [packing](PACKING-RESEARCH.md) reports document their own source records and implemented mechanisms. Historical catalogs remain separately versioned.

The useful question is broader than whether one folder tree makes search easier. A memory system must retain recoverable originals, locate the right evidence, assemble sufficient context, apply it correctly, finish a task, and repair subsequent state when an earlier memory was wrong. Different representations can improve one step while worsening another. A terse summary may be easy to find but omit an exception; a graph may expose a dependency but omit its decisive edge; a very accurate ranker may still lose the evidence during packing. Tests should identify the failing step before prescribing a vault migration.

## Recent work that changes the experimental agenda

**LongMemEval-V2 is particularly relevant to unfamiliar environments.** Its official release tests manually curated questions over multimodal web/enterprise trajectories, including workflow knowledge, local gotchas and invalid premises. Its evidence-return and query-latency setup is closer to an experienced colleague than conversational fact recall alone. A text-only adaptation would omit screenshots and would not reproduce the full benchmark. This motivates testing operational knowledge and rejecting a false premise, separately from retrieving a date. It also supplies an externally authored transfer lane; its code and dataset card declare Apache2.0. [Official repository](https://github.com/xiaowu0162/LongMemEval-V2), [paper](https://arxiv.org/html/2605.12493v1), [dataset](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2)

**Infini Memory provides a concrete document-maintenance alternative.** It stores topic documents, buffers new observations and consolidates/splits/merges them; reading can iteratively inspect evidence. Its reported ablation distinguishes summary selection, lexical evidence retrieval and agentic follow-up, rather than attributing their combined gain to folders alone. This motivates separate comparisons for document organization, evidence selection and additional reading. Our current packers do not reproduce its LLM consolidation or full agentic system, and source retention remains a separate requirement. [Paper and ablations](https://arxiv.org/html/2606.10677v1)

**Mem2ActBench shifts evaluation toward action parameters.** It evaluates whether remembered constraints drive tool selection and parameter grounding, rather than whether a model can repeat a fact. Its synthesized memory chains and human memory-dependence check have different sampling assumptions from this fictional bank. The released README declares MIT, while the root license file was unavailable during this review; upstream component datasets need their own licensing checks. The useful next comparison is a simulated action with memory-conditioned parameters and an executable check, without sending real external actions. [ACL paper](https://aclanthology.org/2026.acl-long.370/), [official release](https://github.com/Cantaloupe-M/Mem2ActBench)

**BEAM broadens both history length and memory abilities.** It uses long generated conversations, validated probing questions and ability-specific evaluation; most answers are scored by atomic rubric nuggets, while event ordering uses a separate alignment/order metric. LIGHT combines episodic history, working memory and a scratchpad. This motivates measuring global synthesis and sequence preservation alongside local fact recovery. Context-length tiers reuse underlying structures and cannot become independent cases by pooling them. The official repository distinguishes MIT code from CC BY-SA4.0 data. [Paper](https://arxiv.org/html/2510.27246v2), [official repository](https://github.com/mohammadtavakoli78/BEAM)

**MemoryAgentBench emphasizes incremental information and updates.** Its multiple competencies include retrieval, test-time learning, long-range understanding and selective forgetting. In its conflict-consolidation setting, later serial-numbered facts are explicitly declared to take priority. That authority policy is valid for that fixture; importing it into arbitrary files as “newest always wins” would change the task. Our stress cases therefore distinguish author/import date, applicability and explicit supersession. The benchmark's repeated queries share ingest histories, so uncertainty should respect those clusters. [Paper and prompt-policy appendix](https://arxiv.org/html/2507.05257v3)

**REMem suggests complementary episodic and factual cues.** Its time-aware graph connects gists and facts, and its ablations distinguish lexical/semantic retrieval and graph components. Different metrics respond differently to an ablation; a small judge-score change need not mean unchanged exact factual recovery. We translate this into separately testable cue, local semantic and explicit-link policies. We do not reproduce learned gist extraction or automatically inferred synonym edges. [Paper and ablations](https://arxiv.org/html/2602.13530v1)

**LightMem makes maintenance scheduling an explicit design choice.** Its stages filter and consolidate observations and perform offline updates. This suggests measuring ingest/build/update costs separately from online retrieval latency. “Sleep” here is a software scheduling metaphor; it is not evidence that a fixed language model receives human memory consolidation. Its update-time assumptions and compression settings need to be preserved when interpreting reported efficiency. Our cached indexes test preprocessing reuse, not the paper's complete consolidation pipeline. [Paper](https://arxiv.org/html/2510.18866v1)

**Dependency-guided rollback treats downstream state as part of memory repair.** A recent controlled study tracks claims, support and steps to invalidate or replay. Its ablations show preservation, recovery and replay cost can trade off; maximizing answer recovery alone can damage benign state. It supplies diagnosed faulty-memory identifiers to compared methods and reports single-run outcomes; an adapted trajectory stress test is not full benchmark reproduction. This motivates testing transitive invalidation and original-preserving repair alongside retrieval. Our engineered cache/write traces check prescribed mechanics, not automatic fault diagnosis or reproduction of that paper's recovery rates. [Paper and ablations](https://arxiv.org/html/2608.10502v1)

## A wider hypothesis portfolio

The following statements are deliberately smaller than “replace PARA with systemX.” Some are implemented in the new grid; others remain separate research candidates. Bundled methods cannot identify every component's causal effect without their own ablations.

|Hypothesis|Concrete test|Status in this round|
|---|---|---|
|Search cues help without costing context space|Same packing, body versus search-metadata ranking|Implemented ranking contrast|
|Character cues recover spelling/alias variants|Word, character and fixed fusion, with near-match failures retained|Implemented|
|Exact identifiers need a separate channel|ID-aware fusion versus ordinary lexical scoring|Implemented heuristic, not entity linking|
|Several query clauses need complementary evidence|Clause fusion versus a single query rank|Implemented|
|Local semantic matching avoids long-record dilution|Sentence lexical MaxSim and dense window MaxSim versus whole text|Implemented|
|Small rerankers benefit from source passages|Same lexical top32, whole versus neighbor-window MiniLM scoring|Implemented; compute counts differ|
|A larger scoring policy is not automatically useful|MiniLM versus Mixedbread with matched packer/candidate scope|Implemented checkpoint-policy comparison; training/tokenizer/quantization also differ|
|Tiny learned rules can prune cheaply|Depth-three development-only tree versus nonlearned policies|Implemented; transfer needs held mechanism tests|
|Diversity can help or remove corroborating authority|MMR/coverage variants and explicitly repeated correction evidence|Implemented bundled comparisons|
|Dependency closure recovers low-similarity prerequisites|Expansion on/off at matched bytes, plus missing-edge counterexamples|Implemented|
|Conflict pairs should stay together|Connected supersession components versus ordinary passages|Implemented; large groups may be skipped|
|Source identity is insufficient for passage coverage|Compare complete declared spans with selected/source-ID proxies|Implemented primary measurement|
|A root entrypoint helps unfamiliar agents|Root README×general retrieval helper factorial|Scheduled fresh-reader comparison|
|Completion feedback prevents endless navigation|Visible remaining budgets and real write/check receipts|Fixed harness feature, not independently ablated|
|Transitive caches avoid stale nested views|Direct versus closure invalidation over prescribed events|Engineered replay|
|Version hashes cannot verify generated facts|Correct source ledger and view checksum with wrong prose|Engineered counterexample; semantic check remains separate|
|Task obligations differ from remembered facts|Implicit action prompts with field-level source grounding|External transfer/future experiment|
|A context-sufficiency sentinel can decide when to search again|Reader marks unresolved required fields before final write|Future matched policy, with conservative-hold costs|
|Query-specific context order helps reasoning|Same exact evidence ordered by chronology, authority or dependency|Future fixed-evidence experiment|
|An obligation manifest prevents missed background requirements|Source-linked rule/exception index versus relevance-only search|Future; authoring/maintenance costs must be measured|
|Multiple competing representations need cross-checks|Recover raw episodes and current projections separately|Future field-verification experiment|
|Non-destructive consolidation supports both detail and reuse|Generated current views plus recoverable originals versus lossy replacement|Future ingest/maintenance experiment|
|Adaptive closure should stop when required support is covered|Fixed expansion versus explicit requirement-guided expansion|Future; inferred requirements may be wrong|
|A native persistent index could outperform repeated scans|SQLiteFTS5/standard search with cold/build/warm accounting|Future engineering comparison, no speed claim|
|Action rollback needs source dependency provenance|Wrong memory followed by dependent steps and selective replay|Future model-mediated repair; mechanical subset implemented|
|Spatial/visual navigation may change human usability|Same sources presented as tree, graph and structured list|Future human/agent modality study|

This portfolio is broader than selecting a folder naming convention, but each hypothesis still points to a falsifiable matched comparison. A larger experimental menu raises the chance of finding a useful mechanism and the chance of finding an accidental maximum. We therefore keep every scheduled result, retain regressions, separate development from held mechanisms, and avoid promoting the largest observed number to a universal winner.

## Biological and human ideas: careful translations

The earlier [biological-memory review](../../research/biological-memory.md), [human-practice review](../../research/human-memory-practices.md) and [transfer analysis](../../research/brain-agent-transfer.md) retain their evidence/source boundaries. Three useful translations remain hypotheses about external systems:

1. **Separate distinctive episodes from reusable structure.** Preserve exact originals and maintain independently checkable current/semantic views. A consolidation job can update external files and indexes; simply rerunning a query does not train a fixed model's weights.
2. **Test discrimination, not just similarity.** Near-identical projects, aliases, scopes and dates require finding why two records differ. Character matching, explicit scope, source lineage and counterexample cases operationalize this idea without asserting they implement hippocampal pattern separation.
3. **Make future obligations retrievable before action.** A useful assistant needs applicable constraints and local gotchas even when the user does not ask for a memory fact. Workflow/action benchmarks and requirement manifests are closer to that problem than a memory quiz.

Forgetting in human systems does not justify deleting a source or silently overwriting contradictory evidence. A computational system can preserve old episodes cheaply while making eligibility, uncertainty and current authority explicit. Conversely, preserving every byte does not guarantee that the reader notices or uses it. Retention, retrieval, reasoning and execution need their own evidence.

## Practical interpretation

The current architecture worth investigating is a canonical source store with versioned, replaceable indexes and projections; inexpensive global candidate search; targeted local scoring where it earns its cost; recoverable source-linked evidence assembly; and a clear unfamiliar-agent path to verified completion. This is an experimental architecture, not a production migration recommendation.

Several attractive alternatives remain unevaluated here: neural sparse models, late-interaction indexes, full automatic graph extraction, LLM consolidation, whole-history multimodal trajectories, human usability and actual external tool actions. Their literature/source/implementation costs are recorded instead of being credited to the local methods. The [prospective plan](PLAN.md), bank audit, execution census, timing receipts and final report will distinguish what was proposed, implemented, executed and independently checked.
