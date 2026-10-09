# Independent fictional corpus authoring

This bundle was independently authored by the `independent_corpus_author` LLM sub-agent on 2026-10-09. It is entirely fictional. It is **not human-authored**, externally validated, or a collection of observed user sessions. The author read the public `research/filing-hypotheses.md`, public `evaluation/protocol.md`, and applicable `AGENTS.md` instructions. The author did not read private vault content, native conversation/session archives, existing fixture gold, reader outputs, or maintenance outputs. No readers or model requests were run by the corpus author, and nothing was published.

The parent supplied the experimental scope and requested schema before authoring. Its only authoring follow-up concerned implementation of the runner contract, visible-checker leakage, citation-set minimality and fixture audit. This is separate corpus authorship within one collaborative LLM team; it is not a blinded human annotation process. The parent must audit the gold, resolve ambiguity and freeze source hashes before scored reader runs.

## Scope and units

`cases.json` contains 12 distinct fictional project families: four for H1, four for H2 and four for H8. Each family has one held-out-formulated task and matched organization conditions, for 28 condition workspaces. Families vary domains and governing constraints, but share one author and a common JSON/checker envelope. Conditions within a family are paired and are not independent samples. Twelve named families do not establish statistical independence or adequate power for general agent-performance claims.

| Hypothesis | Families | Embedded adverse cases |
| --- | --- | --- |
| H1 | Glassmere hydrophone quarantine; Rindle conservation transfer; Sablefin alert routing; Orris calibration hold | Unincorporated correction despite recent summary rewrite; within-record later correction; narrow retained exception; late import of historical brochure; rejected proposal; failed prior verification claim; unresolved equal-authority conflict |
| H2 | Northcanal passenger reissues; Emberhall conservation imaging; Bracken west irrigation; Morroway tactile reflow | Wrong-project near-duplicates with overlapping vocabulary; aliases and task paraphrases; scoped exceptions; unknown technical values; rejected cross-project shortcut |
| H8 | Citrine archive package; Quillspan bridge route; Ternwick local charge schedule; Feldglass seed mass hold | Cancelled obligations; unfulfilled triggers; missing prerequisites; false completion marks; failed old-artifact results; unresolved unit conflict |

Adverse cases are embedded in the main family histories. There are no extra adverse-variant arms, no alias ablation, no source-removal diagnostic, no view-only diagnostic and no schema-taught condition in this initial bundle. Those require separately preregistered runner or corpus work.

## Matched manipulations

All conditions preserve original source records, the same initial editable artifact, the same task and the same local executable. Each source includes an explicit stable ID and numbered source spans. Task prompts authorize one local artifact edit, request source-ID citations, provide the artifact/check command and prohibit external action. They do not identify the decisive source, prescribe retrieval order, teach the memory schema or disclose gold values.

Every case uses the same editable path, `artifacts/result.json`, including all task and executable references. H2 initial artifacts set `project` to JSON null so the task must recover the canonical target from the problem, contextual aliases and original evidence. Case/family identifiers and evaluator directory names must not be supplied to the reader as an additional retrieval cue. H1 and H8 tasks deliberately name their target projects because they test state/obligation handling rather than target-scope recovery.

H1 compares `source_only`, `unlinked_current` and `linked_current`. The linked and unlinked view wording is identical after removing the appended Markdown source pointers. Pointers identify a source ID, numbered span and relative original-record path. Three view families deliberately fail to incorporate later governing evidence; recently rewritten metadata must not be treated as complete coverage. The source-only arm retains every original record and has no current view. All arms have the same basic collection entry; the source-only entry does not instruct readers to look for an absent summary.

H2 compares `generic_headers` with `problem_scope_alias_headers`. Every record has the same stable ID and byte-identical original body in both arms. Only its prefixed header changes. Useful headers identify the affected artifact, actual scope, source-derived aliases and the originating problem. Generic headers provide nonspecific project/topic language. Each header envelope is exactly **384 UTF-8 bytes**, including its final newline. Neutral retained-evidence prose and trailing spaces equalize the byte count. This is a byte-length-matched control; it does **not** establish equal model-token counts, equal semantic information, or realistic maintenance effort. The runner must report actual token counts and this padding convention. No inferred false cue was introduced in these main arms.

H8 compares `prose_obligations` with `structured_obligations`. Both put `pending.md` at the same path and link it from the same entry. Introductory text and every obligation ID, trigger, action, prerequisite, cancellation, fulfillment criterion and current note have identical wording. The structured arm changes those facts into rows. Original records independently retain the underlying obligation facts. Neither arm receives new authorization. Required, forbidden and currently untriggered checks are distinct.

## Artifact and gold contract

The outer bundle has `schema_version`, an explicit `authorship` declaration, and `cases`. Each case contains `id`, `family`, `hypothesis`, `task`, `conditions` and evaluator-only `gold`. Each condition supplies a complete map from relative paths to UTF-8 text. Stage only one condition's file map and the case task for a reader; never stage this bundle, authoring note, gold or evaluator repository.

Every initial artifact uses the same root keys: `project`, `status`, `config`, `history`, `questions`, `obligations` and `evidence`. Domain config and history values vary by family. Current configuration and retained historical explanations are scored separately. Prior-verification state and rejected-shortcut disposition are explicit history fields so their supporting records are genuinely necessary for the task, rather than merely forced citation extras. Source records define the small field conventions; the task requests the meaning without giving the answer.

Gold contains:

- `critical_assertions`: dotted artifact paths and required JSON values. A violation fails the case even if other fields are correct.
- `artifact_path` and `expected_artifact`: the required editable file and author-annotated target values. Compare domain values, history and obligation state semantically where appropriate; citation order is immaterial. A blocked artifact's focused nonempty question is scored by meaning, not exact equality to the reference code in the `questions` array. H2 excludes exact equality to the canonical `project` label from grading; target scope is assessed through the governed decisions.
- `required_source_ids`: the audited **sufficient citation set**, which is a hard grounding gate distinct from full-original read coverage. The artifact must cite a sufficient set of governing IDs; an adjudicated valid alternative set may also satisfy that gate. `expected_artifact.evidence` is an illustrative fuller citation list, so extra valid IDs and citation order do not cause failure. The read log separately measures returned original-source coverage; a sufficient citation set does not prove that its original records were read or that citations caused the decisions. Redundant origins must not be forced into the gate. Wrong-project IDs should be adjudicated for actual misuse separately from discovery coverage.
- `required_checks`: argument vectors with observed expected exit status. A prose claim of a check cannot satisfy this field.
- `forbidden_checks`: argument vectors representing cancelled or untriggered actions. The runner should separately record attempted and actually executed forbidden commands.
- `rationale` and `expected_abstention`: why the evidence governs, and whether a safe blocked artifact plus focused question is the correct continuation.

`h1_orris` and `h8_feldglass` require justified abstention on one essential unresolved value. Abstention does not mean abandoning the task: the reader must still prepare the authorized safe artifact, retain nonconflicting facts, cite the conflicting authority and run the allowed base check. All other cases leave at least one genuinely unspecified technical value as JSON null without inventing a value.

The visible `tools/check.py` is a generic structural/operational checker. It contains no project name, required-source set, expected artifact literal, gold value, answer-key comparison or evaluator path. The base check rejects unfinished status, malformed JSON, duplicate citations, contradictory hold/question state and invalid obligation status. Payload, route, timing and mass modes check local data shape or basic internal consistency. These checks cannot prove correct authority, chronology or scope; the hidden evaluator must inspect those independently. Forbidden modes are harmless local checks in the fictional workspace, not real network or actuation commands; their invocation is still an obligation/authorization error under the task.

## Author-only verification

On 2026-10-09, the author ran a static fixture audit and checker smoke tests in disposable local directories, with hidden child processes and captured output. These are fixture tests, not reader trials or agent-performance measurements. The audit verified:

- 12 unique family names and 28 condition maps, with the then-authored reference sets present in every condition;
- every critical dotted path agrees with the expected artifact;
- every required source ID is present in each condition;
- relative paths have no traversal component, and all embedded Python checkers compile;
- H1 original files are identical and linked/unlinked wording differs only by source pointers;
- H2 original bodies are identical and headers have matched 384-byte envelopes;
- H8 rows reconstruct to exactly the same obligation-fact prose;
- all 15 required checker invocations accept the corresponding expected artifacts; and
- all 12 unfinished initial drafts fail the generic base check.

Captured audit stdout:

```json
{
  "kind": "author_static_and_checker_smoke_audit",
  "reader_runs": 0,
  "case_count": 12,
  "condition_count": 28,
  "required_check_commands_passed_on_gold": 15,
  "unfinished_drafts_rejected": 12,
  "manipulation_invariants": "passed",
  "critical_path_consistency": "passed"
}
```

After the parent identified a potential H2 retrieval cue in the family-specific output filenames, the author renamed every editable artifact and check reference to `artifacts/result.json`, changed H2 draft project values to null, and repeated manipulation/critical-path checks and the 15 required checker smoke runs. All passed, and all 12 unfinished drafts again failed base. No reader or model was called for this correction.

The pre-freeze source audit then removed RI-01, SA-01 and OR-01 from the respective sufficient citation sets: their destination corrections already restate the historical destinations needed by the artifacts. Original records and the fuller illustrative evidence arrays remain intact. Quillspan's accepted ordered stop list was added as a critical assertion so the bridge-closure correction cannot be treated as ordinary partial credit. Task quote text was checked for common UTF-8 quote mojibake and replacement characters; none was found, so tasks were not rewritten. These surgical changes do not alter condition files, source bodies or executed checks.

The parent still needs an independent source-to-gold review, a durable execution receipt, fixture hash freeze, reader isolation controls and a preregistered scoring/reporting plan. The smoke result does not certify gold semantics, enforce fresh readers, estimate performance or justify any filing-method recommendation.
