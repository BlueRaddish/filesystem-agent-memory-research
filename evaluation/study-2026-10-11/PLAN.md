# Expanded atomic retrieval study — prospective protocol

This is a new study, separate from the frozen October 9 pilot. The user authorized additional rounds, a larger case bank, independently switchable hypotheses, deterministic retrieval and locally executed open-source scoring/routing models. Only newly authored fictional records enter public model requests. Production PARA and capture tools are unchanged.

## Atomic factors

| Factor | Off | On |
|---|---|---|
| A: index cues | Generic record header | Add existing record title, workstream aliases and scope to its index/header; original body unchanged. |
| B: dependency expansion | Pack the ranked seeds | Expand declared references and reverse supersession edges from ranked seeds within the same total context-byte budget. |
| C: derived-view version gate | All records eligible | Remove derived views whose declared incorporation ledger is stale, missing or inconsistent with available source versions/declared supersession. Originals remain eligible. |

All eight A/B/C combinations are evaluated. These are authored metadata interventions; accurate extraction of aliases or dependencies from arbitrary prose is **not** demonstrated. Incorrect and missing metadata are a separate stress stratum. Filtering is not a warning or an automatic summary repair.

Expansion uses breadth-first traversal to depth two and at most 16 newly appended records per ranked seed, including reverse supersession. These fixed bounds prevent unbounded closure; they do not demonstrate recovery of arbitrary long dependencies. Gate scope compatibility is exact equality or literal `all`. Broad authored desk views use `all`; arbitrary natural-language scope equivalence is not inferred.

## Corpus and split

Two isolated LLM authors each create 24 semantic families with two task queries and 10–14 original/derived records per family. The 48 families and 96 clustered tasks are not human-authored or representative population draws. Authoring scripts must disclose common framing and causal-template reuse; new names/numbers alone do not create independent families. Development takes the lowest-ID family in six predeclared strata per author: A uses correction, scope, conflict, prerequisite, Unicode and import; B uses conflict, prerequisite, Unicode, import, missing-edge and wrong-ledger. `family-split.json` records the exact IDs, giving 12 development and 36 held-out families while retaining each stratum in held-out. Both queries and all variants remain in the same family split. This replaces an initial unexecuted 01–06 split that could remove whole strata when authoring order groups similar cases; no scored result motivated the correction.

Strata include late corrections, scoped exceptions, unresolved authority, missing prerequisites, Unicode/aliases, late imports, missing edges and wrong incorporation ledgers. Ground truth declares explicit `ready`/`hold` status, answer keys, critical values and alternative sufficient original-evidence sets. It is excluded from every retriever/scorer/router/reader input. Original bodies retain the required facts.

The completed bank has exactly 480 records: A has 192 originals and 48 derived views; B has 216 originals and 24 derived views. Every task currently has one authored sufficient set, not exhaustively adjudicated alternatives or a proven minimal set. Peer LLM reviews checked the two banks against source bodies and corrected an adoption-evidence omission and an ambiguous internal courier handoff before collection. No human gold adjudication occurred. Shared role order, repeated provenance/domain framing and a uniform ten-record family shape constrain causal diversity.

Each task receives a deterministic collection containing every document from its target family plus unrelated/near-match documents drawn from other families. Collection sizes are 48 and 144 documents, and output budgets are 4,096 and 8,192 UTF-8 bytes. Deterministic fixture construction uses the task's family only to build the environment; engines receive all collection records, a query and public metadata, never target-family identity or gold. Cross-family distractors are not additional independent tasks. Whole records are packed; oversized records are skipped and recorded, not silently truncated. No record deletion changes retention.

Prospective byte-feasibility inspection found that only 49/72 held-out authored bundles fit 4,096 bytes without A cues and 32/72 with them; all fit 8,192. Report this structural ceiling alongside recovery and a clearly labeled feasible-subset descriptive result. A combines improved index cues with their serialization cost; a zero result where the authored bundle cannot fit does not isolate ranking quality. Oracle diagnostic packets intentionally bypass the byte budget.

## Round 1: factorial retrieval

Run eight factor cells at both byte budgets and both collection sizes for all tasks using BM25. The primary retrieval outcome is complete recovery of at least one declared sufficient **original** evidence bundle. Also report governing-ID coverage, bytes, reconstructed local tokenizer counts, document counts, stale/derived-view inclusion, missing references, total warm index/rank/pack costs and paired family-level A/B/C effects and interactions. Individual index and packing times are not separately instrumented. Coverage does not establish correct source use.

## Round 2: retrieval engines and branching

Use the same corpus, factors and budgets for six fixed engines:

1. Flat BM25.
2. BM25 branch ranking, top two branches, then document BM25.
3. BM25 top-32 candidates reranked by pinned quantized MiniLM L6.
4. BM25 top-32 candidates reranked by pinned quantized Mixedbread xsmall.
5. Mixedbread top-two branch routing followed by within-branch scoring.
6. The same learned branch routing with a fixed top-eight global BM25 rescue candidate set.

Branch descriptions consist of retained workstream identity/aliases and concatenated record titles/scopes (when A is on), not an answer-bearing generated summary. Global rescue is always performed in its own arm; it is not a threshold tuned on held-out scores. Learned branch decisions and document candidate sets are retained so evidence lost before reranking can be distinguished from packing loss. The exact two quantized artifacts, publisher revisions and SHA-256 values live in `model_runtime.py`. Scores are not calibrated authority/correctness probabilities. Combined query/document inputs are capped at 512 model tokens; truncations are counted. Model load/download, first query and warmed scoring costs are separated. Cached score reuse across B/C/budget cells is declared and never counted as a fresh latency measurement.

## Round 3: downstream decisions and fresh discovery

Select 12 held-out families from each author by ascending SHA-256 of `family_id + ':reader-20261011'`, before examining retrieval outcomes. Use query 1, the 144-document collection and 4,096-byte budget. Run four fixed packet arms per family (96 single-completion trials): BM25 000; BM25 111; Mixedbread rerank 111; learned routing with rescue 111. This compares fixed candidate systems, not every downstream factorial interaction.

For the first six selected families per author, add two separately labeled diagnostic controls (24 trials): the entire collection and a gold sufficient-original packet. Oracle packets are evaluation upper bounds, never deployable policies or evidence of retrieval efficacy. The full-collection control measures actual supplied context and costs; it is not resource-matched to small packets.

For those same 12 families, additionally compare raw virtual filesystem discovery and discovery with an explicit retriever tool (24 trials). Each new reader starts without PARA conventions or personal knowledge, sees a neutral task and JSON list/read/search/write protocol, and receives an initially shallow root listing. The virtual hierarchy is fictional PARA-style folders with workstream hubs and retained records. No native host filesystem is exposed. Only the retriever arm advertises a `retrieve` operation using the fixed Mixedbread-plus-expansion/version policy. Cap at four reader responses, 16 actions and 16,384 returned UTF-8 bytes, and report incomplete/no-write/invalid/native-unavailable/infrastructure outcomes in the denominator. This is navigation of this constructed hierarchy, not validation of a personal vault, external cold state or provider-wide erasure.

Discovery reserves 256 returned bytes for bounded control errors; execution stops when less than that reserve remains. Oversized whole observations are refused. A tool observation can ground a final artifact only after it has been replayed in a later reader prompt; a read and write in the same action batch do not establish that the model received the source. Search excerpts and complete reads are recorded separately. The helper accepts only the exact task query, returning its fixed packet; general query reformulation is outside this test.

The same Muse model/high effort is pinned across reader arms, using fresh rootless local processes/sessions and no provider continuation/store association. A development-only non-ASCII preflight must establish caller-to-upstream text-digest equality and exact output recovery. Remote service history, hidden system prefix and erasure cannot be certified. The adapter/wrapper/binary hashes and capabilities are recorded without publishing credentials or host paths. No silent repair/retry replaces a scored call; failures retain the original receipt. Responses are actually written to host-mediated artifacts and schema-checked, then factual/citation gates are independently graded against actually supplied/replayed original IDs. Decision accuracy is not described as a full deployment workflow.

## Freeze and analysis

Before scored collection, freeze corpus, code, plan, model/tokenizer manifests, deterministic schedules, reader schema and private adapter/wrapper hashes in a public-safe manifest. No held-out outcome tunes budgets, candidate counts, router depth, gates or selected reader arms. A correction discovered after collection remains a versioned amendment or separate sensitivity analysis, not a silent score change.

Primary reader success requires accepted JSON, explicit status, every critical answer value correct, sufficient valid original citations and clean completion. Extra valid citations/answer fields are allowed; section-qualified citations normalize to an original ID. Missing infrastructure responses remain failures for complete task and have unknown usage rather than fabricated zeros.

The automated answer gate compares exact authored values, including free-form strings and list order. Its primary result is **exact authored value-and-source match**, not an exhaustive semantic correctness judgment. Equivalent paraphrases or reordered unresolved lists can fail. A separate review of mismatch rows will identify plausible semantic false negatives, retain original scores and report its review scope; no post-collection vocabulary or scorer change replaces the frozen primary. Section suffixes are normalized to source IDs without verifying section existence, another limited citation proxy.

Report paired family-aggregated differences and whole-family bootstrap intervals as descriptive uncertainty conditional on this authored bank. Tasks, factor cells, noise variants and repeated measurements are not independent families. Report A/B/C main contrasts and AB/AC/BC/ABC interactions separately from engine comparisons. Keep development, held-out, reader, oracle, full-context and discovery tables distinct. Publish raw synthetic IDs/selections/receipts, runnable checks, source reviews, failures and limits, plus figures illustrating effects, interactions, evidence-loss stages, speed/context tradeoffs and fresh discovery.
