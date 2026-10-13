# External memory-retrieval transfer lane

This lane uses externally authored public benchmark artifacts and stays separate from the October 13 fictional bank. The runnable BEAM comparison follows [EXTERNAL-PLAN.md](EXTERNAL-PLAN.md); its only scored endpoint is publisher-declared original-message ID recovery. It does not reproduce a benchmark's answer score. No reader, judge, provider call, live tool action, screenshot, or private personal corpus is used here.

## Source access, provenance and licensing

The [source manifest](external-transfer-sources.json) pins data/code revisions, URLs, licenses, byte counts and hashes. Complete selected BEAM files were checked against publisher Git blobs and SHA-256. Bounded prefixes have their own actual hashes and are explicitly incomplete; a prefix hash is not whole-file verification. Raw third-party corpus, questions, answers, screenshots, profiles, embeddings and packets remain outside Git. Public references and derived schemas/counts do not rehost the data.

The pinned V2 checksum list matches the downloaded questions, small haystack, data card, schema and license. Its README entry differs: advertised SHA-256 `bd0890407b11ea5e7f521f47f031823f58f77ac8c9e0b5837bb4cae9f6bc9837`, actual pinned-file SHA-256 `c5de92eadfd8238802b476e446b05a766c312ab0f07518dbda434f914aa4df37`. The actual README independently matches the pinned publisher Git blob `db28e2234dd8b0a4221f2620d213567b1235aea0`. Record the checksum inconsistency rather than claiming every V2 publisher checksum passed. It does not affect the separately frozen BEAM files.

| Source | Verified access and origin | Retrieval feasibility and limitation |
|---|---|---|
| [LongMemEval-V2](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2/tree/f152293e235517d504809563c833d7190b8c713b) | Ungated, Apache-2.0. Human-curated questions over agent trajectories from synthetic benchmark environments. Full questions, schema, card and small haystack downloaded; only an 8 MiB trajectory prefix. | 451 questions; 422 text-only; two shared 100-trajectory small haystacks. Original support labels were removed in the released data. Text-only retrieval would require new support annotation and be an adaptation. |
| [Cleaned LongMemEval V1](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/tree/98d7416c24c778c2fee6e6f3006e7a073259d48f) | Ungated; dataset card declares MIT, code MIT. Human-curated questions and simulated/human-edited evidence, with public ShareGPT/UltraChat filler sources. Complete 15,388,478-byte oracle file matches publisher LFS SHA-256; S downloaded only as an 8 MiB prefix. | 500 oracle questions, including 30 abstentions. `answer_session_ids` and turn `has_answer` give original retrieval labels. Oracle histories lack distractors and cannot measure ordinary retrieval. The 15 complete S-prefix records all belong to one question type and are an ordered convenience audit. |
| [MemoryAgentBench](https://huggingface.co/datasets/ai-hyz/MemoryAgentBench/tree/7ea066982b140a19337e17e60d45d4076e042faf) | Ungated; dataset card MIT, code MIT. Mixed reformulated sources plus newly constructed tasks. Public metadata verified; corpus not downloaded/parsed. | Advertised split rows: 22 accurate retrieval, 6 test-time learning, 110 long-range understanding, 8 conflict resolution. Files are Parquet; no installed `pyarrow` and no dependency was added. Metadata includes answer-bearing fields, so forwarding it wholesale would leak labels. |
| [BEAM](https://github.com/mohammadtavakoli78/BEAM/tree/b2da22eac88bb0874c64665f13457eb99835774a) | Ungated JSON in the official repository; benchmark CC BY-SA 4.0, code MIT. Automatically generated synthetic conversations and probing questions with author validation. Five selected histories and questions checked against publisher Git blobs. | Small, text-only retrieval adaptation is feasible with original `source_chat_ids`. Named criterion groups must be preserved. Those labels have not been semantically validated as sufficient/minimal evidence. Official QA/nugget/ordering metrics are unexecuted. |
| [Mem2ActBench](https://github.com/Cantaloupe-M/Mem2ActBench/tree/b00726940b5abbe9bd324bdd7a2cb272f5c62a29) | Public JSONL; README declares MIT, but no standalone LICENSE at the pin. Source-specific derivative obligations not independently resolved. Synthesized/stiched ToolACE/BFCL/OASST1 histories and reverse-generated tasks with subset human review. | 400 QA rows downloaded; 123 complete sessions in a 2 MiB prefix. `tool_call`, `grounding_info`, `evolution_chain`, source IDs and complexity metadata are evaluator gold. Useful for later parameter-grounding study; no tool or score executed here. |

The V1 cleaning release is the current official data link in the [pinned README](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/README.md). Its mixed natural/synthetic history construction is described in the [paper](https://arxiv.org/html/2410.10813v1). MemoryAgentBench's source mixture and competency definitions come from its [official code README](https://github.com/HUST-AI-HYZ/MemoryAgentBench/blob/538026089d1a8a8eff05121d0db89b388f360eba/README.md). Mem2ActBench's task construction and subset human review are described in the [ACL paper](https://aclanthology.org/2026.acl-long.370/). A public benchmark license declaration does not independently establish every upstream component's redistribution terms; this repository ships none of these corpus files.

## What the executed read-only audit establishes

`external_probe.py` uses only the Python standard library. Its self-check and actual-artifact audit pass. It verifies 33 downloaded file digests and creates separate allowlisted source/query and evaluator-gold projections in memory. It prints schemas, hashes and counts, never source/question/answer text. The probe fetches nothing, writes nothing and computes no retrieval score. A projection boundary check proves which fields cross the interface; it does not prove semantic truth, absence of benchmark contamination in pretrained models, or annotation completeness.

The V2 question schema contains `answer` and `eval_function`; trajectory states contain actions, thoughts, accessibility observations and screenshot paths. The input projection withholds evaluator fields, question type, thoughts and screenshot paths. Its [released schema](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2/blob/f152293e235517d504809563c833d7190b8c713b/SCHEMA.md) supplies no support IDs, and the [release notes](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2/blob/f152293e235517d504809563c833d7190b8c713b/README.md) say the construction labels were removed. Only eight complete trajectories were observed in the prefix; the entire 1,195,604,539-byte trajectory file was not downloaded or validated.

All 29 V2 `errors-gotchas` questions have images; excluding images removes that capability entirely. The remaining types are static/dynamic/procedure and their premise-awareness abstention variants. Even their text-only questions can depend on screenshot-only history evidence. The [V2 paper](https://arxiv.org/html/2605.12493v1) describes human question annotation and multimodal evidence, while the [data card](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2/blob/f152293e235517d504809563c833d7190b8c713b/DATA_CARD.md) limits interpretation to customized benchmark environments. A later text-only lane must annotate support from released text alone, retain unsupported-text cases in its denominator, and explicitly distinguish this adaptation from V2's multimodal benchmark.

The first BEAM convenience audit has 188 messages, 20 questions and 18 label-bearing questions. Its support field mixes integer lists and dictionaries of named groups. Recursively flattening values resolves every original message reference; iterating dictionary keys would incorrectly treat criterion names as source IDs. This history was used for schema inspection and is excluded from the selected transfer sample.

## Separate, frozen BEAM experiment

The fixed path-hash rule selected histories 14, 6, 7, 16 and 10 before retrieval outcomes. They contain 1,452 messages, 100 questions, 90 positive-support questions and ten unlabeled abstention questions. The latter are outside the declared positive retrieval endpoint and remain counted in the source audit. The 90 labeled questions preserve 120 criterion groups across nine ability categories. Original message IDs resolve mechanically; support semantics are not independently certified.

Four preselected rankers cross two preselected packers and three UTF-8 budgets, giving 2,160 scheduled packets. The protocol fixes candidate, byte, wrapper, source-exactness, whole-message and partial-selection endpoints. Five histories are the analysis clusters; there is no independent-90-query interval, population winner, or pooling with the fictional study. The [machine-readable result](external-results.json) contains the timestamped protocol/code/data freeze and allowlisted descriptive outcomes. Private receipts retain the per-query rows and ranking/packet hashes. The existing quantized English MiniLM window encoder uses 192-token windows with 32-token overlap and a 256-token encoding cap; the official BEAM answer evaluators and model comparisons are not run.

## Executed outcomes: declared original-ID proxy

The freeze timestamp is **2026-10-13 10:14:19 UTC**, digest `956dc90c08577629f6b39cfd7e8a61998b3ea95c7c6b3f8e04ab76257ae89c58`. Lexical execution completed at 10:14:32 UTC; dense execution ran 10:18:56–10:23:15 UTC after explicit resource clearance. All **2,160/2,160** scheduled positive-support packets completed, with zero observed structural/inference failures and no dropped scheduled rows. Encoder window/query truncation counts were zero. Stage receipts were saved atomically at completion; per-packet interrupted-progress persistence was not exercised. Private stage SHA-256 receipts are `f054d97e7569110cd54f23fdc2ce06259dd0cee7f0f572e6a259354b5ea3dbe5` (lexical) and `b1fe514309456b6d1889889ad3bcbe63c3750bc7e3ee7d16292595ef51961557` (dense).

**Execution limitation and protocol correction:** the frozen implementation accumulates rows in memory and saves only after an entire 1,080-cell stage succeeds. An exception aborts that stage without a per-cell failure row or checkpoint, and an absent completed-stage destination permits a restart. It is fail-closed whole-stage execution, not the per-cell failure accounting or interrupted-receipt/resume infrastructure promised in the prospective plan. In this actual run both stages completed without an observed exception, and all 2,160 scheduled rows are present in the complete receipts; no failed/partial stage was retried or substituted. The frozen plan/code and scores remain unchanged. Future interrupted runs would need an explicitly amended persistence protocol before claiming complete failure/resume accounting.

The table shows **queries whose entire publisher-required ID union was exposed as complete adapted original messages, out of 90**. It is not answer accuracy. Each history has 18 queries, so these fractions also equal the predeclared equal-history averages.

| Ranker | Whole 4 KB | Whole 8 KB | Whole 16 KB | Sentence 4 KB | Sentence 8 KB | Sentence 16 KB |
|---|---:|---:|---:|---:|---:|---:|
| `body_bm25` | 22 | 21 | 24 | 20 | 29 | 31 |
| `entity_rrf` | 27 | 25 | 33 | 29 | 36 | 38 |
| `dense_windows` | 15 | 17 | 20 | 15 | 23 | 24 |
| `dense_window_rrf` | 16 | 19 | 20 | 18 | 28 | 29 |

At the fixed 8 KB sentence-neighbor cell, word/character `entity_rrf` has seven gains and zero regressions versus matched body BM25 (36 versus 29 complete bundles). Dense windows have seven gains and thirteen regressions (23 versus 29); dense-window RRF has four gains and five regressions (28 versus 29). Source aliases are empty, so `entity_rrf` here primarily measures word/character fusion rather than a learned entity system. The ordering describes these five synthetic histories; it does not establish a general lexical winner or rule out other dense encoders/representations.

The same 8 KB sentence-neighbor counts by history show the repeated-observation structure explicitly. Each cell is out of 18; full history/category/cell detail remains in the result JSON.

| History (upstream number) | Body BM25 | Entity RRF | Dense windows | Dense-window RRF |
|---|---:|---:|---:|---:|
| H1 (14) | 5 | 5 | 4 | 4 |
| H2 (6) | 6 | 8 | 5 | 4 |
| H3 (7) | 7 | 9 | 5 | 8 |
| H4 (16) | 6 | 9 | 6 | 8 |
| H5 (10) | 5 | 5 | 3 | 4 |

Ranking also limits packing: all declared IDs enter the first 32 candidates for 33/90 body-BM25 queries, 41/90 entity-RRF queries, 25/90 dense-window queries and 31/90 dense-window-RRF queries. At 64 candidates these become 42, 51, 36 and 45. Increasing the candidate ceiling was not used to replace the frozen 32-candidate results.

### Byte ceilings and partial selection

Even perfect ranking cannot fully expose oversized source bundles. The following necessary feasibility counts retain every impossible case in the main denominator. The sentence column uses an optimistic one-whole-body-per-original lean-wrapper lower bound; its extra actual passage wrappers and two-window ceiling can cause further failures.

| Budget | Whole-wrapper bundle can fit | Sentence lower bound can fit |
|---|---:|---:|
| 4,096 bytes | 76/90 | 76/90 |
| 8,192 bytes | 79/90 | 79/90 |
| 16,384 bytes | 82/90 | 83/90 |

Required union costs range from 263 to 29,062 bytes with whole-record wrappers (median 819.5), and 163 to 28,462 with lean wrappers (median 619.5). At 8 KB, entity RRF/sentence neighbors recovers 36/90 whole bundles, or 36/79 among byte-feasible cases. That diagnostic does not remove its eleven byte-infeasible cases from the primary result.

At that same cell, selected-ID bundle recovery is **37/90**, while complete-original bundle recovery is **36/90**. The average recovered fraction of required IDs is 54.1% when partial selections count and 49.0% when complete originals are required; an average 0.30 required IDs per query is selected only partially. Thus the two endpoints are distinct, although this cell's complete-bundle gap is small. Neither selection nor complete-message exposure proves semantic sufficiency without span/entailment labels.

Budget increases are not guaranteed to preserve a greedy whole-record packet. Body BM25 drops from 22 complete bundles at 4 KB to 21 at 8 KB: zero gains, one regression and 89 ties. A source-exact replay of that knowledge-update case verified that additional earlier ranked records fit at 8 KB and displace one required later original. The unchanged implementation was retained; no outcome-driven packing fix or replacement score was introduced.

### Actual dense work and limits

The dense stage created **4,931 document-window vectors** across five histories and encoded **180 queries** (each of 90 strings separately for both dense policies). Vectors occupy 7,574,016 in-memory matrix bytes, excluding model, lexical indexes and cache metadata. All five document indexes were new cache entries; model weights were reused from the verified private cache. One encoder/process served the sequential histories using two CPU threads and batch 12. No new dependency, torch install, authenticated service or provider call was used. These times reflect shared-machine work and are not a controlled latency comparison.

The source labels can overinclude, omit or duplicate relevant semantic evidence. Named groups are preserved conjunctively, not interpreted as minimal alternatives. Whole-message recovery is a conservative exposure proxy; passages can contain useful evidence without covering the whole message, and a whole message can contain misleading or insufficient evidence. The result does not score answers, temporal order, instruction/preference compliance, tool parameter correctness or live execution. There is no query-level uncertainty interval, population-generalization claim, or full-BEAM claim.

## Further falsifiable avenues

Workflow/gotcha/premise memory should be tested as conditional environment knowledge, including failed trajectories and transfer to a changed interface. V2 offers those task categories, but a text-only lane cannot test its screenshot gotchas. Distinguish remembering a rule from recognizing when its premise no longer applies.

Mem2ActBench motivates parameter grounding: recover a specific tool's omitted parameters from history, preserve explicit versus inferred provenance, and detect missing or conflicting evidence before an action. A future run should freeze allowed tool schemas separately from expected calls and keep extracted evolution facts/grounding annotations in the evaluator. Structural call validity, parameter correctness and observed source exposure should be separate outcomes.

A source-linked rollback experiment can replay synthetic corrections against cached runbooks: retain immutable original observations, hash dependencies, invalidate descendants and restore the prior view after an interrupted or rejected update. This tests maintenance mechanics; deriving correct procedures or deciding that a correction is authoritative requires separate semantic evidence. No new workflow, action or rollback outcome is claimed by this retrieval lane.
