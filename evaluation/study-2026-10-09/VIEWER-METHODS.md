# Viewer construction and verification

The portable [viewer](index.html) is a presentation of recorded fictional-data
results. The [report](REPORT.md), [raw receipts](results.json) and [independent
audit](AUDIT.md) remain authoritative for interpretation. Its trial explorer
contains **80 main plus six exploratory onboarding observations**; the four
later transport diagnostics are separate. Principal comparison bars explicitly
select unbriefed rows.

Gemini, accessed through an authenticated Antigravity CLI, authored the HTML,
layout and interactive logic. A first draft was rejected because it synthesized
mock rows and artifact snippets from aggregate totals. A revision also failed
its exact-text patch contract. Later schema/label reviews corrected actual
object rendering, onboarding/audit lookup, shared H6 IDs, termination labels,
proxy definitions and the historical initial-value wording. These presentation
attempts are not reader experiment trials and are never pooled with their scores.
Private generation handoffs, account material and runtime identifiers are not
published.

The final [Gemini-authored template](viewer-template.html) contains exactly one
data-assignment slot. [make_viewer_data.py](make_viewer_data.py) projects recorded
outcomes, complete artifact objects and actual maintenance checkpoints into
[viewer-data.json](viewer-data.json). [assemble_viewer.py](assemble_viewer.py)
imports those exact JSON values without asking a model to reproduce a dataset.
It rejects missing/repeated slots and non-object data, verifies JSON roundtrip,
escapes script-closing characters and Unicode line separators, and replaces the
destination atomically. These protections do not constitute a general browser
security audit.

The final viewer was exercised in an actual installed Chromium browser at
1400px and 390px widths. Checks reconciled all 86 displayed identities,
onboarding conditions, termination reasons and execution/source flags, plus all
84 written artifact JSON objects. Regime/hypothesis filters, trial search,
artifact disclosure and all three H6 schedule selections were exercised. All
24 displayed H6 checkpoints matched recorded coverage, stale fields, dirty state
and current-state flags; coverage details opened. Nine selected-arm onboarding
cells each used N=1 and their actual audited artifacts. Four diagnostic rows
remained separate. No page-level JavaScript errors or page horizontal overflow
were observed; wide tables use contained scrolling. Read [viewer-qa.json](viewer-qa.json)
for the bounded receipt and final file hashes.

Independent editorial reviews checked the data projection and presentation
logic, public text, sensitive-pattern absence and decoded PNG/SVG metadata.
Current HTML imports no external asset and contains no telemetry/network API
code. Its CSP denies connections, frames, objects and form submission, while
allowing ordinary public source links. This is a bounded code/metadata review,
not proof of privacy, attention, comprehension or all possible network behavior.

The original frozen scores remain unchanged. Posthoc sensitivity is labeled
separately and was reviewed unblinded by a fixture author. Successful structural
checks and full-original reads are displayed as separate measurements, not
factual correctness guarantees. Git attributes preserve exact recorded study
bytes, including Windows newlines, so publishing cannot invalidate frozen
SHA-256 receipts through newline conversion.

To regenerate the imported viewer after checking the recorded inputs:

```sh
python evaluation/study-2026-10-09/make_viewer_data.py
python evaluation/study-2026-10-09/assemble_viewer.py --template evaluation/study-2026-10-09/viewer-template.html --data evaluation/study-2026-10-09/viewer-data.json --output evaluation/study-2026-10-09/index.html
```

The template alone intentionally shows a data-not-loaded message. Open the
assembled `index.html` for the completed artifact. GitHub previews HTML source;
download/open the file to use its interactive controls. The [report](REPORT.md)
also embeds 12 scientific PNG charts, with SVG exports under [figures](figures/).
