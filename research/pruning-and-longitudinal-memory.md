# Pruning and retrieval as memory grows

Pruning is worth testing as a policy for controlling what competes for attention. **An old or rarely opened file is not necessarily a dead branch.** It can contain a standing constraint, the reason a decision changed, or evidence needed when a dormant project returns. The initial candidate is therefore reversible demotion with explicit recovery, compared against unrestricted retrieval and destructive controls. This is a research direction, not a recommendation to delete a live memory vault.

## Scope and source status

This structured scoping extension reviews **18 source records**, accessed on **2026-10-16 UTC** (October 15 Pacific): cache research, storage-system documentation, agent-memory research, a human file-management study and cognitive work. These records are not 18 newly discovered or independent experiments. MemoryBank, MemoryAgentBench and GrayArea revisit work in earlier catalogs; a newer inspected version or a different research question does not make a new study. One RocksDB record groups two related official documents. The [catalog](../sources/pruning-longitudinal-memory.json) gives URLs, publication/version status, review depth and limitations. Fifteen records received selected full-text or documentation-section inspection; GrayArea and the two cognitive records received primary abstract/metadata inspection. Full-text access attempts for the cognitive papers failed. No paper's code or results were reproduced here.

Searches targeted cache admission and replacement, compaction and tombstones, agent forgetting and consolidation, incremental memory evaluation, and reversible file demotion. Selection was mechanism-driven, not exhaustive or preregistered. Recent preprints remain preprints. Documentation establishes a system's stated behavior, not an agent accuracy result. The review proposes experiments; it reports **no new benchmark outcomes**.

## Five operations that should not share one score

| Operation | What changes | What must be measured separately |
| --- | --- | --- |
| Physical deletion | The source bytes are removed from the specified retained stores | Irrecoverable evidence loss, remaining copies and deletion scope |
| Active-index pruning | Sources survive, but leave ordinary candidate retrieval | Hot-path exposure, fallback recall and recovery cost |
| Cold archiving | Sources survive in a less prominent or slower tier, with a recovery route | Reactivation success, access delay and total retained storage |
| Summary compaction | A shorter representation substitutes for some source content | Lost qualifiers, source expandability and cumulative rewrite drift |
| Navigation pruning | Hubs, links or visible branches are reduced | Fresh-reader discoverability, dangling links and orphaned evidence |

Moving a folder to an archive has no retrieval effect if the same search still indexes everything equally. Removing a vector from one index is not source deletion. A summary can reduce prompt bytes while leaving total storage unchanged. Report the actual operation, affected tier and recovery contract.

## Cache research: admission, replacement and workload change

ARC separates recently seen and repeatedly seen pages and uses metadata about evicted pages to adjust their balance. Its equal-page demand-paging evaluation supplies a mechanism for remembering that a cold item was wanted again. It does not show that a frequently accessed document is authoritative or sufficient. [PL01](https://www.usenix.org/legacy/events/fast03/tech/full_papers/megiddo/megiddo.pdf)

TinyLFU makes **admission** a separate decision: a newly requested item competes with an eviction candidate using an approximate recent-frequency history. Counter resets age that history; W-TinyLFU adds a recency window. This motivates a probationary active tier and adaptive counts, rather than admitting every new note permanently. LRU and LFU remain useful simple controls. [PL02](https://arxiv.org/pdf/1512.00727v2)

SIEVE uses a queue, access bit and moving eviction hand; hits do not reorder the queue. The paper studies web/object-cache efficiency and implementation scalability. Its transferable experiment is lazy bookkeeping versus eager reordering, with one-hit scans explicitly represented. It supplies no evidence about preserving rare project exceptions. [PL03](https://www.usenix.org/system/files/nsdi24-zhang-yazhuo.pdf)

A September 2026 prefix-cache preprint is a useful counterexample to importing a cache winner: its traced session pacing makes recency unusually predictive, while miss costs and session sizes vary. KV-prefix reuse preserves computation for already specified prompts; semantic-memory retrieval chooses evidence for a new problem. Neither task's hit rate establishes the other's answer quality. [PL04](https://arxiv.org/html/2609.28870v1)

**Engineering inference.** Compare LRU, frequency with aging, and simple admission under several streams. Define an access event carefully: candidate ranking, opening a file, citing it, and verified contribution to a correct answer are different signals. Counting automatically generated maintenance reads can create an artificial popularity loop. Include the metadata and maintenance costs of the policy itself, not just the active source bytes.

## Storage systems: what can be discarded without breaking reconstruction?

Kafka's keyed log compaction retains a final state per key; retaining every intermediate event is a different contract. Its documentation also explains that lagging consumers can miss deletion markers after their retention window. A current-state projection can therefore be compact while an explanation or historical reconstruction still needs older events. Correct keys and update semantics are prerequisites. [PL05](https://kafka.apache.org/41/design/design/)

Cassandra documents tombstones and the conditions for purging them; a replica that misses a deletion can otherwise resurrect old data. This motivates retaining enough deletion/supersession metadata to prevent re-ingest from silently reviving a suppressed memory. It does not prescribe Cassandra's grace interval for an agent filesystem. [PL06](https://cassandra.apache.org/doc/stable/cassandra/managing/operating/compaction/overview.html)

RocksDB's DeleteRange design separates making keys invisible from reclaiming their physical space. Its discussion covers snapshots, older versions, compaction and read costs. Its official compaction-filter documentation gives a concrete failure case: `kRemoveAndSkipUntil` skips keys without deletion markers, allowing older versions to reappear; it also documents snapshot-repeatability exceptions. These are software-specific boundaries, not agent-memory results. An agent-memory benchmark should distinguish a logically hidden note, a removed index entry, a retained snapshot and reclaimed bytes. [PL07](https://rocksdb.org/blog/2018/11/21/delete-range.html), [compaction-filter documentation](https://github.com/facebook/rocksdb/wiki/Compaction-Filter)

Git garbage collection treats reachability from references, the index and reflogs as retention roots and documents concurrency hazards. This suggests a **dependency-aware** pruning control: keep evidence reachable from current obligations or retained historical claims. A broken or incomplete dependency graph can still misclassify valuable records as unreachable. No garbage-collection command is proposed for the live vault here. [PL08](https://git-scm.com/docs/git-gc)

**Engineering inference.** A source record, a current-state projection and a navigation link need stable identities and distinct lifecycles. A current preference update can supersede an old value without invalidating the old event as historical evidence. Deletion, retraction and supersession should be explicit different operations. Test a restart or index rebuild after pruning; otherwise apparent success can disappear when old files are scanned again.

## Agent-memory work: decay, consolidation and changing facts

MemoryBank offers time-and-recall reinforcement as an optional anthropomorphic forgetting mechanism alongside conversation records and hierarchical summaries. Its companion setting and simulated-dialogue probes do not establish an optimal decay constant, rare-constraint protection or sustained project continuity. Its human-inspired formula is a candidate policy, not a biological necessity for durable files. [PL09](https://arxiv.org/html/2305.10250v3)

MemoryAgentBench incrementally feeds chunks and includes FactConsolidation, which orders counterfactual edits and asks for the final state. This is valuable for testing stale-fact use. The supplied overwrite instruction and constructed edits simplify authority; later text in a real project may be a proposal or an unauthorized assertion. This review inspected v4 as well as the earlier method description. [PL10](https://arxiv.org/html/2507.05257v4)

Memora generates sessions from explicit evolving memory traces and separates valid-information presence from invalid-information absence in its FAMA evaluation. Weekly-to-quarterly simulations and repeated mutations motivate measuring a trajectory rather than only a final snapshot. Simulated personas, generated dialogue and judge-based criteria bound the evidence; its calendar labels are not observed months of deployment. [PL11](https://arxiv.org/html/2604.20006v1)

Useful Memories Become Faulty When Continuously Updated by LLMs compares episodic and abstract stores, update schedules and retain/delete/consolidate controls. It reports deterioration under repeated textual abstraction in its tested tasks. This motivates preserving expandable episodes and repeatedly retesting earlier tasks. It does not establish that all consolidation fails or that unbounded raw retention is optimal. [PL12](https://arxiv.org/html/2605.12978v1)

Deployment-Time Memorization tests synthetic canaries and deletion modes across raw and summary tiers on 50 sampled LongMemEval-oracle instances. Raw-only scrubbing can leave derived copies recoverable in that setup. Its utility proxy and bounded probes do not certify complete erasure. Retrieval optimization by archiving and a request to erase information have different success criteria. [PL13](https://arxiv.org/html/2606.10062v1)

FSFM proposes decay, active deletion and safety-triggered forgetting. Its reported comparison places one system under a capacity cap and the baseline under unlimited retention; its tables also report loss of important records. Those conditions do not isolate a universal pruning benefit. Its labeled-content removal result must not be read as proof that every security risk is eliminated. [PL14](https://arxiv.org/html/2604.20300v1)

Learning What to Remember distinguishes future-query-aware scoring from query-blind retention. It learns factor weights using gold-evidence retention and explicitly leaves downstream QA untested; only four of seven proposed factors are active in its API-free setting. Its strongest methodological lesson is to hide future probes when pruning. The fitted weights are workload-specific candidates. [PL15](https://arxiv.org/html/2606.12945v2)

## Human demotion and adaptive forgetting: useful analogies with limits

GrayArea evaluates demoting files within their folder context as an intermediate option between keeping and deleting. Its primary abstract reports a folder-cleaning study, not agent retrieval or long-term reactivation. It supports testing a visible, reversible inactive region; it does not show that hiding files preserves every important fact. [PL16](https://www.microsoft.com/en-us/research/publication/its-not-that-important-demoting-personal-information-of-low-subjective-importance-using-grayarea/)

Anderson and Schooler's abstract relates the probability of future need in examined environments to frequency, recency and exposure patterns, offering an adaptive account of human memory. Richards and Frankland's perspective argues that transience can support flexibility and generalization. These are reasons to test changing demand and interference, not evidence for a universal time-to-live or deletion rule for files. Only their primary abstracts were accessible in this review. [PL17](https://journals.sagepub.com/doi/abs/10.1111/j.1467-9280.1991.tb00174.x), [PL18](https://pubmed.ncbi.nlm.nih.gov/28641107/)

## Atomic hypotheses for extended-use experiments

The following are **proposed, falsifiable statements**. Each needs a defined corpus, capacity, retrieval budget, history and reader. Gains in one endpoint do not substitute for failures in another.

| ID | Change one mechanism | Predicted benefit to test | Counterexample or falsifier |
| --- | --- | --- | --- |
| P1 | Demote by inactivity, retain cold sources | Fewer irrelevant active candidates at equal hot-path budget | Dormant-project evidence becomes unreachable or recovery outweighs saved work |
| P2 | Add cold fallback to the same active policy | Recover evidence missing from the hot tier | Trigger fails on a plausible but incomplete hot answer |
| P3 | Add admission before replacement | Resist one-pass ingestion or scan pollution | New important constraints wait too long for promotion |
| P4 | Age frequency counts, keep all other rules fixed | Recover faster after a hotspot shift | Repeated long gaps cause useful stable sources to be discarded |
| P5 | Pin currently declared obligations and their dependencies | Preserve rarely used governing evidence | Pins consume the active budget or incomplete links omit prerequisites |
| P6 | Gate current-state use by explicit supersession | Reduce obsolete-value use | A historical question needs an older version or an update lacks authority |
| P7 | Keep source expansion beside summaries | Recover details omitted during compaction | Reader trusts the summary and never requests expansion |
| P8 | Compact navigation independently from sources | Reduce fresh-reader search effort | A removed hub edge isolates a still useful branch |
| P9 | Rebuild retrieval after pruning from the declared retained state | Preserve the intended pruning/deletion contract | Suppressed sources reappear or tombstones are lost |
| P10 | Use dependency-aware eligibility before age-based demotion | Preserve evidence needed by retained claims | Incorrect roots or links make irrelevant history permanently live |

A deletion arm and a demotion arm must start with the same retained candidates and selection scores; changing those simultaneously confounds selection with reversibility. A summary-only arm and a source-linked summary arm should share the same summaries. An oracle with future queries can diagnose an upper bound but must remain evaluator-only.

## What an extended-use test must expose

Use a chronological stream: ingest documents and corrections, perform maintenance using only the past, then issue the next probe. Preserve a held-out future schedule. Include growth without fact changes, repeated updates to the same facts, near-duplicate accumulation, changed vocabulary, renamed projects, cross-project dependencies and a dormant topic returning after a long gap. Vary one-hit scan traffic and workload shifts separately from growth. An old-but-valid constraint and an obsolete value should not be treated as the same kind of old record.

Evaluate at several checkpoints and immediately before/after pruning, then after reactivation and restart. Track **material evidence retained**, **material evidence exposed to the reader**, **correct current or historical interpretation**, **unsupported or stale use**, and **task completion** separately. Include queries requiring a complete bundle and a rare exception, not only single-record hits. A smaller active corpus can improve precision while damaging completeness.

Record source, active-index, cold-index, summary, metadata, tombstone and checkpoint bytes separately. Count ingest/maintenance work, documents scanned, bytes opened, retrieval calls and recovery cost. Measure wall time only under a stated implementation and timing protocol; deterministic operation counts are not latency observations. Report peak maintenance space as well as final size.

Compare both equal active capacity/retrieval budgets and capacity allowed to grow toward an accuracy target. Include retain-all with the same reader budget, a capable search-all baseline and explicit irreversible controls. Otherwise apparent pruning gains can come from handicapping unrestricted retrieval or giving the pruned system extra fallback reads. A hot-only hit and a cold recovery have different costs.

Repeat across independently authored stream families and multiple growth trajectories. Seeded variants of one rule template do not become independent real-world histories. Cluster uncertainty by history or mechanism family, report every checkpoint and failure class, and reserve untouched future trajectories for confirmation. A fresh agent should receive only the documented memory entry point and task, with no evaluator labels or prior navigation knowledge. Successful deterministic replay alone cannot establish that an unfamiliar model will discover the same evidence.

## Candidate direction, pending measurements

The strongest starting architecture to test is **source retention plus a bounded active view, explicit current-state semantics and recoverable cold search**. It protects the distinction between reducing competition and destroying evidence. The policy still needs to earn its complexity: fallback can be slow, summaries can omit exceptions, dependency pins can bloat and never-used files can still matter later. The experiment should identify where each policy stops working, rather than select one universal retention horizon for PARA.
