# Retrieval beyond repeated relevance inference

Primary sources were accessed on **2026-10-13 UTC**. This note separates implemented infrastructure, fictional smoke checks and research hypotheses. It does not report benchmark accuracy, select a policy using held-out outcomes or change the October 9/11 studies. The associated source catalog is [index-sources.json](index-sources.json).

The research direction is to increase the number of genuinely different mechanisms while making their failures attributable. Retrieval can fail because a name does not match, a requirement receives too little attention, an exception lacks topical language, the index is stale, a representation truncates the governing sentence, or the reader misuses correctly retrieved evidence. A different scoring model addresses only some of these problems. The following implementations therefore keep retrieval, evidence expansion, packing and downstream verification separate.

## Implemented deterministic policies

[index_lab.py](index_lab.py) supplies thirteen policies using the Python standard library. Every policy accepts the same retained record fields and query, returns every collection ID once, and uses lexical ID order for tied scores. It never accepts task answers, evidence sets, author strata or outcome labels. Unknown fields are ignored before index hashing. No policy generates text, changes a source or builds the reader's context packet. Search metadata can therefore be useful without consuming reader context bytes; the experiment's packet builder must enforce that separation.

| Policy | Distinct mechanism | Fixed implementation and main failure hypothesis |
|---|---|---|
| `body_bm25` | Lexical source-body baseline | NFKC/casefold Unicode word tokens; BM25 k1=1.2, b=.75. Exact names absent from the body can be missed. |
| `search_bm25` | Search-only descriptive metadata | Concatenate title, scope, aliases and body for indexing. Compare directly with body BM25 to isolate the representation change. |
| `word_tfidf` | Cosine rather than BM25 saturation | Log-scaled term counts, smoothed IDF, L2-normalized vectors. Long records and uncommon query words interact differently. |
| `char_tfidf` | Partial word and spelling overlap | Boundary-preserving character 3/4/5-grams inside each normalized word, with TF-IDF cosine. Supports surface-form overlap, not semantic equivalence. |
| `field_bm25` | Separately weighted fields | body BM25 + 2×title BM25 + cue BM25; cues contain scope/aliases. Independent field scores are combined after saturation. This is **not** BM25F. |
| `rrf_word_char` | Fusion of heterogeneous lexical rankings | Equal reciprocal rank fusion of search BM25 and character TF-IDF; k=60, ranks start at one. |
| `entity_rrf` | Literal identity as an additional channel | Add a partial ranking of exact case-sensitive record IDs and normalized alias-phrase matches. Nonmatches receive no entity-channel vote. |
| `clause_rrf` | Fair attention to multiple written requirements | Split the actual query at semicolon/question/newline and “and/also/plus”; fuse up to eight clause BM25 rankings equally. Log omitted clauses. |
| `sentence_maxsim` | Local matches inside a long record | TF-IDF cosine over body sentence fragments; average each query clause's maximum sentence match. Source order is ranked, not rewritten. |
| `coverage_mmr` | Sequential marginal coverage and redundancy | Greedy score = .65 normalized BM25 + .25 newly covered IDF-weighted query terms − .10 maximum similarity to an already selected record. |
| `scope_temporal` | Explicit applicability rather than recency | Add/subtract .20 for a uniquely mentioned known scope and .20 for a declared effective interval matching literal “as of YYYY-MM-DD.” Keep every original eligible. |
| `graph_diffusion` | Move lexical relevance through declared relations | Four diffusion rounds, .35 propagation/.65 query restart, over a bidirectional graph of links, supersedes and incorporation IDs. Missing edges remain in the receipt. |
| `pseudo_feedback` | Unsupervised vocabulary expansion | Take the top three positive BM25 sources; select six non-stopword body terms by clipped TF×IDF; combine .75 original and .25 expanded normalized scores. |

These are thirteen implementation policies, not thirteen independent causal hypotheses. Several share the same tokenizer and lexical scorer. For example, body/search BM25 isolates one representation choice; RRF combines two previously defined channels. A factorial plan should isolate those components before interpreting a combined policy's outcome.

The BM25 constants match familiar Lucene choices, while this study keeps its own explicit tokenization and exact formula. Its scores are not claimed to be byte-equivalent to Lucene or calibrated relevance probabilities. [IL01: Lucene BM25 API](https://lucene.apache.org/core/9_9_1/core/org/apache/lucene/search/similarities/BM25Similarity.html)

Character grams and smoothed TF-IDF are established text representation tools. The scikit-learn documentation describes word/character analyzers and the weighting choices; this implementation reimplements the declared formulas without importing scikit-learn. It does not learn transliterations, repair arbitrary typos or understand a renamed workstream unless an indexed alias supplies the bridge. [IL02: feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html), [IL03: vectorizer parameters](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)

RRF's original formula needs no learned fusion weights, but its constant remains a choice. A later analysis finds sensitivity to fusion parameters and better convex combinations on its tested datasets. Neither paper establishes a winner for this vault-like benchmark. Consequently k=60 is a fixed baseline; tuning requires development data and a separate held-out evaluation. Receipts expose the channel rankings, rather than calling their agreement confidence. [IL04: original RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf), [IL05: fusion analysis](https://arxiv.org/html/2210.11934v2)

Literal identity is a useful escape from semantic ranking, particularly for product codes, source IDs and homonyms. OpenSearch's exact-term guidance also explains why analyzed text fields are a poor substitute for literal keyword fields. The local identity channel preserves case for record IDs but normalizes aliases; it does not establish that an alias refers to exactly one entity. Shared aliases should remain explicit collision cases. [IL06: exact-term semantics](https://docs.opensearch.org/latest/query-dsl/term/term/)

Clause fusion, sentence MaxSim and marginal coverage are three different ways to address a query with several requirements. The first rewards documents that rank well for separate written clauses; the second lets different sentences support different clauses; the third rewards new query-word coverage across a sequence of records. Token coverage is only a proxy for an information requirement. “Permission is withheld” and “permission is granted” may share almost all words while governing opposite actions.

MMR introduced a relevance/novelty tradeoff, and coverage-based diversification makes the set objective explicit. Our .65/.25/.10 lexical heuristic is inspired by that family, not a replication of its subtopic models or a proof of submodular optimality. A correction may be almost a duplicate of the obsolete record it corrects. Deduplication or diversity penalties can therefore discard the most important change. Measure governing-original recovery and correction recovery separately from topical diversity. [IL07: MMR](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf), [IL08: coverage diversification](https://www.eecis.udel.edu/~hfang/pubs/irj12.pdf)

The graph policy borrows the idea of query-biased relevance propagation from personalized/Topic-Sensitive PageRank. It performs only four rounds on declared local relations and is not the original precomputed topic algorithm. An undirected relation is deliberately an eligibility cue, not authority: a stale summary can point to a current original, and a wrong link can spread relevance to an irrelevant source. Evaluate correct, missing, wrong and high-degree links separately. [IL09: Topic-Sensitive PageRank](https://snap.stanford.edu/class/cs224w-readings/Haveliwala02Topicsenitive.pdf)

Pseudo-feedback is a deliberately cheap experimental alternative to a generative query rewrite. It can bridge vocabulary when the first results are useful, and amplify the wrong topic when they are not. The relevance-language-model literature motivates studying feedback, but the six-term TF-IDF heuristic is not RM1/RM3 and supplies no learned relevance estimate. [IL10: relevance-based language models](https://ciir-publications.cs.umass.edu/pub/web/getpdf.php?id=225)

## Cached dense retrieval actually implemented

[dense_runtime.py](dense_runtime.py) uses the public Apache-2.0 `sentence-transformers/all-MiniLM-L6-v2` encoder. It is a **bi-encoder**, distinct from the October 11 `cross-encoder/ms-marco-MiniLM-L6-v2` reranker. The model card describes 384-dimensional sentence/paragraph representations and default 256-wordpiece truncation. The chosen publisher ONNX artifact is pinned below; the adapter implements attention-mask mean pooling followed by L2 normalization. [IL11: dense model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [IL12: publisher ONNX files](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/onnx)

| Property | Frozen value |
|---|---|
| Revision | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Weight | `onnx/model_quint8_avx2.onnx` |
| Publisher bytes | 23,046,789 |
| Publisher and downloaded SHA-256 | `b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21` |
| CPU settings | CPUExecutionProvider, two intra-op threads, one inter-op thread, sequential execution, batch size 12 |
| Already installed packages in smoke | numpy 2.4.5; onnxruntime 1.29.0; tokenizers 0.23.1 |

Seven model/configuration/tokenizer files are validated against pinned SHA-256 values, including existing cached files. Their public manifest is [dense-model-spec.json](dense-model-spec.json). No pickle, torch, authenticated model service, downloaded Python code or new dependency is used. The model and embedding cache must be outside the public repository. Cache arrays use NumPy's non-pickle format; reload validates the vector digest, shape, floating type, finiteness and normalization.

Two independent representation factors are available. `text_mode='body'` encodes only source prose; `text_mode='search'` encodes title, scope, aliases and body. `windows=False` encodes the entire chosen string with 256-token truncation. `windows=True` instead creates 192-token windows with 32-token overlap from tokenizer offsets, records original Unicode character ranges and aggregates the maximum query cosine for each source. Windows are retrieval representations; they do not automatically authorize the packet builder to omit surrounding qualifications. The maximum can overrate a long irrelevant source because it offers more chances to contain a matching window.

The query is encoded once per call. `dense` ranks normalized cosine; `dense_rrf` fuses that order with BM25 over the same body/search representation, with k=60. The current adapter performs exact matrix search and no approximate-nearest-neighbor pruning. Measure query encoding, matrix search, index preparation, cache reload, storage, updates and model loading separately. Backend documentation describes mean-pooling requirements and quantization options; it does not predict this machine's throughput. [IL13: Sentence Transformers backend guidance](https://www.sbert.net/docs/sentence_transformer/usage/efficiency.html)

The private smoke receipt confirms execution, not benchmark quality: a pair of fictional retention sentences had cosine .778, compared with −.021 for a fictional recipe; a long test string triggered truncation; whole-record and window indexes produced complete rankings; window representations in that smoke did not truncate; vector reload was exactly equal. The first short query calls took about six milliseconds after loading and indexing, but three fictional records are not a meaningful latency benchmark. Those observations must not be presented as a speed advantage over the previous study.

## Applicability and uncertainty remain separate problems

The temporal policy intentionally refuses to substitute modification or authorship time for when a rule applies. It uses optional explicit `effective_from`/`effective_to` dates (also accepting the observable field names `valid_from`/`valid_to`) with inclusive boundaries and a literal query date. Conflicting field names are rejected. No date is invented for undated records. It recognizes a scope only when exactly one known literal scope occurs in the query; absent/ambiguous scope stays unknown. All records stay eligible even after a negative applicability bonus. This policy is weak on purpose: it tests the value of supplied correct fields, not automatic extraction of temporal meaning.

The temporal retrieval survey distinguishes temporal intent, normalization and evolving facts; TempRetriever explores lexical/temporal-semantic fusion for time-sensitive questions. Their tasks motivate further experiments but do not validate this simple rule or treating the newest record as authoritative. Test late imports, historical questions, future-effective approvals, scoped exceptions and overlapping intervals. [IL14: temporal retrieval survey](https://arxiv.org/html/2505.20243v1), [IL15: TempRetriever](https://arxiv.org/abs/2502.21024)

A low score gap, channel disagreement or missing link is evidence of retrieval uncertainty, not a calibrated probability that context is sufficient. A proposed coverage-aware controller can search additional channels when declared constraints lack support, but it must log its stop rule and cannot use the authored evidence set to decide when to stop. Also retain low-relevance governing corrections independently: authority is not topical similarity. A useful future paired comparison is fixed retrieval versus retrieval plus an independently specified missing-field/contradiction search, with the same total context allowance.

## Additional avenues researched, not implemented in this adapter

| Avenue | Mechanism and promising independent experiment | Current boundary |
|---|---|---|
| Document-only neural sparse | Precompute expanded term weights; literal query-token IDF lookup avoids neural query inference. Compare index cost/update cost with cached dense. | OpenSearch `doc-v2-distill` card says Apache-2.0; no weights downloaded, inference or export performed here. |
| SPLADE-family sparse expansion | Neural vocabulary expansion with sparse matching can bridge paraphrases while retaining term attribution. | Inspected NAVER cocondenser checkpoint is CC BY-NC-SA 4.0, not the permissive execution choice for this lab. |
| ColBERT late interaction | Cache token vectors; sum each query token's best document-token match. Compare complete evidence recovery with single-vector/window-max retrieval. | Official code is MIT; no ColBERT index or inference run here. CPU/search and GPU/indexing requirements need a separate adapter plan. |
| Learned fusion calibration | Tune a small number of channel weights on development families, then freeze. | Requires held-out families and scope-specific calibration; no learned weights in these policies. |
| Contrastive requirement retrieval | Independently search for vetoes, exceptions, unresolved approvals and disqualifying conditions alongside positive matches. | Proposed lexical/structured controller; a negative word alone is not a veto or contradiction. |
| Cost-sensitive set packing | Optimize marginal governing coverage per context byte while reserving space for linked qualifications. | Requires a support proxy available at retrieval; using the gold bundle would be oracle packing. |
| Causal/update index tests | Edit one original, rename one alias, add a future correction, then restart and query before/after. | Exact cache keys include the used content/metadata and source revision; natural extraction correctness remains untested. |
| Active evidence acquisition | Treat absent prerequisites or channel disagreement as reasons for a bounded additional search. | Specify observable triggers, expansion cost and stopping behavior before outcomes are inspected. |

OpenSearch's exact document-only checkpoint encodes documents with a masked-language-model transform, while the demonstrated query is token presence multiplied by supplied IDF weights. “Inference-free query” still includes tokenization and search. NAVER's inspected sparse checkpoint has a different license. They must not be treated as interchangeable implementations. [IL16: OpenSearch document-only card](https://huggingface.co/opensearch-project/opensearch-neural-sparse-encoding-doc-v2-distill), [IL17: NAVER SPLADE card](https://huggingface.co/naver/splade-cocondenser-ensembledistil)

ColBERT delays query/document interaction until after independent encoding and retains a token-level MaxSim mechanism. The local sentence TF-IDF policy and dense-window maximum are much cheaper proxies; neither implements ColBERT. Published throughput and accuracy refer to their own hardware/corpora. The official repository's current distribution and license are linked for future implementation work. [IL18: ColBERT paper](https://people.eecs.berkeley.edu/~matei/papers/2020/sigir_colbert.pdf), [IL19: official repository](https://github.com/stanford-futuredata/ColBERT), [IL20: MIT code license](https://github.com/stanford-futuredata/ColBERT/blob/main/LICENSE)

## Reproducible interface and checks

```python
from index_lab import PreparedIndex, METHODS
index = PreparedIndex(docs)             # document ID -> retained source fields
index.prepare_characters()             # charge this to build time if used
ids, receipt = index.rank_with_receipt(query, 'entity_rrf')

from dense_runtime import Encoder, DensePreparedIndex
encoder = Encoder(private_cache, threads=2)
dense = DensePreparedIndex(docs, encoder, text_mode='body', windows=True)
ids, receipt = dense.rank_with_receipt(query, 'dense_rrf')
```

The simple `rank(docs, query, method)` function creates a new stdlib index each call. Use the prepared interface to study amortized costs. Every deterministic receipt records retained-collection/query/ranking hashes and method-specific diagnostics; it excludes timing so repeated identical calls are equal. Dense receipts separately retain execution timings, token counts, truncation and index identities. A cached build retains the original build's token-usage receipt, clearly marked with `index_cache_hit`; it does not claim those tokens were recomputed during reload.

[benchmark_runner.py](benchmark_runner.py) adds the prospective study orchestration. `--prepare` trains the depth-three tree only with development queries/documents and builds three full-bank dense indexes. `--run` requires the exact freeze-file SHA and verifies pinned code/bank/model files before scoring. Two hidden owned workers are the ceiling. Query-group checkpoints are fingerprinted; a completed recorded fault is preserved when resuming. Public per-template shards omit repeated source text and retain exact intervals, body hashes, packet/packing-receipt hashes, complete-rank digests and top-64 IDs. The four dense policies intersect global document cosine scores with each local collection; window RRF then uses **local** BM25 IDF/ranks. `build_packet(family_id, task_id, ranker, packer, budget, size, privatework)` reconstructs a stored cell and checks the executed interval/hash/byte receipt without loading a model. The self-check confirms the prospective 21-ranker/198-cell schedule and reconstruction on artificial records; it does not run the bank comparison. Warm timing is a separate serial mode with document indexes prepared first and query/pair caches disabled.

Run `python index_lab.py --self-check`. The actual local check passed all thirteen policies: complete permutations, deterministic receipts, finite scores, ID boundaries, explicit effective dates, missing edges, empty collections, exclusion of unknown/gold fields, snapshot isolation and malformed-input rejection. Run `python dense_runtime.py --cache PRIVATE_CACHE --smoke --receipt PRIVATE_RECEIPT` for the optional pinned model smoke. No factorial scored outcomes are loaded by either check. The study runner, evidence labels, budgets, outcome analysis and publication are separate responsibilities.
