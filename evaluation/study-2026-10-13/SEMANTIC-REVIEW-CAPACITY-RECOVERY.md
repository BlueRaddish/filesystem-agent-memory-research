# Prospective supplemental semantic-review execution recovery

This amendment changes execution grouping before any recovery reviewer is
created. It preserves the original [semantic review plan](SEMANTIC-REVIEW-PLAN.md),
rubric, cases, opaque identities, saved judgments and primary endpoints. The
original three-context capacity plan did not complete. This is a recovery plan,
not a semantic result or a claim that the proposed smaller groups will fit.

## Observed stop boundaries

The three original contexts received disjoint partitions of 64, 63 and 65 cases.
Structural execution audits retained 10, 38 and 37 saved per-case judgments,
respectively: **85 retained judgments and 107 unjudged cases**. The audit checked
schema, case/hash bindings, citation coordinates and complete model-visible case
delivery before each exclusive output write. These checks do not establish
semantic correctness; descriptive semantic aggregation and publication remain
pending.

The first context stopped with `server_overloaded` three times across its
original attempt and two explicitly authorized recoveries. Its 10 saved
judgments remain retained, together with all failed native prefixes and the
original directory-creation protocol deviation. The backend message does not
establish context capacity as the cause. There will be no further resume of
that context under this amendment.

The second and third contexts stopped themselves after observed compaction
during an unfinished case. Their 38 and 37 saved judgments all preceded
compaction. Neither produced a new case frame or judgment after compaction.
The unfinished cases had only 10 of 13 and 6 of 7 chunks delivered; the first
context's unfinished case had only 4 of 7. No judgment from any of those partial
reads is retained. Every such case will restart at chunk 1 in a new context.
All original saved files, scope/completion records, input indices, case files
and failure prefixes remain unchanged. A partial or stopped task is not
reported as a clean completed review.

## Prospective assignment rule

Only the unjudged complement of each original partition is eligible. The 85
retained case identities are excluded from new assignments without inspecting
their labels or rationales. There is no rerating, outcome-guided selection or
exchange of cases across original partitions.

Each new context is capped at **450,000 original case UTF8 bytes and 18 cases**.
Within each old partition, sort remaining index records by decreasing byte
size, then ascending case ID. Start with the larger of the byte-cap and
case-cap lower bounds on group count. Place each record into the eligible
group with the least assigned bytes, breaking ties by group number. If a
placement fails, increase the number of groups and restart. An individual
case above the byte cap is a refusal requiring a further prospective decision.
This deterministic greedy rule is not a minimum-bin optimizer.

The sealed structural boundaries and unchanged indices produce this proposed
assignment, fixed before new judgments:

| Original partition | Retained | Remaining | Remaining case bytes | New contexts: cases / bytes |
| --- | ---: | ---: | ---: | --- |
| 1 | 10 | 54 | 1,433,157 | 12 / 357,120; 14 / 358,823; 14 / 359,120; 14 / 358,094 |
| 2 | 38 | 25 | 728,895 | 13 / 365,924; 12 / 362,971 |
| 3 | 37 | 28 | 800,336 | 14 / 401,191; 14 / 399,145 |
| Total | 85 | 107 | 2,962,388 | 8 new contexts |

Thus the revised execution plan has **11 contexts in total: the original three
plus eight new contexts**, with at most three new contexts active concurrently.
This counts initial contexts, not each failed turn or authorized resume as a
new independent reviewer. Group identifiers and assignments are saved privately
before launches. The stager launches no tasks and makes no provider calls.

## Inputs, transport and write boundaries

Each new input folder contains only its subset index, byte-identical indexed
case files, the unchanged opaque-case reader, the unchanged frozen rubric and
group-scoped operating instructions. The generic helper and literal PowerShell
here-string transport pattern are reused. Cases are copied as strict UTF8 raw
bytes; their literal JSON fields and values are neither parsed nor rewritten by
the recovery stager. Each new index records the original case IDs, byte counts
and case hashes. All 204 original staged input pins are verified before and
after staging. No original file is edited, moved, deleted or overwritten.

New input/output projections use a create-new sibling root, refuse linked or
reparse paths and unsafe index names, and keep each reviewer's output leaf
absent until that reviewer creates it once. The output parent is precreated.
Existing leaves and failed partial staging directories are stop conditions,
not implicit retries. Retained saved-output hash records come from the sealed
structural receipts; staging checks their current filename, size and timestamp
snapshots without opening judgments. Root separately owns saved-byte fixity and
native execution acceptance.

Reviewers use complete numbered list pages, then ascending case IDs. Every
current case requires all of its chunks before a judgment. Payloads remain at
most 4,096 UTF8 bytes each, with at most two frames per tool output and an output
budget of at least 12,000 tokens. Only ASCII Python source passes through the
literal shell pipeline; captured case-frame bytes use `stdout.buffer` with
strict UTF8 validation. A missing, malformed, changed or truncated display, or
compaction that makes the complete current case unavailable, requires stopping
and reporting. No silent retry, summary substitution, case skipping or partial
judgment is authorized. Fresh reviewers receive no prior judgments or partial
read summaries.

Authored answers, conditions, primary scores, the private mapping, bank and
native diagnostics stay withheld from reviewers. Visible source/task IDs,
content and policy strings can still cue assignments; opaque IDs do not prove
condition concealment. Instructions restrict reads but do not create an
enforced filesystem sandbox. Actual inherited model/effort, lineage, ordinary
instruction classes, observable parent material and compaction must be recorded
honestly; unavailable facts stay unknown. No model override is proposed.

## Acceptance and limits

The four labels, original-only Unicode citation coordinates and exact per-case
JSON schema are unchanged. New judgments are exclusive create-new files in
separate output folders and are saved before the next case is read. Root must
independently audit complete native frame census/payloads and saved bytes before
accepting them. Final messages, local hashes and staging success do not prove
complete model-visible delivery.

After all required outputs pass execution and mechanical validation, the 85
retained and 107 new judgments may be combined by the unchanged original case
identities and input hashes for a complete 192-case census. Original preparation
and partition indices remain the authoritative identity set. No key access,
unblinding or descriptive aggregation is authorized by staging alone. Semantic
review does not regrade the frozen primary study scores.

The smaller byte/count caps are a prospective operating heuristic, not a
verified token or context-capacity bound. The new contexts inherit the same
model route; they provide no independent model-family validation. Each case
still receives one judgment, with no duplicate-rating reliability estimate,
human adjudication, empty-prefix claim or remote-erasure claim. Adding contexts
also changes shared within-context exposure, which must be disclosed alongside
any eventual descriptive semantic results. No cross-context independence or
causal comparison is inferred.

Publish and accept this amendment before creating recovery reviewer tasks.
Root separately reviews the exact staged manifest and launch prompts before
launch. Further failures require retained evidence and an explicit decision;
this amendment supplies no automatic retry or further splitting policy.
