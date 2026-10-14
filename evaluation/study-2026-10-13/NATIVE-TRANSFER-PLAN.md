# Native deterministic BEAM transfer: prospective supplement

**Designed and source-audited after the main study freeze; scoring NOT EXECUTED.**
This lane tests whether the already frozen deterministic lookup methods recover
publisher-declared original messages in additional externally generated histories.
It changes no primary study input or score. It is a separate synthetic-data
adaptation, not a human-history benchmark, answer evaluation, official BEAM
reproduction, semantic truth test or SQLite token-speed claim. No model, provider,
native Muse call or main authored-bank data/outcome is used.

## Fixed source and selection

The [official BEAM repository](https://github.com/mohammadtavakoli78/BEAM/tree/b2da22eac88bb0874c64665f13457eb99835774a)
is pinned at `b2da22eac88bb0874c64665f13457eb99835774a`. Its
[README](https://github.com/mohammadtavakoli78/BEAM/blob/b2da22eac88bb0874c64665f13457eb99835774a/README.md)
identifies synthetic conversation/question generation and distinguishes MIT code
from CC BY-SA 4.0 benchmark data. The [paper](https://arxiv.org/abs/2510.27246v2)
provides provenance, not a reproduced endpoint. Source text and adapted packets
remain private; this package publishes attribution and file fixity, not raw data.

Reuse the original external lane's complete twenty-path `chats/100K/*/chat.json`
frame and order ascending by `SHA256("external-beam-20261013-v1:" + path)`, then
path. Exclude its original first five histories, 14, 6, 7, 16, 10. Take the next
up to twenty in that same frame: only **fifteen** remain, ordered
**19, 8, 17, 15, 9, 18, 2, 13, 5, 20, 3, 4, 11, 1, 12**. Do not fill from larger
context frames or tune this selection to any old or new retrieval result.
History 1 had an earlier convenience schema audit; that exposure is disclosed.
The original five scored histories are excluded and will not be pooled here.

All thirty chat/question artifacts plus README/LICENSE are actually available
and prefetched without retrieval. The complete pinned publisher tree matches
the earlier tree entries; every file matches its declared byte count and Git
blob SHA-1, and actual SHA-256 is retained in
[native-transfer-sources.json](native-transfer-sources.json). Chat/question files
total 10,606,006 bytes; each chat is under one megabyte. There are 188–392 source
messages per selected history. No pickle, remote code, installer or new dependency
is used.

## Label availability before engines

The initial estimate of 270 valid positive questions plus thirty unlabeled
abstentions **failed the source/schema doctor**. All fifteen histories and all
300 questions remain in the audit. The immutable publisher files contain:

| Question class | Questions | Nominal packet rows |
|---|---:|---:|
| Valid nonempty, resolved positive support groups | 264 | 6,336 |
| Empty non-abstention support | 5 | 120 |
| Nonempty union with an empty named criterion group | 1 | 24 |
| Unlabeled abstention, audited outside the retrieval grid | 30 | 0 |

The five empty labels are history 9 preference-following question 2 and both
summarization questions in histories 18 and 20. History 12 knowledge-update
question 1 has an empty named group. Their answers or source text are not used
to invent replacements. Freeze these six query identities and mechanical
classifications before outcomes. Validity requires a nonempty query string,
integer nonboolean publisher message IDs, resolved distinct original IDs,
nonempty support union and every named group nonempty. Plain lists form one
group; named groups remain conjunctive. Duplicate source message IDs are rejected.
Repeated support IDs denote one original message.

Preserve **270 nominal non-abstention tasks, 1,080 engine jobs and 6,480 packet
rows**. The six unscorable queries have 24 explicit skipped engine jobs and 144
`label_unscorable` packet rows, with null metrics and no retrieval attempt. These
are separate from retriever/infrastructure faults and genuine native zero hits.
There are 264 mechanically scorable queries and 1,056 scorable engine jobs.
The thirty abstention questions, five other missing labels and one malformed
group retain separate census identities. No absent label is scored as an answer
failure, zero recovery or successful abstention.

## Observable projections and unchanged algorithms

[native_transfer.py](native_transfer.py) reuses the unchanged
`external_eval.project`, `criteria`, `measure` and packing helpers, and the
unchanged `native_index_lab.NativeIndex`, `NativeTokenizer`, `build_indexes` and
`rank_step`. Their exact source hashes are bound before import and in the private
manifest. The original main-bank loaders/scorers and previous external results
are not invoked. Each history has its own database, source ledger, reference
index and checkpoint directory; identical publisher IDs across histories cannot
mix.

One original message is one source record, ID `M` plus six zero-padded digits.
The adapted body remains exactly `time_anchor: JSON_VALUE\nROLE: CONTENT`, with
the original content and nullable message/batch time anchor. Fixed adapter
metadata is revision 1, source kind, blank title/authored_at, scope `all`, and
empty aliases/links/supersedes/incorporations. No profile, plan, question-type
construction marker, question, answer, rubric, rationale or support label is
added to the sources. Native ID/revision columns are UNINDEXED identity metadata.

Body retrieval indexes the adapted body. Both search representations are exactly
`"\n".join([blank_title, "all", adapted_body])`; the fixed `all` token is not a
gold cue. Native vocabulary/scoring and custom BM25 tokenization/scoring differ.
Only a string question crosses ranking and packing; Windows-safe opaque query
IDs are checkpoint identity, not features. Category/support groups stay in the
evaluator. Label metadata changes cannot alter the source/search projection.

| Engine | Existing rule |
|---|---|
| `fts_body_or` | SQLite FTS5 body, unicode61 remove_diacritics 2, native terms quoted and OR-combined, bound MATCH, ascending native bm25 then binary ID. |
| `fts_search_or` | Same native rule over the existing search projection. |
| `body_bm25` | Existing custom body BM25, k1 1.2 and b .75. |
| `search_bm25` | Same existing custom BM25 over the existing search projection. |

There is no AND arm or new normalizer. Native all-matching rows remain bounded
by at most 392 messages here; the frozen implementation's full fetch is not a
production scalability claim. Native nonhits are never tail-filled from other
records. Keep the first at most 32 matching candidates; custom references return
every message once before that truncation. The inherited one warmup plus three
repeated rankings checks repeat agreement. All clocks are operational receipts
under concurrent shared-host activity, not controlled speed comparisons.

Cross the four engines with unchanged `whole_record` and `sentence_neighbors`
at 4,096, 8,192 and 16,384 UTF-8 bytes. No new packing heuristic, window ceiling
or outcome tuning is introduced. Count wrappers and separators; preserve Unicode
character offsets, original-source hashes and exact packet bytes. Empty native
matches produce a real zero-byte packet with zero recovery for valid labels.

## Endpoints and denominators

Retain the earlier publisher-ID proxy endpoints: all required IDs recovered as
complete original-message bodies; required distinct-ID fraction; complete
criterion-group fraction; weaker selected-ID bundle/fraction; partial selected
IDs; byte use; and candidate all/any/fraction at 8/16/32/64. Adjacent exact
observations may jointly expose a complete adapted message. An ID hit or partial
passage does not establish answer-bearing evidence. No minimal-span, QA, entailment,
natural-history or human-validity endpoint is claimed.

Reuse the exact whole-message bundle wrapper cost. It is exact for whole_record
and an optimistic one-body/lean-wrapper lower bound for sentence_neighbors;
additional wrappers and its two-window ceiling can prevent complete exposure.
Impossible bundles remain in the valid-label denominator. Feasible-only results
are explicitly conditional diagnostics.

Future aggregation first reports questions available and label validity before
engine results. Keep nominal history/category denominators alongside scorable
and fault-free denominators. Histories 9 and 12 have seventeen valid positives;
histories 18 and 20 have sixteen; the other eleven have eighteen. Average histories
equally and separately report query-weighted results. Each category has thirty
nominal questions; valid counts are preference 29, summarization 26, knowledge
update 29 and thirty in each other category.

Valid-label algorithm faults remain scheduled, with null per-row metrics and
explicit failed-workflow counts. Verified recovery numerators are divided by
all scheduled valid-label questions; fraction/boolean lower and upper bounds
show unresolved fault contributions rather than assigning invented numeric row
values. Fault-free metric means and feasible-only diagnostics name their actual
denominators. Label-unscorable rows never enter the valid-label recovery endpoint.
Paired differences versus body_bm25 use the same history/packer/budget; paired
gains/ties/regressions use only pairs with two measured packets and disclose
missing pairs. No query-independent confidence interval or population winner is
inferred from these clustered synthetic histories.

## Freeze, persistence and verification

`--doctor --work PRIVATE_ROOT` verifies source bytes, projections, label census,
code and SQLite runtime/FTS5 availability without building actual history indexes
or ranking. `--prepare` writes a new private manifest only; it binds the exact
plan/runner/ledger/dependencies, dataset files, deterministic schedule, source/
query/label hashes, engine/packer/budget controls and runtime. Root independently
reviews and publicly freezes these bytes before issuing a private exact-manifest
clearance. The author/helper never creates clearance. No scored `--run` or
`--aggregate` is authorized during this design/doctor task.

Future `--run --manifest-sha256 HASH` requires that clearance and an exclusive
local coordinator lock. One worker processes histories sequentially; the lock
does not coordinate another host. Explicit `--resume` is required after a started
run. Inputs/runtime/source changes and recorded checkpoint-hash changes reject.
Ranking reuses the original pending/sealed cache and retains errors/unknown
interrupted calls without retry. Each packet has its own pending marker, sealed
row, exact rank/manifest/label identity and independent validation; an interrupted
packet becomes a retained fault, not a silent rerun. A validated completed row
saved just before interruption may be recorded as recovered on explicit resume.
Build/reopen/source-ledger faults are retained; an interrupted initial preparation
receives an explicit unknown-preparation receipt. No whole-stage overwrite or
automatic retry is used. Failure receipts and raw diagnostics remain private.

Completion requires exactly the 1,080 engine jobs and 6,480 packet identities,
including skipped labels and operational faults. Aggregate output is private and
allowlisted; raw chats, question/answer/support text, packet text, absolute paths,
credentials and native traces are never published. Root separately reviews any
later public summary. A separate preparation census records the latest sealed
tokenizer, per-history index-stage, native-build, reopen/source-integrity and
reference-preparation statuses. Downstream preparation receipts absent after a
stage fault are explicitly `not_reached`; receipt history remains private.

Verification uses the repository route `python scripts/check_repository.py` and
this runner's one stdlib `--self-check`, exercising the reused consuming functions
with fictional normal/failing fixtures, source stripping, Unicode offsets,
zero hits, label-unscorable nulls, pending/cache/no-retry behavior, packet/source
tampering, checkpoint changes and clearance rejection. It also drives a complete
fictional coordinator/aggregate census, cached completion and interrupted resume;
the per-file `recorded_file_sha256` map remains distinct from the native
`checkpoint_sha256` seal. Unequal-history fixtures check the separate query and
equal-history denominators and unresolved-fault bounds. Such fixtures and compile/
source checks do not establish actual transfer results. Actual history retrieval,
6,480-row persistence/resume, aggregate and scientific outcome audits remain
unreached until the separate reviewed run.
