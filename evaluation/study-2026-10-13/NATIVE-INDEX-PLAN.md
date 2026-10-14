# Development-only SQLite FTS5 — prospective protocol

This independent supplement tests a native SQLite retrieval avenue. It does not alter the frozen core or existing supplements, select a main winner, or make a confirmation claim. No provider/model calls, dependency installation, production index change, main outcomes or confirmation data are allowed.

The only source bank is the private development excerpt, SHA-256 `a4b7f77cf2311e1c2cd742df9996ddd5d5b7542b9a0a20f3eb305621f9f9a8fa`, derived from bank SHA-256 `280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760`. Retain 24 development histories, 72 tasks and all 276 records. Retrieval uses only observable document fields and original query text. Evaluation alone receives declared evidence sets/spans; expected answers, rationales and answer contracts/keys are never projected into retrieval.

Before any development score, pin this plan, code, official-source catalog, frozen shared libraries, source/document/query projections, Python/native SQLite fingerprints, tokenizer configuration, schedule and fixed timing protocol in a private manifest. Root's reviewer clearance must match that manifest hash. Prospective self-checks use fictional fixtures, not development retrieval outcomes.

## Six fixed engines

Four native policies cross two contentful FTS5 views with two literal predicates: `fts_body_or`, `fts_body_and`, `fts_search_or`, `fts_search_and`. The body view indexes unchanged body text. The search view indexes the same concatenation used by the frozen lexical search surface: title, scope, aliases and body, separated by newlines. Source ID and canonical revision are stored as UNINDEXED fields. An ordinary source ledger enforces unique IDs. Building, updating or deleting a source changes that ledger and both FTS views in one explicit transaction; update/deletion occurs only in the fictional self-check, not the experiment corpus.

Use `unicode61 remove_diacritics 2`, default character categories, no stemming, prefix expansion, synonyms or stopword removal. Extract query terms through a separate in-memory FTS5 table and its `fts5vocab(instance)` view, in token-offset order, then deduplicate terms by first occurrence. Quote every term with double quotes, doubling embedded quote characters, and join only with the selected fixed OR or AND. Bind the completed MATCH value as a SQL parameter. Original punctuation/operators are data, not caller-controlled SQL/MATCH syntax. An empty token list yields zero hits.

Native ranking returns only genuine MATCH hits, ordered by ascending SQLite `bm25()` and binary source-ID tie breaking. Keep the first 32 IDs; do not append nonmatching IDs or fabricate scores. SQLite's smaller-is-better score convention and native tokenization differ from the references. The frozen `body_bm25` and `search_bm25` implementations are the other two engines, retained unchanged; these references rank every document and do not share the native MATCH hit predicate. No algorithm equivalence is claimed.

The fixed schedule is task-ID order, then the above four native engines followed by the two references. No routing, cue expansion, adaptive query rescue, repeated cap retrieval, neural model or policy tuning.

## Packing, outcomes and failures

Use unchanged `whole_record` and `closure_passages` packers at 4096, 8192 and 16384 UTF-8 bytes. Packing always uses the original task query and at most 32 retrieved candidates. Total: 72 × 6 engines × 2 packers × 3 budgets = 2592 scheduled packets. New/reused/final aggregate packet checkpoints must meet exact source text/range/hash, canonical wrapper, byte-cap and recomputed-score checks.

Primary: recovery of at least one declared exact-span bundle. Secondary: best declared span fraction, selected original-ID bundle, whole-source bundle and candidate top-32 original-ID bundle. Report every scheduled denominator, zero-hit query/packet count, ranking fault, packing fault and failure phase/class. Native zero hits pack an empty genuine candidate list and score zero coverage. A ranking or packing fault is an explicitly failed workflow with no fabricated packet/ranking and zero successful-workflow recovery; preserve it in the scheduled denominator. Separate fault-free counts/rates are diagnostic, and zero hits remain in those denominators.

One durable checkpoint per ranking and packet uses atomic replacement, flush and fsync. A pending interrupted step is retained as an explicit unknown-result fault when resumed, rather than silently retried. Resuming a stage requires explicit verified `--resume`. Fault checkpoints are never retried. A persistence failure that prevents saving any checkpoint stops an incomplete stage with prior files retained; public aggregation requires the full scheduled grid. No silent restart or changed fingerprints.

## Fixed timing protocol

Run one serial worker. Record native schema/content build and commit/close, native disk bytes/hash, reopening the persisted index, source-integrity validation, tokenizer setup and the separate reference-index preparation clocks. SQLite content is unchanged after build and reopened read-only for ranking.

For each of 432 query/engine jobs, construct native literal terms once outside ranking timing (record that normalization clock), perform one untimed ranking warm-up, then three serial measured ranking repetitions. Each repetition must agree with the first result; a disagreement is retained as a ranking fault. Native ranking timing includes the complete matching-order fetch before the top-32 candidate cap. Reference timing covers the existing full ranking call, including its own normalization. Preserve each repetition separately; no averaging away failures or rerunning a faster sample. Packing is timed once per scheduled packet, excluding checkpoint persistence and scoring validation. Clocks cover different work and implementations; no equivalent-algorithm, provider, storage-system or causal latency/hardware claim is permitted. Shared-host load and the fixed warm schedule limit interpretation.

## Verification and publication

The runnable stdlib self-check covers Unicode/diacritics, punctuation, injection-looking text treated as literal terms, embedded quote escaping, empty/unknown terms, duplicate IDs, and a real disk index reopened before and after a committed source revision update and deletion. It also checks rollback consistency, native hit ordering/sign, interrupted-step retention and altered source packet rejection.

Official SQLite documentation only: [FTS5 query strings](https://www.sqlite.org/fts5.html#fts5_strings), [unicode61](https://www.sqlite.org/fts5.html#unicode61_tokenizer), [bm25](https://www.sqlite.org/fts5.html#the_bm25_function), [fts5vocab](https://www.sqlite.org/fts5.html#the_fts5vocab_virtual_table_module), [bound parameters](https://www.sqlite.org/lang_expr.html#parameters), and [transactions](https://www.sqlite.org/lang_transaction.html). Their role and access ledger are in `native-index-sources.json`.

Publish only this plan, code, safe aggregate/report, source catalog and derived scientific figure pairs/registry. Keep the database, source/query text, MATCH expressions, exact packets, per-step errors and private paths outside Git. Root owns publication, PARA and opening the artifacts. Existing QUERY files stay stable.
