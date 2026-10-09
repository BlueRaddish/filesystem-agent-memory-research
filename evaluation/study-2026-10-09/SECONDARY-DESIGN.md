# Secondary mechanism fixtures — 2026-10-09

**Status: wholly fictional authored test data; no model or reader results are claimed here.** These fixtures exercise H3, H5 and H7 through twelve matched case-condition executions, and H4/H6 through engineered deterministic evolution traces. They supplement the primary H1/H2/H8 suite. Each task family was authored specifically for this study; the small number of engineered families cannot validate general filing benefits.

All source records, entities, dates and events are invented. No private PARA records, native session content, or personal data were read or reused.

## Reader cases

| Hypothesis | Family | Matched arms | Governing difficulty |
| --- | --- | --- | --- |
| H3 | Brindle Parcel | fixed chunks / coherent capsules | Correction split from verification challenge; distant archived exception |
| H3 | Drift Rota | fixed chunks / coherent capsules | Slot correction, missing-team failure, declined publication and archived exception |
| H5 | Cinder Archive | generic headers / explicit eligibility | Late import of old authority, newer unapproved proposal, historical rule, scoped archive exception |
| H5 | Tidal Ledger | generic headers / explicit eligibility | Equally authorized incompatible instructions with unknown precedence |
| H7 | Moss Spindle | no dependency links / dependency links | Weak bridge to calibration, scoped exception, cycle and irrelevant link |
| H7 | Orchid Raster | no dependency links / dependency links | Missing approved prerequisite, cycle and unapproved decorative near-match |

Every arm retains readable original source files. The task, structural checker and tools are identical within a matched family. A reader writes `artifacts/result.json`, then actually runs `python tools/check.py artifacts/result.json`. The checker asserts JSON shape only; it contains no gold decisions and explicitly distinguishes structural validity from task correctness.

The common artifact keys are `status`, `decisions`, `historical`, `unanswered` and `evidence`. Gold critical assertions use dot paths into that artifact. Required evidence IDs are a subset requirement; extra IDs or a different evidence order are not errors by themselves. Natural-language uncertainty wording must not be exact-matched against the illustrative expected artifact. Correct blocked handoffs in Ledger and Raster satisfy the abstention objective without claiming the underlying operation is complete.

A ready artifact may record a genuinely unknown nonessential detail without becoming blocked. Essential unresolved prerequisites require a blocked artifact and a focused clarification. Brindle Parcel's R302 is optional failure corroboration because R303 independently states that the recorded failure still stands.

H3 indexes reproduce each numbered original passage once. Fixed units contain three passages; coherent units follow the authored event boundaries. No arm receives an answer-rich abstract. Passage text and intact sources are matched, while unit boundaries and metadata overhead differ. Report actual returned bytes and source expansion. These tiny stores allow exhaustive reading, so a null result may reveal a discovery ceiling.

H5 source bodies are byte-identical between arms. Generic and source-derived eligibility header strings have the same character length within each source. Character matching does not guarantee tokenizer matching; report actual tokens. Explicit disputed eligibility keeps both Ledger instructions visible. Choosing a single winner would violate the intended intervention.

H7 changes only dependency lines in the entry index. The same reader policy and filesystem tools apply. Linked-arm cycles and irrelevant paths are deliberate robustness cases. Raster's calibration source is genuinely absent in both arms. Link traversal, satisfied generated prerequisites, and additional reads do not prove complete governing evidence.

## Deterministic evolution traces

The `maintenance_cases` field is evaluator-only. It must never be exposed to a reader. Event operations write exact supplied text or rename an exact path within a newly staged trace workspace. Preserve source versions and log all file mutations and outcomes. Paths, missing links and corrections are actual filesystem states, not descriptive prose.

H4 starts with a common shared rule, project associations, and a Birch-only archived exception. Canonical and duplicated stores receive identical authority changes. A correction, a storage rename, a broken Birch link and an exception correction have prescribed repairs under a shared cap of two repair mutations per event. Canonical repairs require four file writes across the trace; duplicated repairs require five. Both methods suffer indexed separator-rule access failures before repairs. These access flags cover the indexed rule and explicit local exception; they do not claim complete inherited-state access or permit fallback to retained authority/version files. The exception must remain local. This arithmetic reflects the engineered storage design; it does not measure an LLM maintainer, reliability distribution or reader benefit.

H4 schema:

- `initial_files`: common authority records.
- `conditions[].files`: condition-specific starting store.
- `events[].common_operations`: source event writes, excluded from repair budget but logged.
- `events[].operations_by_condition`: injected storage moves or access faults.
- `events[].repair_operations_by_condition`: predetermined repairs, charged to the repair budget.
- `checkpoints`: before/after-repair authority, access and current-state expectations.

H6 replays the same eight event steps in every arm. Shared machinery includes the dependency map, incorporation coverage, source versions, gap audit, atomic view commit, and review cap. All arms have exactly three scheduled review attempts and a two-governing-record inspection cap per attempt:

| Schedule | Review steps |
| --- | --- |
| update triggered | 1, 4, 5 |
| handoff triggered | 4, 6, 8 |
| fixed period | 2, 5, 8 |

Step 3 removes a dependency before its governing correction. Step 4's shared handoff audit exposes the incorporation gap and restores the declared dependency. Step 5 interrupts any scheduled review before its candidate can replace the committed view; interrupted attempts consume budget. Steps 6 and 8 audit gaps again. No arm receives free final cleanup.

The triggered arm consequently reaches the final checkpoint with old committed separator data and a dirty/gap warning after spending its final attempt on the interruption. Handoff and fixed-period schedules reach the current final view. This deliberately prevents a guaranteed trigger-policy victory and exercises backlog, missed dependencies and interrupted writes. A warning is not repaired state or observed reader safety. Record authority mismatch, stale duration in event steps, coverage, available and inspected source versions, attempts, reads and mutations at every checkpoint.

All governing K601/K602 original versions are retained. The irrelevant decorative K699 record is overwritten at step 7 without retaining its original version; the trace makes no all-record retention claim.

H6 holds replay count and attempt caps constant; source-version exposure differs naturally with timing. Its output is a whole-policy engineered trace, not a timing-only causal estimate. No model benefit or biological spacing claim follows.

## Isolation, scoring and reporting

Stage only one condition and its generic task in a fresh isolated workspace. Exclude this JSON, gold, builder scripts, the original repository, prior runs and provider memory. Use enforced allowlisted tools or an actual sandbox, with no network. A changed process or a cwd restriction alone is insufficient. If enforcement is incomplete, label executions leakage-prone demonstrations.

Freeze the artifact requirements before running readers. Retain failed, interrupted and abstaining runs. Log returned evidence spans rather than treating citations as proof of discovery or use. Inspect actual artifact bytes and the observed post-write check. Separate critical errors, ordinary details, complete continuation, valid abstention, historical accuracy and resources.

Visuals should show counts and denominators, individual paired outcomes, per-case critical failures, discovery paths, verification traces and the maintenance timeline. Distinguish executed case coverage from measured efficacy. Six deliberately engineered families are not sufficient for broad model-performance or safety claims.

## Runnable fixture consistency check

Run the following PowerShell block from the repository root. It verifies the six-family/twelve-condition schema, identical checker and original sources, H3 index passage multisets, H5 header lengths and bodies, and H7 source equality. It does not run a reader or establish filing benefit.

```powershell
@'
import collections
import json
from pathlib import Path

p = Path("evaluation/study-2026-10-09/secondary-cases.json")
data = json.loads(p.read_text(encoding="utf-8"))
assert len(data["cases"]) == 6
assert sum(len(c["conditions"]) for c in data["cases"]) == 12
checker = None
for case in data["cases"]:
    a, b = case["conditions"]
    fa, fb = a["files"], b["files"]
    assert fa["tools/check.py"] == fb["tools/check.py"]
    checker = checker or fa["tools/check.py"]
    assert checker == fa["tools/check.py"]
    assert case["gold"]["artifact_path"] == "artifacts/result.json"
    assert case["gold"]["required_checks"][0]["argv"] == [
        "python", "tools/check.py", "artifacts/result.json"]
    originals = sorted(k for k in fa if k.startswith("memory/sources/"))
    assert originals == sorted(k for k in fb if k.startswith("memory/sources/"))
    if case["hypothesis"] == "H5":
        for key in originals:
            ha, ba = fa[key].split("\n\n", 2)[1:]
            hb, bb = fb[key].split("\n\n", 2)[1:]
            assert len(ha) == len(hb), key
            assert ba == bb, key
    else:
        assert all(fa[k] == fb[k] for k in originals)
    if case["hypothesis"] == "H3":
        def passages(text):
            return collections.Counter(
                line for line in text.splitlines()
                if line.startswith("R") and line[1:4].isdigit())
        assert passages(fa["memory/index.md"]) == passages(fb["memory/index.md"])
assert len(data["maintenance_cases"]) == 2
assert {m["hypothesis"] for m in data["maintenance_cases"]} == {"H4", "H6"}
print("PASS: fixture consistency; no reader or model benefit tested.")
'@ | python -
```
