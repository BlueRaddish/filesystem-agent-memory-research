# Independent reconstruction and adjudication audit

This audit concerns the final 2026-10-09 fictional pilot. It reconstructs the frozen scoring and then explains convention-sensitive failures. It does **not** replace the scores, validate a production filing system, or establish general treatment effects. The secondary fixture author also performed this audit; the adjudications are an unblinded LLM review, not independent human labels or a held-out adjudication dataset.

The public [results](results.json) exactly match the 86 completed synthetic receipts. There are 86 distinct scheduled IDs, 80 principal unbriefed runs and six exploratory onboarding runs. No final-batch retry was substituted. The earlier aborted batches remain separate in [attempt 1](attempt-1/aborted-results.json) and [attempt 2](attempt-2/aborted-results.json), with their freezes and source snapshots. Their missing final receipts and rejected provider work must not disappear from execution history.

## Reconstruction

An independent standard-library calculation checked every final row against the frozen case, selected condition and action events. It reconstructed expected-field mismatches, critical assertions, the declared lexical focus rubric, exact citation subsets, final writes, successful authorized checks after the final write, successful full-read paths and origin IDs, returned bytes, action/call caps and combined scoring gates. It found **zero inconsistencies**. All frozen file hashes still match. [adjudication.json](adjudication.json) pins the audited inputs and retains the original failures alongside the sensitivity labels.

The write receipt hashes logical UTF-8 text with LF newlines. The check receipt hashes physical file bytes, which contain CRLF on this Windows host. Reconstructing the CRLF transformation reproduces the physical check hash for every final-write check. These are different hash conventions; their differing digests do not indicate an intervening writer.

| Observed metric | Principal, 80 | Onboarding, 6 | All, 86 |
|---|---:|---:|---:|
| Frozen complete-task gate | 60 | 5 | 65 |
| Frozen gate plus protocol clean finish | 57 | 5 | 62 |
| Actual artifact written | 78 | 6 | 84 |
| All required checks passed after final write | 78 | 6 | 84 |
| Exact required-ID citation gate | 74 | 5 | 79 |
| Required-original full-read coverage proxy | 79 | 6 | 85 |
| Successful check result supplied to a later reader call | 69 | 6 | 75 |

Here a **protocol clean finish** means the artifact passes the stated gate, `termination` is `reader_done`, and there is no infrastructure error. It does not add a receipt-inspection criterion. The later-call measurement proves that a successful result was included in a subsequent prompt; it does not prove attention, comprehension or correct source use. A stricter all-required-check-modes version has the same observed count, 75/86, in this dataset. Full original reads are a discovery proxy, not a correctness gate or a measure of recall truth.

The host recorded 127 authorized artifact-write events and 194 executed checks, all with exit 0. Repeated checks are not independent successful tasks. No forbidden virtual attempt or execution was recorded. Unavailable native attempts are separate from that virtual-tool metric.

## Uniform post hoc sensitivity rules

These rules were formulated after observing the failures. They apply uniformly to all 86 rows, preserve actual writes/checks and forbidden-action gates, and are **descriptive sensitivity analysis**, not a new preregistered benchmark score. Their semantic judgments are limited to this small authored corpus.

1. **Completion label:** treat `complete` as `ready` only in a non-abstaining secondary task whose instructions/checker specify a status string without supplying that exact ready/blocked convention. All other source-derived values and completion requirements still have to pass. This does not relax a genuine required hold.
2. **Record and section citation:** recognize `ID:S<number>` as citing its bare record ID only when both that ID and section exist in the selected condition's retained original. The required source set must still be covered. Do not accept nonexistent IDs, arbitrary prefix matches, or a missing governing record.
3. **Supported extra annotations:** allow additional notes in an expected empty `historical` object only when retained evidence supports every note and the notes neither contradict current decisions nor introduce unsupported facts. The two observed affected artifacts were individually reviewed against R704/R705 and R711/R712/R715. The task/checker permits an object, and the preregistration says extra keys are not compared; the frozen empty-object comparison nevertheless requires exact `{}`.
4. **Focused blocker:** a held artifact may satisfy the question criterion when a question explicitly identifies the missing authority/prerequisite and requests its resolution, despite omitting the proxy keyword. A named unresolved field is also inspectable as a focused request. A generic question, invented blocker or loss of the required null/hold would not qualify. All 18 held artifacts were inspected; T049 is the only changed lexical judgment.

| Outcome under sensitivity rules | Principal, 80 | Onboarding, 6 | All, 86 |
|---|---:|---:|---:|
| Verified artifact gate | 77 | 6 | 83 |
| That gate plus protocol clean finish | 74 | 6 | 80 |

The sensitivity still fails T043, T027 and T082. It retains the infrastructure interruptions of T013/T053 and the turn-cap termination of T073. The apparent improvement largely measures rubric conventions; it is not evidence that a filing treatment improved accuracy.

## Every frozen complete-task failure

Classes below are mutually exclusive primary explanations. Original per-row fields remain in `results.json`; the compact audit retains them without changing gold or grades.

| ID | Case and condition | Regime | Primary explanation | Sensitivity gate |
|---|---|---|---|---|
| T003 | H5 archive, explicit eligibility | Fidelity | `complete` / `ready` convention | Pass |
| T014 | H3 rota, fixed chunks | Matched | `complete` / `ready` convention | Pass |
| T023 | H8 Quillspan, prose | Fidelity | Valid record:section citation format | Pass |
| T024 | H3 parcel, coherent capsules | Matched | `complete` / `ready` convention | Pass |
| T027 | H2 Northcanal, generic headers | Matched | Resource cap; no authorized write/check | Fail |
| T028 | H7 spindle, dependency links | Fidelity | Supported notes in expected empty object | Pass |
| T039 | H7 raster, dependency links | Fidelity | Supported notes in expected empty object | Pass |
| T042 | H8 Ternwick, structured obligations | Matched | Valid record:section citation format | Pass |
| T043 | H1 Sablefin, linked current view | Fidelity | Wrong final correction and missing governing citation | Fail |
| T049 | H5 ledger, generic headers | Fidelity | Focused question omitted proxy keyword | Pass |
| T054 | H3 parcel, fixed chunks | Fidelity | `complete` / `ready` convention | Pass |
| T056 | H3 parcel, fixed chunks | Matched | `complete` / `ready` convention | Pass |
| T059 | H1 Orris, linked current view | Matched | Valid record:section citation format | Pass |
| T064 | H8 Citrine, prose, no entry | Fidelity | Valid record:section citation format | Pass |
| T065 | H3 parcel, coherent capsules | Fidelity | `complete` / `ready` convention | Pass |
| T068 | H5 archive, generic headers | Fidelity | `complete` / `ready` convention | Pass |
| T070 | H3 rota, coherent capsules | Fidelity | `complete` / `ready` convention | Pass |
| T079 | H5 archive, generic headers | Matched | `complete` / `ready` convention | Pass |
| T081 | H3 rota, fixed chunks | Fidelity | `complete` / `ready` convention | Pass |
| T082 | H5 archive, explicit eligibility | Matched | Reader-process failure; no artifact | Fail |
| T084 | H3 rota, coherent capsules | Matched | `complete` / `ready` convention | Pass |

This is 11 status conventions, four citation-format-only failures, two supported extra-note failures, one lexical focus failure, one substantive correction failure, one resource/no-write failure and one infrastructure/no-write failure. T043 also uses section-qualified citations, but normalizing them does **not** restore the absent SA-04 citation.

T049 holds retention null, authority unresolved and pruning unauthorized. Its question asks which signed instruction governs, naming R512's seven days and R513's eleven days, then asks what order or precedence rule resolves the conflict. That is a focused request about the actual blocker even without the word `retention`. The frozen lexical score remains failed.

## The substantive source-use failure

T043 writes `jitter_ms: 200` even though SA-04:S2 requires zero throughout the local plan. It fully reads SA-04 before the first write. Its evidence names SA-01/02/03/05 sections and omits SA-04; the final artifact matches the stale derived view, which SA-05 explicitly says did not incorporate SA-04.

The observed sequence is: read current view at turn 2; read the full correction at turn 4; write 200 at turn 5; reread current view at turn 6; retain 200 through three writes and seven successful structural checks. This supports the narrow finding that origin discovery and structural passes did not ensure use of the governing correction. Stale-view anchoring is a plausible **inference**, not measured internal reasoning. The local plan was not published or deployed. One outcome from one authored family does not show that pointers cause errors or that the unlinked condition is generally better.

## Protocol and encoding limits

| ID | Frozen artifact gate | Actual termination | Later result supplied |
|---|---|---|---|
| T013 | Pass | Infrastructure error after write/check | Yes |
| T053 | Pass | Nonzero reader-process exit after write/check | No |
| T073 | Pass | Reader-turn cap after write/check | No |
| T027 | Fail | Returned-byte cap; no write | No |
| T082 | Fail | Nonzero reader-process exit before write | No |

T027's unchanged draft values and T082's absent fields are failed artifact gates, not authored factual mistakes. A gate-passing artifact is not necessarily a clean protocol finish.

The recorded controls for all 553 accepted calls conform to the frozen model/high-effort identity, local fresh-process/session and one-native-tool inventory claims. They record 1,013 internal upstream requests, 372 session-local bookkeeping calls and 213 verified-unavailable native attempts. Reader-call caps concern explicit harness calls, not a fixed number of provider requests. Failed calls' missing usage is not zero provider work. Token totals are accepted-call metadata, not a complete cost account; cache counters must not be added twice.

The [offline encoding diagnostic](stdio-encoding-diagnostic.json) shows inherited CP1252 stdin/stdout, while the parent sends/receives UTF-8. Curly apostrophes decode into mojibake; CP1252 output can fail the parent's UTF-8 decoder or fail to encode a character. Actual coordinator evidence ties T013 to invalid UTF-8 byte `0x97`. Public T053/T082 receipts identify nonzero exits but do not independently classify their underlying causes.

All non-ASCII fixture characters are curly apostrophes: 11 of 18 task texts plus Rindle derived views and Sablefin originals. All gold keys/values are ASCII. This bounds direct target-value exposure but does **not** establish harmlessness for reading, decisions, lexical search or tokens. The host prompt hash covers intended UTF-8 text; same-call unchanged-input receipts establish consistency of the adapter-decoded input across internal rounds, not intended-prompt fidelity. Any UTF-8-corrected follow-up must be a distinct phase with its own records and limitations.

Fresh local sessions, no supplied PARA/other-trial history, no native collection access and checked `store:false` are operational controls. They do not prove remote erasure, unfamiliarity with previously submitted corpus text, absence of provider personalization, a cold cache, every injected system-prefix byte or every operating-system read. Glassmere and Citrine have disclosed setup exposure. Neither accepted calls nor repeated regimes are independent samples.

## Maintenance and inference bounds

The five [maintenance traces](maintenance-results.json) are actual disposable staged-file replays with asserted checkpoints, not LLM-effect validation. H4 has four canonical versus five copied repair mutations, but 62 versus 45 logged state reads and two indexed separator-access failures in both conditions. This is not total-cost or availability dominance, and it does not measure full inherited state or retained-source fallback.

Each H6 schedule has three attempts and six governing-record body inspections, with initial ingest, metadata and evaluator reads separately counted. Auxiliary hash/consistency reads are evaluator instrumentation. Interrupted attempts consume budget without committing the candidate. Update/handoff/fixed schedules expose different versions and produce five/four/six stale event steps; the update policy ends stale/dirty while the others end current. These are event steps, not elapsed-time durations or universal policy rankings. The version index and dependency/coverage machinery are engineered; automatic extraction and production maintenance are not tested.

The 18 families come from two LLM fixture authors. Use paired family outcomes within each regime, keep the six onboarding runs separate, and report the 80 principal denominator for filing comparisons. No independent-trial confidence interval, significance test, population accuracy claim or general H1-H8 validation follows from these data. H3 tests index grouping under whole-file/line tools, not a unit-aware retrieval algorithm; H5 supplies manually correct metadata; H7 does not isolate traversal-depth policy; H8 tests representation under a controlled executor. Larger independently authored, prospectively scored and transport-corrected studies remain necessary.

## Separate selected UTF-8 diagnostic

The later [follow-up](followup-results.json) has four trials and 33 accepted reader calls, not four total model calls. Its outcome-selected [plan](followup-plan.md) and [freeze](followup-freeze.json) precede those trials and retain the main corpus/results hashes. All seven frozen public input hashes and the result's follow-up freeze hash match. The diagnostic reuses the unchanged main runner/scorer; all four write artifacts that independently match the expected fields, cite required origins, pass actual authorized checks after their final write, receive a later result and terminate `reader_done` without infrastructure errors. Their logical/physical hashes and returned-byte accounting also reconstruct without discrepancy.

D001-D003 recover jitter zero in Sablefin's three arms. D004 recovers the exact source label U+9752 U+706F, symbol U+03BB and threshold 8 while retaining original threshold 4. All 33 recorded calls have the same effective model/high effort and conforming local controls; they record 20 bookkeeping calls and three verified-unavailable native attempts, with no forbidden virtual operation. Main results remain 86 rows and are not pooled with these four.

These observations support successful correction and Unicode continuation examples under the declared `-X utf8` transport change. They do not isolate encoding from stochastic reader variation, prior service exposure, changed concurrency or other factors. The selected Sablefin family is not held out. The public follow-up freeze pins public data/code but not the private adapter or command file; the recorded native binary hash is not an adapter-code hash. Receipts do not supply a caller-to-upstream prompt digest comparison or per-call actual stdio encoding. Exact artifact recovery is useful functional evidence, not a proof of every input byte or general filing efficacy.

## Repeatable aggregate integrity check

Run this Python fragment from the study directory. It checks the saved audit against the immutable result, manifest and original failure rows; it does not automate the unblinded semantic adjudications.

```python
import hashlib, json
from pathlib import Path
a = json.loads(Path('adjudication.json').read_text(encoding='utf-8'))
for name, expected in a['input_sha256'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
r = json.loads(Path('results.json').read_text(encoding='utf-8'))['trials']
f = json.loads(Path('freeze.json').read_text(encoding='utf-8'))
assert {x['trial_id'] for x in r} == {x['trial_id'] for x in f['jobs']}
assert len(r) == len({x['trial_id'] for x in r}) == 86
assert sum(x['score']['complete_task'] for x in r) == 65
assert sum(x['score']['complete_task'] and x['onboarding'] == 'unbriefed'
           for x in r) == 60
assert {x['trial_id'] for x in r if not x['score']['complete_task']} == {
    x['trial_id'] for x in a['frozen_complete_task_failures']}
assert sum(x['sensitivity_complete_task'] for x in a['trial_adjudications']) == 83
assert sum(x['sensitivity_clean_finish'] for x in a['trial_adjudications']) == 80
print('PASS: pinned inputs, 86 scheduled rows, frozen and sensitivity counts')
```
