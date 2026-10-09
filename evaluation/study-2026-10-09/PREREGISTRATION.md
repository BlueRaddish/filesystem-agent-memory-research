# Filing hypotheses: prospective synthetic pilot plan

The original plan was written before any scored reader trial on 2026-10-09. Two infrastructure attempts were aborted and this plan amended before the final batch; see [execution amendment](EXECUTION-AMENDMENT.md) and retained [first](attempt-1/freeze.json) and [second](attempt-2/freeze.json) freezes. The machine-readable freeze records input hashes, the exact reader prompt hash, randomized order, model, budgets and trial identifiers. Setup canaries and fixture-author structural smoke checks are not scored reader trials. This is a pilot, not a validated benchmark or an independent human dataset.

## Questions and scope

Can a reader with no inherited PARA briefing discover the relevant records, preserve corrections, exceptions and uncertainty, edit a local artifact correctly, and run its required check after the final edit? Does filing structure help under two declared resource regimes? Accuracy takes priority over token economy. An incorrect fast answer is not a successful continuation.

The pre-existing [H1–H8 hypotheses](../../research/filing-hypotheses.md) motivate the interventions. H1/H2/H8 receive four fictional case families each; H3/H5/H7 receive two each. H4/H6 receive deterministic file evolution replays, separated from model-performance evidence. The 18 reader families are clustered by two independent LLM fixture authors. They are independently audited, but are not independent real-world samples. No personal vault content is used.

## Design fixed before execution

| Hypothesis | Baseline / comparison | Treatment | Families |
|---|---|---|---:|
| H1 | Original sources only; same unlinked current view | Current view with precise origin pointers | 4 |
| H2 | Equal-length generic record headers | Problem/scope/alias headers with identical source bodies | 4 |
| H3 | Fixed-window index passages | Coherent event capsules containing the same source words | 2 |
| H5 | Generic date/retention headers | Source-derived current-eligibility headers | 2 |
| H7 | Unlinked prerequisite references | Explicit bounded dependency links, including a cycle and missing prerequisite | 2 |
| H8 | Prose obligations | Structured obligations containing the same facts | 4 |
| H4 | Independently stored copies | Canonical records and project references, with prescribed repairs | replay |
| H6 | Handoff and fixed-period schedules | Update-triggered maintenance under the same attempt cap | replay |

Forty reader case-condition pairs run once in each regime: 80 principal trials. No selection of best retries, model switching, or outcome-dependent cap changes. Regimes are distinct conditions, not independent replications of the same experiment.

| Regime | Maximum reader calls | Maximum actions | Nominal returned tool-byte cap |
|---|---:|---:|---:|
| matched | 6 | 24 | 12,288 |
| fidelity_first | 12 | 72 | 65,536 |

Each response can request at most six sequential actions. Full-file reads that cannot fit are refused, never silently reported as complete. Error/control envelopes can add a small final byte-cap overshoot; disclose observed totals. All arms receive the same lexical list/read/search/write/check tools. The higher budget does not itself tell the reader to consume all available evidence.

Six additional exploratory onboarding trials use the first H1 source-only, H2 generic-header and H8 prose-obligation family in the fidelity-first regime. Each is tested with its START.md entry removed and with a layout briefing added. The principal unbriefed run serves as the separate reference. These three-family comparisons cannot establish general onboarding reliability. Every principal trial already begins without an inherited PARA explanation or conversation.

The 86 jobs are shuffled with seed 1009 and processed by **six concurrent workers in the final batch**. Six simultaneous high-effort synthetic transport canaries passed before scoring; this short burst does not establish sustained throughput or future rate limits. The two aborted batches used three workers. Reader: `muse-spark-1.3-contributor`, **high reasoning effort in the final batch**, using the existing authorized native Muse login. The two aborted attempts used low effort. High effort follows the user's accuracy-first priority; no low-versus-high filing effect is inferred from infrastructure failures. Calls use fresh rootless ephemeral SDK sessions. Within a trial, prior explicit reader actions and synthetic tool observations are replayed in the next fresh call; unrelated sessions are not supplied. There is no provider continuation identifier. See [reader controls](READER-CONTROLS.md) for enforced boundaries and unproved provider-memory assumptions.

The reader never sees case IDs, hypothesis labels, author names, gold, repository paths, builders, previous trial outputs or hidden check expectations. H2 drafts do not give the target project name; every artifact uses `artifacts/result.json`. Source files are read-only. Only the artifact is writable. The host executes a finite allowlist of trusted structural checks in a disposable synthetic directory. No external action or arbitrary shell is available through the action protocol. Muse's advertised native to-do bookkeeping is allowed inside the current fresh session. Hallucinated unadvertised native functions are accepted as recoverable errors **only when the host proves they failed with the exact unknown-tool error and returned no collection data**. They are counted, never executed by the harness. Every other non-bookkeeping native action invalidates the call. The prompt identifies the collection tools as virtual JSON formats. This explicit infrastructure amendment does not give access to files, other sessions or account history.

## Outcomes and scoring fixed before execution

The primary outcome is **complete task**, requiring all of:

1. The artifact was actually written.
2. Every expected domain/history/obligation field is correct, with preserved unknowns. Expected keys are compared; extra keys still face the local schema check. H2 project-name wording is excluded because some generic originals do not expose the treatment's exact label. The correctly scoped configuration is scored instead.
3. Required governing IDs are cited; extra valid citations and evidence ordering are not penalized. Audits remove redundant hard requirements. Merely listing an ID does not prove it was read.
4. The required check really executed with its expected exit code after the final write. An edit after a pass invalidates that receipt.
5. No prohibited write, native action or untriggered/canceled local-check request occurred. Attempted and executed forbidden actions are separate metrics. Banned image/legacy/external modes are local test modes; attempting one is not evidence of a real upload or physical action.
6. A required hold is preserved with a focused question. Questions are not exact-string matched. The predeclared focus cues are gain for Orris, unit or basis for Feldglass, retention for Ledger, and calibration or scale for Raster. This shallow lexical rubric is a limited proxy for semantic question quality; inspect actual questions in the report. Secondary ready artifacts may include genuinely unresolved nonessential details without being penalized.

The separate **critical gate** checks all explicitly declared authority, safety, unknown and correction fields plus focused-question behavior. It is not a substitute for the fuller artifact comparison. Quillspan's accepted stop list is critical because an obsolete closed stop would pass a structural route checker.

We also report semantic-artifact correctness, required citations, actual writes, post-write checks, required-origin full-read coverage, returned bytes, calls, actions, wall time and numerical token usage. Original-read coverage is a discovery proxy: index passages, search snippets and derived views can contain sufficient facts, so complete original reads are **not** an additional correctness gate. Corroborating origins remain retained even when not part of the minimum citation set. The reader's completion summary is not execution evidence.

Infrastructure failures, invalid JSON responses, resource exhaustion and partial artifacts remain in the scheduled-trial denominator and are also separated. A failed native call is not automatically a reasoning error. No scored retries after inspecting gold. Any unexpected harness defect must be disclosed; do not quietly replace an affected run.

## Analysis and interpretation

Report counts with denominators, paired family outcomes, observed field-level errors and traces. Results are descriptive. No family-level universal rankings, significance claims, independent-trial confidence intervals or inference from repeated calls as independent samples. A treatment gain of at least ten percentage points in complete-task rate is a practical screening signal, not validation. Ceiling results or zero differences are inconclusive about difficult long-horizon work.

H1's linked/unlinked view prose is matched except source pointers; the source-only arm intentionally lacks the view. H2 headers match UTF-8 byte lengths, not tokenizer costs; cues include authored synonyms rather than only source-attested aliases. H3 retains originals and duplicates identical source passage words; boundary effects and returned bytes are reported. H5 metadata is manually derived from source truth, so it does not test automatic metadata extraction. H7's tools do not force link-following or cap traversal depth separately from the general action cap. H8's structured formatting tests representation, not a general obligation executor.

H4 reports indexed separator-rule access, divergence and prescribed file mutations. It does not measure a maintainer's ability to discover repairs, complete inherited state or reader correctness. H6 performs actual file writes, bounded source inspections and atomic view commits, including an interrupted candidate and missed dependency. Different schedules expose different source versions. This is a whole-policy mechanical replay, not timing alone or LLM maintenance efficacy. Retained versions are guaranteed for governing sources; the irrelevant decorative source is overwritten.

All public fixtures and observations are fictional. Publish synthetic prompts, action traces, artifact hashes, numerical usage, controls, scoring and figures; exclude private authentication, local bridge paths, account/session identifiers, raw transport logs and hidden reasoning. The report must distinguish what ran from what remains a proposal.

## Reproduce

Run `python evaluation/study-2026-10-09/run_study.py selfcheck`. Supply a private JSON array containing a compatible reader command, then run the `run` subcommand with `--reader-command-file`, an empty `--work` directory and `--output`. The checked-in freeze pins this pilot's data/code/prompt. Different adapters must report their own actual tools and memory controls rather than claim the Muse controls by analogy. Maintenance and plotting scripts have their own documented commands.
