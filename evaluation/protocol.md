# Protocol: accurate continuation by an unfamiliar agent

**Status:** proposed experimental protocol, not completed benchmark results. The included fictional fixture is an illustration and harness check, not a validated benchmark. The primary objective is material correctness; tokens, latency, and maintenance are secondary measurements.

The [2026-10-09 pilot report](study-2026-10-09/REPORT.md) records actual bounded experiments, with an [independent reconstruction](study-2026-10-09/AUDIT.md). It distinguishes operationally fresh local sessions from unproved remote unfamiliarity, keeps setup failures and selected follow-ups separate, and discloses scoring underspecification and a transport defect. It does not establish that all of this protocol's ideal controls were achieved or that the corpus is a validated benchmark.

## 1. Specify what success requires before testing

Choose concrete tasks with observable outcomes: recover a current decision, explain a historical change, diagnose a failed attempt, update a local artifact, or continue unfinished work. Have an evaluator identify the required facts, governing sources, temporal order, scope, disallowed actions, necessary checks, and legitimately unknown details before running the reader. Annotate minimal sufficient evidence sets, including valid alternative sets, separately from useful supporting context. Do not penalize a correct grounded answer for omitting a redundant source.

Label each requirement as critical or ordinary in advance. A critical error should fail the relevant task rather than disappear inside a high average recall score. Examples include applying a superseded instruction, exposing a forbidden artifact, or claiming a verification that failed. Keep historical and current-state questions separate.

Audit the answer key against the actual source records, including message-level ordering inside a single session. A session date or file modification time is not enough to resolve two corrections within that record. Record ambiguous gold labels and exclude or adjudicate them transparently rather than silently changing the key after seeing outputs.

## 2. Make the fresh condition genuinely fresh

Use a new agent session with no prior conversation, saved memory, layout tutorial, task-answer examples, or knowledge of the particular collection. The generic task prompt can explain tool availability and authorization; it should not name hidden locations or tell the reader which source is decisive.

Stage only the memory condition and the task in an isolated workspace. Keep gold evidence lists, expected outputs, graders, builder scripts, and prior runs outside the agent's accessible filesystem. A prompt saying "do not read the answer key" is not an isolation mechanism. Disable inherited history and retrieval integrations; restrict file access and networking so the agent cannot obtain the public fixture's answer key from the original repository. Record the actual enforcement method.

The fixture staging script copies a small allowlisted set of files and excludes evaluator materials. It does not sandbox the agent, clear provider-side memory, or prevent access elsewhere. Those controls belong to the execution harness. If they are missing, label the trial a leakage-prone demonstration rather than a cold-start result.

Run two discovery conditions: a discoverable entry point and a collection without that entry point. Also compare a schema-taught reader as a separate onboarding intervention. Do not call a reader familiar with the collection "fresh" merely because it uses a new process.

## 3. Compare minimal memory conditions

| Condition | Agent receives | What the comparison can diagnose |
| --- | --- | --- |
| Source-only | Original evidence records and basic file tools | Baseline discoverability and reading |
| Brief-only | Current-state brief, no original evidence | Consolidation loss and unsupported projection authority |
| Sources + brief | Both, with explicit source links | Whether projections improve navigation without sacrificing fidelity |
| Sources + brief + lexical index | Same evidence, exact-term retrieval | Known-item and rare-identifier recovery |
| Sources + brief + hybrid/link expansion | Same evidence, additional access paths | Paraphrase, dependency, and cross-project recovery |
| Full context | Entire condition evidence in the prompt | Retrieval omissions versus interpretation/distraction |
| Oracle evidence | Evaluator-selected necessary evidence | Reader/action failures with privileged discovery removed |

Treat oracle evidence as a diagnostic reference condition, not a deployable system or a guaranteed accuracy upper bound. No oracle annotations enter ordinary retrieval. Separate the experiment that changes organization from the experiment that changes tools or prompts; otherwise the intervention is confounded.

Use a matched reader, source corpus, task, tool behavior, and resource cap for component comparisons. Also run a fidelity-first condition allowing additional retrieval until an explicit stopping policy is reached. Report both; neither budget setting answers every practical question.

## 4. Include difficult cases deliberately

- A late correction and an earlier decision in the same record, with source positions available.
- A recently rewritten brief incorporating only older evidence.
- A narrow exception alongside a broad rule.
- A proposal that was declined or never executed.
- A success claim contradicted by a recorded tool result.
- Two differently worded records needed for one dependency.
- A real unresolved conflict between sources of comparable authority.
- A missing fact that should elicit a focused question or abstention.
- A historical question requiring the old version rather than today's answer.
- A renamed folder, cross-project association, irrelevant near-duplicate, and archived distractor.
- An interrupted publication or an index lagging a committed correction.

Scale from controlled fictional tasks to independently authored public or consented datasets. Vary distractor relevance and position, history length, correction frequency, and metadata completeness. Do not assume that adding random text captures the difficulty of plausible obsolete evidence.

## 5. Record separate measurements

| Layer | Suggested measurement | Important boundary |
| --- | --- | --- |
| Preservation | Required facts and qualifiers present; unsupported additions; recoverable source links | A fact's bytes can survive without a usable interpretation |
| Discovery | Necessary-source recall; complete evidence-set coverage; discovery success; tool calls | Top-k relevance alone misses distributed dependencies |
| Interpretation | Correct authority, chronology, scope, historical reconstruction, and abstention | Citation presence is not causal evidence use |
| Action | Artifact requirements satisfied, checks actually run, forbidden-action count, verified continuation | Prose success claims are not execution evidence |
| Maintenance | Correction propagation, stale-projection duration, broken links, revision effort | A well-organized final snapshot can hide costly repairs |
| Resources | Input/output/tool tokens, latency, ingest work, storage and human review | Report alongside fidelity, not as its substitute |

Use claim-level scoring with explicit evidence IDs and applicable slots. Report macro and task-level results, critical-error counts, complete-task success, failure categories, and unanswered items. Keep partial credit visible. One missing critical constraint can matter more than several correct incidental facts.

For artifacts, inspect the generated bytes and actual tool outcomes in the authorized sandbox. If the task requires a test, capture its command, exit status, and output. Separate "the agent said it checked" from "the harness observed the check." Use blinded human adjudication for disputed semantic judgments where feasible; publish judge prompts and calibration if model grading is used.

## 6. Control comparison and reporting risks

Freeze source versions, source/fixture hashes, reader model identifier/date, prompt, tool implementations, retrieval settings, resource limits, and stopping rules. Repeat trials with recorded seeds where supported and different distractor placements. Preserve failed and interrupted runs in denominators with explicit reasons. Do not report a selected best attempt as typical performance.

Keep ingest, maintenance, retrieval, and answer-generation costs distinct. A memory condition should not secretly receive more source evidence than a competitor. Cross-paper headline comparisons are background evidence, not matched experimental results. Disclose dataset overlap and benchmark familiarity risks.

Use confidence intervals and effect estimates appropriate to the unit of independent variation once a sufficiently sized experiment exists. The tiny fixture here cannot estimate general model performance. Preregister the primary outcomes and materially meaningful improvement threshold before collecting a larger comparison.

## 7. Diagnose failures before reorganizing

For each material error, inspect whether the governing detail existed in durable memory, appeared in fetched evidence, was interpreted correctly, and was acted on with verification. Record multiple causes when the layers interact. Repeat with oracle evidence to isolate discovery from later failures, without leaking the diagnostic answer into the original run.

After a proposed filing change, rerun the same held-out tasks and add new independently authored tasks. A design tuned to a few known traps can appear successful while failing ordinary unfamiliar work. Prefer the smallest intervention that fixes a repeatable failure without introducing critical regressions.

The project's [fictional example](../examples/README.md) illustrates this protocol's boundaries. Passing its deterministic repository checks demonstrates a coherent fixture and safe staging behavior. It does not demonstrate that any agent has completed the tasks.

## 8. Test translations from biology and human practice

The [transfer review](../research/brain-agent-transfer.md) specifies proposed comparisons for episode-plus-state views, distinctive cues, retrieval probes with source feedback, maintenance timing, discrimination among similar records, and reminders for future obligations. No new agent experiment is claimed by those proposals.

The [filing hypotheses](../research/filing-hypotheses.md) develop eight concrete interventions, including boundary selection, canonical shared records, current eligibility and dependency expansion. They specify negative tests and disconfirmation, with critical errors and full maintenance effort reported separately from search savings.

Keep the learner and mechanism clear. Human retrieval-practice results concern changes in a person; fixed-model external-memory maintenance must identify the records, indexes, prompts or policies it changes. For a maintenance comparison, keep the reader fixed and compare matched interventions, then test with a fresh reader on withheld tasks. Record every repair and its supporting evidence.

Maintenance prompts and final tests must be separately authored. Do not leak final answer keys through a rehearsal process. Evaluate new formulations and combinations, and include a project or scope not seen in maintenance. Use an equal-budget summary-writing or inspection control to distinguish source-feedback benefits from additional work.

For scheduling, match review counts and evidence availability while varying placement around updates and handoffs. Calendar delay alone is not evidence of a human-like spacing effect in static files. Measure correction lag and downstream obsolete-rule use. For source/context cues, use text-length-matched controls and near-duplicate distractors. For reminders, inspect actual trigger handling, local checks and resulting artifacts; remembering an obligation in prose is a separate outcome from completing it.

Describe a successful result as evidence for the tested implementation and task. It does not validate the biological analogy, prove that an agent has human memory, or establish a universal policy for all collections.
