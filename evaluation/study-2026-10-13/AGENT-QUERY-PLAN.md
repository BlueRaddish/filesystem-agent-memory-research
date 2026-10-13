# Development-only fresh query cues — prospective protocol

This supplement tests whether one fresh model call per task can improve source-exact evidence coverage when used only to propose retrieval cues. It is separate from the frozen main experiment, does not choose its winner, and makes no confirmation or answer-quality claim. No main result, confirmation gold, or full challenge bank is opened by this lane.

The only bank input is the private development excerpt: SHA-256 `a4b7f77cf2311e1c2cd742df9996ddd5d5b7542b9a0a20f3eb305621f9f9a8fa`, derived from bank SHA-256 `280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760`. All 24 development histories, 72 tasks and 276 records are retained. Generation receives only each task's original query, inside the fixed instruction below. Retrieval receives observable documents and query strings. Evidence sets and exact spans are used only after retrieval/packing for evaluation; expected answers, rationales, answer contracts and answer keys are never projected into either interface.

Before calls or scores, `prepare` writes a private frozen manifest with exact source, task/query projection, document projection, prompt, code, library, transport, runtime and command hashes; fixed schedule and counts; and environment metadata. A review clearance must match its SHA-256. Changes require a new reviewed manifest before outcomes. The manifest and clearance are not public artifacts.

## Fixed generation

Schedule 72 calls, one per task in task-ID order, with at most two network workers. Use the existing verified Muse transport, model `muse-spark-1.3-contributor`, reasoning effort `high`, the current authorized login, and a 300-second call timeout. Do not change the adapter, model or settings. No native filesystem, web, shell, artifact, messaging or provider tools are allowed; session-local bookkeeping is the existing adapter's only advertised native capability. Existing same-call controls must verify freshness, native inventory, UTF-8 and exact upstream prompt text against runtime hashes. Retain control failures as failures.

Fixed prompt prefix (the task query is then supplied as one JSON string):

```text
You propose search queries for a fictional read-only evidence collection.
You see only the task text. Do not answer the task or assert any factual result.
Return exactly one JSON object with one key: "queries".
Its value is an array of zero to three alternative retrieval queries or explicit
conditional subquestions that could find evidence needed for this task.
Preserve named workstreams, scope, dates, exceptions and conditions where useful.
Do not invent record IDs, documents, facts, values, decisions or evidence.
Do not repeat the original task query. Each query must be a nonempty string
of at most 512 UTF-8 bytes. If no useful alternative exists, return {"queries":[]}.
No markdown, commentary, answers or extra keys. Use no tools.
Task query (JSON string):
```

Reject fenced/prose output, duplicate JSON keys, non-finite constants, extra keys, non-string/empty/duplicate cues, original-query duplicates, more than three cues, cues over 512 UTF-8 bytes, total output over 4096 UTF-8 bytes, unencodable text, and source-format IDs (`Nddd-Rddd`) absent from the original query. Whitespace is trimmed; uniqueness uses casefolded trimmed strings. An empty list is an unusable generation. These structural checks do not prove that every cue is free of an implicit factual assumption.

Every failed, interrupted, rejected, empty or otherwise unusable generation is retained, with the original query as explicit fallback. No retries, corrective prompts or hand edits. A pending call lacking a receipt is never reissued. Returned call receipts and derived generation checkpoints are atomically flushed and fsynced immediately; actual prompt/output and call traces remain private. Resume must be explicit and must verify all frozen fingerprints. On checkpoint reuse, evaluation and aggregation, retained receipt hashes or genuine unknown-pending provenance are checked, and saved cues/failure/fallback are compared with the fixed validation re-applied to retained raw output.

## Fixed retrieval and packing

Compare three policies: `original_query`; `deterministic_clause_cues` (original plus the first three unique non-original clauses from the existing `clauses_for` splitter, in its fixed order); and `generated_cues` (original plus up to three accepted generated cues, or original-only fallback). The original query is always the first channel. Each cue independently ranks all 276 documents with `body_bm25` or `entity_rrf`. Fuse complete rankings with equal-weight reciprocal rank fusion, constant 60, with document-ID tie breaking. One channel retains the original ranking exactly. No answer-dependent expansion, rescue retrieval, cap circling, re-retrieval, learned ranker, reranker, local ONNX or adaptive tuning.

Prepare one shared lexical index, including the character channel required by `entity_rrf`. Cache each cue/retriever ranking with provenance. Take top 32 fused IDs, then pack using the unchanged `whole_record` or `closure_passages` packer at 4096, 8192 or 16384 UTF-8 bytes. Packing always receives the original task query, so only ranking changes between policies. The full fixed grid is 72 × 3 policies × 2 retrievers × 2 packers × 3 budgets = 2592 packets. Every source observation must reproduce the unchanged body's exact character range and hash, and every packet must meet its byte cap. A shared validator checks new packets, reused checkpoints and final aggregate inputs against canonical packet pieces and recomputed primary/secondary scores. Cached fusion rankings must remain full, unique document permutations before packing or aggregation.

## Outcomes and cost

Primary: count of packets recovering at least one declared exact-span evidence bundle (`support_metrics`). Secondary: best declared span fraction, selected original-ID evidence bundle, whole-source bundle, and top-32 candidate original-ID evidence bundle. Summarize all scheduled workflows, including fallback, and separately the same matched tasks conditional on usable generation. Report paired task counts of improvement, regression and tie against `original_query` within every fixed retriever/packer/budget cell. Do not claim inferential significance or select a winner from these development outcomes.

Report generation stage wall time, sum and distribution of the transport's host-measured call elapsed time and the optional numeric elapsed field reported in the adapter control receipt as separately named summaries with missing counts, returned/accepted/usable/failure counts, and each numeric usage field retained by the frozen transport by its exact name, field-specific reported/missing count and sum. The control-receipt field's timing semantics are not independently established as provider-server time. Neither elapsed field is relabeled as the other or added to the other. Returned-call counts come from persisted call-receipt provenance, separately from accepted calls and interrupted calls with an unknown pending receipt. The transport retains only matching, finite nonnegative numeric fields from accepted envelopes; usage from rejected envelopes and other names is unavailable to this lane. Provider counter semantics and overlap remain ambiguous; no grand total across counter names, fabricated token conversion, price estimate or inferred zero for missing usage. Lexical index preparation, newly computed cached cue ranking, policy fusion and packing times are recorded separately. Concurrent workloads and cache order prevent causal hardware-speed claims. Per-call, per-ranking and per-packet checkpoints use atomic replacement plus flush/fsync, and interrupted stages require explicit resume.

The no-retry rule applies to generation calls. A local indexing, ranking, packing or persistence exception stops evaluation with earlier checkpoints retained; it does not create a failed per-packet denominator row. Explicit evaluation resume may recompute a missing deterministic local step after fingerprint verification. Public aggregation requires the completed 2592-packet grid; an incomplete stage is disclosed as incomplete and is not silently replaced with partial complete-grid results.

## Adjacent primary research

[Query2doc](https://aclanthology.org/2023.emnlp-main.585/) generates pseudo-documents and expands queries; this experiment generates bounded query strings, not pseudo-documents, and does not reproduce its full method. [HyDE](https://aclanthology.org/2023.acl-long.99/) generates hypothetical documents and encodes them for dense retrieval; this experiment has no dense encoder and does not implement HyDE. [RQ-RAG](https://arxiv.org/abs/2404.00610) learns query rewriting, decomposition and disambiguation in a retrieval-augmented system; this experiment does not train a model or reproduce that system. These papers motivate the adjacent design space, not a claim of method equivalence or transferred benchmark performance.

The public deliverables are this protocol, runnable stdlib-only code, a safe aggregate JSON and a report with primary-source links. Public files exclude task text, generated cues, source packets, expected answers, absolute private paths, provider handles and native authentication logs. The frozen main experiment and its analysis specification remain unchanged.
