# Small decision models for memory retrieval

**Research access date: 2026-10-11. Local model execution results are pending at the time of this research note.** This literature and distribution review proposes measurable retrieval components; it does not report successful local inference, a winning architecture, or a production memory migration. The [October 9 pilot](../study-2026-10-09/REPORT.md) remains a separate study. The October 11 catalog, `model-sources.json`, supplements the historical 125-source catalog without changing its October 8 cutoff.

The most practical interpretation of a decision-only model is a scorer that returns relevance scores or category labels instead of generating an answer. Two small encoder rerankers are suitable first candidates. Their value should be tested alongside deterministic search and evidence expansion. The important objective is complete governing evidence, including corrections and exceptions, rather than fewer tokens alone.

## What a decision model actually decides

A cross-encoder jointly processes a query and a candidate passage and produces a relevance score. It differs from a bi-encoder, which independently embeds queries and documents for similarity search. A cross-encoder can exploit interactions between their words, but it must process each candidate pair. The standard practical arrangement retrieves a shortlist first and reranks it second. [DR06](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)

This is a useful division of work. An encoder scorer does not need a conversational session, generated explanation, or repeated filesystem tool calls. Nevertheless, it still tokenizes and computes over input text. A score is neither a proof that a source is correct nor a calibrated probability that an answer is safe. A highly relevant obsolete decision can rank above a short correction because both discuss the same subject. Authority, applicability and evidence completeness need their own checks.

The earlier pilot illustrates the distinction: a reader received all governing originals, yet retained a superseded value. Retrieval coverage, factual use and structural checks can dissociate. A newer consistency-audit preprint similarly separates corpus conflicts, retrieved-context conflicts and answer consistency on controlled corpora. Its inspection framework does not certify truth. [DR12](https://arxiv.org/abs/2609.07075)

## Candidates for the first local comparisons

| Candidate | Publisher properties | Proposed role and limit |
|---|---|---|
| MiniLM L6 cross-encoder | 22.7M parameters; English; Apache-2.0 card; standard BERT sequence classifier | Small CPU baseline; combined query and passage limit of 512 tokens |
| Mixedbread xsmall v1 | 70.8M parameters; English; Apache-2.0; standard DeBERTa-v2 sequence classifier | Second encoder architecture; also a 512-token combined limit |
| Qwen3 Reranker 0.6B | Multilingual; Apache-2.0; documented 32K sequence length | Later longer-input and multilingual comparison; considerably larger |

MiniLM's card describes MS MARCO passage-ranking training and supplies raw score examples. Its published throughput table uses a V100 GPU; those numbers are not estimates of desktop CPU performance. The inspected tokenizer configuration lowercases input. A comparison must record this behavior, particularly for identifiers and names. [DR01](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2)

Mixedbread xsmall has publisher ONNX exports and preserves case. Its standard sequence-classification configuration contains no custom architecture mapping. Its model-family benchmark is aggregated across selected BEIR datasets, rather than agent memory tasks. The current Mixedbread repository prominently discusses newer, larger v2 models; their multilingual and long-context claims must not be transferred to this English xsmall v1 checkpoint. [DR02](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1)

Qwen is a different kind of scorer. Its official example loads a causal model and compares the final-position logits for yes and no. A forward pass can therefore return a decision score without generating reasoning or prose. This is operational decision scoring, although the underlying architecture is generative. Its larger input capacity is useful to test, not an assurance that longer inputs improve evidence selection. [DR03](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)

Apache-2.0 distribution terms support these practical local comparisons. They do not, by themselves, establish that all training data and training procedures are reproducible. Code licenses, checkpoint licenses and training-data availability are separate properties. As a contrasting example, Jina reranker v3 distributes useful scoring weights under CC BY-NC 4.0; describe that release as restricted open weights rather than an unrestricted open-source choice. [DR04](https://huggingface.co/jinaai/jina-reranker-v3)

## Exact quantized versions and loading boundaries

The following values were read from the publishers' live repository metadata and small configuration files. They identify the proposed artifacts; they are not local download or inference receipts.

| Model | Pinned revision | Selected ONNX artifact | Size in bytes |
|---|---|---|---:|
| MiniLM L6 | `233902d25c440f23af6f7d6e94d2946bac0bee0a` | `onnx/model_quint8_avx2.onnx` | 23,200,716 |
| Mixedbread xsmall | `b5c6e9da73abc3711f593f705371cdbe9e0fe422` | `onnx/model_quantized.onnx` | 87,245,802 |

The advertised LFS SHA-256 values are:

- MiniLM: `c80a8b34256ea453093d612e3ac48d3d965a0c0a48c7906709af8b8e28461bf9`.
- Mixedbread: `15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30`.

Each distribution provides `config.json`, `tokenizer.json`, `tokenizer_config.json` and `special_tokens_map.json`. MiniLM also provides `vocab.txt`; Mixedbread provides `spm.model` for a slow-tokenizer fallback. The inspected configurations use built-in BERT and DeBERTa-v2 types, with no `auto_map`. They do not require remote custom Python code. Load reviewed local files, disable remote code and validate actual model inputs and outputs before collection. [DR01](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2), [DR02](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1)

MiniLM's selected export targets AVX2. Mixedbread's quantization configuration specifies QInt8 weights, per-channel quantization and reduced range. Hardware compatibility and successful inference still require execution checks. Quantized rankings should be attributed to that exact checkpoint and backend; their equivalence to full precision is not assumed.

## Token boundaries and real costs

Both immediate candidates allow 512 tokens for the query, passage and special tokens together. A long record silently truncated before its correction would appear successfully scored while losing essential evidence. Freeze the passage construction policy, preserve source identities, and record truncation. Later tests should place a governing correction beyond the initial window and compare explicit windowing with full-record expansion.

Three budgets should remain separate: scorer input tokens and pairs, returned context for the downstream reader, and reader input/output tokens. A local classifier can remove API calls for selection while consuming CPU time and memory. It does not make retrieval cost zero. A smaller returned context can also be expensive to obtain if every branch and every document must be scored.

Measure initialization separately from warm inference, with CPU thread count, batching, sequence length and concurrent load controlled. Report index construction and update costs as well as query latency. Sentence Transformers documents PyTorch, ONNX and OpenVINO options and warns that performance varies by model and workload. Its backend guidance is a reason to measure, not a promise that a named optimization always wins. [DR05](https://www.sbert.net/docs/cross_encoder/usage/efficiency.html)

## Deterministic retrieval and the candidate ceiling

Lexical ranking, exact identifiers, aliases and explicit scope filters provide strong non-generative baselines. BEIR's heterogeneous comparison finds BM25 robust, while reranking and late interaction achieve strong average zero-shot results at greater computation. This supports comparing several mechanisms and task types instead of designing only examples where semantic matching should succeed. It does not establish an expected improvement on this study's fictional workstreams. [DR07](https://arxiv.org/abs/2104.08663)

The shortlist is a hard ceiling: a reranker cannot recover a correction excluded before scoring. Report candidate-stage governing-source recall separately from final context recall. Compare scoring all records on small collections with reranking a fixed lexical shortlist. This reveals whether a failure belongs to candidate generation or the decision model.

Deterministic expansion is a separate hypothesis. After selecting a record, resolve its source links, supersession chain and prerequisite links with explicit cycle and missing-link handling. This can recover related evidence without asking a language model to guess every connection. Supplied links are an experimental input, however. Perfect author-supplied metadata tests the benefit of using correct links; it does not test reliable automatic extraction. Missing, wrong and stale links require additional conditions.

## Hierarchy as representation and hierarchy as pruning

A branch scorer can compare a query with descriptions of candidate folders, keep a small beam, and then score records below them. Branch descriptions may convey scope more clearly than arbitrary directory names. But a wrong parent decision can exclude an entire subtree. Folder ownership is also not necessarily semantic relevance: shared evidence may belong to an area while governing several projects.

Published hierarchical retrieval offers mixed, useful guidance. HHR combines sparse and dense methods at document and passage levels and reports improved zero-shot retrieval relative to its dense hierarchical baseline. Its document/passages hierarchy and training regime differ from a personal filing tree. [DR08](https://aclanthology.org/2023.findings-acl.679/)

RAPTOR constructs a hierarchy of summaries and original passages, but compares two query policies. On its 20-document QASPER subset, searching the collapsed multi-level tree performs better than layer-by-layer traversal; the main experiments use collapsed retrieval. Thus, useful hierarchical representations do not imply that greedy branch pruning is best. The comparison is limited, and summary generation is itself a learned preprocessing step. [DR09](https://arxiv.org/html/2401.18059v1)

Compare flat retrieval, beam-one routing, beam-two routing and routing with global rescue under the same returned-context allowance. Count branch decisions, scored pairs, excluded governing sources and rescue successes. Global rescue should have a frozen rule and budget; enabling it only after inspecting failures would bias the comparison.

## Governing evidence and memory-specific evaluation

Memory queries require more than topical similarity. They may ask for a past state, the current approved state, a scoped exception, or whether sufficient evidence exists to proceed. LongMemEval explicitly separates indexing, retrieval and reading and includes knowledge updates, temporal reasoning, multi-session reasoning and abstention. Its published design improvements motivate tests of granularity and retrieval cues, while its conversational question answering does not validate executable agent workflows. [DR10](https://arxiv.org/abs/2410.10813)

Temporal-conflict research uses evolving document versions and structured subject, relation and timestamp records. It reports gains for knowledge organization over its tested baselines. This supports testing applicability metadata, while also exposing the cost and possible errors of extracting structured state from prose. Modification time alone is an inadequate stand-in for when a decision became effective. [DR11](https://arxiv.org/html/2506.07270v1)

For each task, predeclare the complete governing evidence set and the decision it supports. Score complete recovery, correction and dependency recovery, wrong-scope selection, and final source-grounded action separately. A topical ranking metric can remain useful without becoming the primary success gate. Contradictory evidence should remain inspectable when unresolved; dropping it to obtain a cleaner-looking answer can hide the real task. [DR12](https://arxiv.org/abs/2609.07075)

## Adjacent classifiers and recursive reasoning models

SetFit combines a sentence-embedding body with a classification head and supports few-shot training without inference prompts. Its framework is Apache-2.0; the chosen base model has its own license. A branch-label classifier built this way would require training examples and held-out workstreams, rather than importing a ready-made PARA expert. [DR13](https://github.com/huggingface/setfit)

fastText is MIT-licensed classification software. It offers a simpler supervised routing baseline, but branch labels and language-specific coverage still have to come from the experiment. A trained classifier emits labels; it does not explain which source versions govern a downstream action. [DR14](https://github.com/facebookresearch/fastText)

HRM and TRM are relevant architectural research rather than drop-in document retrievers. Their releases demonstrate small recurrent or recursive networks on trained puzzle tasks. Applying those approaches to natural-language filing would require a new task representation, training data and an evaluation against simpler scorers. Their puzzle results do not establish faster or better memory retrieval. TRM's repository is archived as of the access date, which also matters for maintenance planning. [DR15](https://github.com/sapientinc/HRM), [DR16](https://github.com/SamsungSAILMontreal/TinyRecursiveModels)

## Atomic combinations and evidence needed for a recommendation

Separate the interventions: aliases; scope cues; passage reranking; branch pruning; global rescue; deterministic evidence expansion; and source-version checks. A change to one factor should not silently change document truth, candidate limits or reader instructions. Factorial combinations can then estimate interactions, such as whether reranking helps only after aliases recover the missing candidate.

Keep independently authored workstreams as the statistical unit. Split development and held-out testing by family; paraphrases, repeated conditions and repeated model draws remain within that family. Freeze preprocessing, metadata assumptions, query wording, thresholds and budgets before outcomes. Report paired family-level differences with uncertainty and task-specific failures rather than treating every condition as a new independent case.

The useful comparison is a frontier: complete evidence and correct source use against latency and context volume. Fewer retrieved tokens are beneficial when governing evidence remains available. More scored pairs may be justified when they recover corrections. Any claim that a small decision model improves the filing system needs both executed retrieval measurements and downstream evidence-use checks. Those results belong to the execution report, not this literature review.
