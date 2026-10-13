# Prospective supplemental review of actual reader artifacts

Prepared before inspecting October 13 reader outcomes. **NOT EXECUTED.** This
supplement follows the frozen 192-trial reader schedule; it does not replace,
adjust, adjudicate or redefine any primary score. The prior
[October 11 semantic review](../study-2026-10-11/SEMANTIC-REVIEW.md) supplies the
four-label pattern and disjoint size-balanced partition method. October 13 has
stricter typed contracts, but exact key agreement still differs from entailment.

## Census and execution gate

After all 192 scheduled trials are recorded, the root execution audit must first
verify the actual outcomes, artifacts and native/private receipts. Run the
stdlib-only [preparer](prepare_reader_review.py) only with the exact audited
`reader-results.json` and `freeze.json` SHA256 values. It imports no study
implementation, loads no model, and invokes no provider. Its `--self-check` uses
only synthetic temporary fixtures and can run before collection.

Every on-disk artifact enters an opaque case, including contract-invalid objects,
unjustified holds and artifacts retained after a late execution fault. No-write
trials receive no semantic rating, but their count and reason remain in the full
192 denominator. An expected artifact missing from disk, a missing retained
write-hash receipt, or a hash/value discrepancy is a hard preparation error;
never silently omit the trial. The private root audit must resolve that discrepancy
before review. A late-fault reconstructed write receipt can establish retained
artifact fixity but cannot recover discarded chronology or evidence exposure.
Such an artifact remains included with `not_auditable` extraction status and zero
supplied evidence. Neither a failed upstream submission nor a newly requested
same-batch read grounds a write.

The preparer checks every frozen input hash, schedule/checkpoint census and
fingerprint, exact retained artifact bytes and write hash, saved prompt hash,
persisted prompt/runtime identity, accepted upstream receipt, write response/action
links, final-write event/receipt, returned result links and source-body fragments.
All input, artifact, source-body, case and partition hashes are retained privately
for the later independent root audit. Complete collection alone is not root
acceptance of extraction.

## Smallest blinded interface

Each reviewer receives only a partition index, this rubric, and its case files:

```text
case_id
task: id, query, answer_keys, answer_contract
artifact: actual parsed JSON value; artifact_utf8 and exact byte SHA256
deliveries: operation, exact actual returned source-bearing result,
            delivered-prompt SHA256, source-fragment crosslinks and result hash
source fragment: opaque fragment ID, visible source ID, start/end/text,
                 source-body SHA256, actual-result text pointer and offsets
extraction_auditability: auditable/not_auditable and missing-proof reasons
offset_unit: Unicode code points, half-open
```

A hash is a fixity anchor, not an added authority fact. The input includes no
authored answer, gold rationale, support set/span, family/template/split, condition
arm/block, primary score, outcome flag or case-to-trial key. The exact actual
artifact is preserved even when it has unwanted keys or a wrong JSON type; its
extra content is not trusted as evidence. All packets and diagnostics remain
private until a separate public privacy review and explicit publication.

For direct/oracle trials, preserve only the exact supplied packet from a verified
accepted saved prompt tied to the retained artifact response/write. For discovery,
use source-bearing host results replayed in the verified accepted final-write
prompt, crosslinked to retained earlier action events. Current response-batch
results are excluded. Full original/derived bodies never enter a case unless
those exact bodies were actually delivered before writing.

Preserve source headers exactly as delivered. `whole_record` and whole-file `read`
have verbose SOURCE headers with title, scope, aliases, authored time, links,
supersession and incorporation data, plus time scope when present. `ranked_body`
and passage/retrieve packets have only ID, character range, kind and revision.
Literal search results have path, ID, line, range and text; do not add revision,
scope or other bank metadata. Search is original-only under its supplied tool
contract. Derived views remain visible when actually delivered and identifiable
from their delivered headers; they cannot substitute for original support.
For header validation, reproduce the frozen observational document projection:
aliases are the family name followed by its declared aliases, even though raw
family record objects lack that injected field. This validates the delivered
verbose header; it never enriches minimal headers or search results.
Navigation README/list results and the reader's prior generated guesses are not
source evidence. No native diagnostics, account identifiers or host paths enter
reviewer inputs.
JSON boundaries reject duplicate keys, nonfinite numbers including exponent
overflow, and lone surrogates. Retained output types remain exact.

## Review labels and exact required output

Use one fresh LLM reviewer context per disjoint partition. Each artifact receives
one rating, with shared context inside its partition. Assign packets greedily by
encoded input bytes without outcome or condition stratification. Do not reveal
the private condition key until every required judgment has been durably saved
and checked against its case-file hash. There are no human adjudicators, duplicate
ratings or reliability estimate; no claim of independent model-family validation
or remote provider erasure follows.

Each case judgment must bind `case_id` and `input_sha256` and contain:

```text
answer_judgments: one entry per requested answer key
status_judgment
citation_judgment
full_query_judgment
limitations: list of concrete missing-proof or ambiguity notes
```

Each judgment entry has `label`, a substantive `rationale`, and `citations`.
Every review citation identifies a supplied original fragment ID and a nonempty
half-open source interval contained within that fragment. Explain any derived-view
conflict in the rationale, but ground positive factual support or contradiction in
supplied originals. If no original can support the judgment, use an empty citation
list and explain the evidence boundary. Do not invent a span or cite an unavailable
full record. A citation's coordinate validity is checked mechanically; entailment
is the reviewer's substantive judgment.

| Label | Evidence-bounded meaning |
| --- | --- |
| `supported` | Supplied applicable originals establish the claim as returned, including qualifiers and status. |
| `contradicted` | Supplied positive counterevidence establishes an incompatible claim; missing evidence alone does not contradict. |
| `not_established` | The supplied evidence permits assessment but does not establish the claim or its negation. |
| `not_auditable` | The claim cannot be assessed because the artifact, chronology, readable evidence or output meaning lacks the necessary audit proof. |

Judge all requested answer fields individually, even if the artifact is malformed
or misses a key. Preserve type/convention problems in the rationale; do not coerce
integer `0` into boolean `false`, flatten ordered lists, reduce contract-prescribed
fractions, normalize IDs, or silently substitute a plausible intended answer.
Explicitly distinguish a settled negative fact from `null`, absent information and
an evidence-bounded hold. A justified hold can have a supported status while the
full requested query remains unresolved. A readiness claim requires enough supplied
applicable original evidence to resolve the query's requested requirements, not
merely a syntactically valid answer.

Judge the actual artifact's citations for original interval support of its material
claims, including unsupported/missing/derived references and overbroad span claims.
Review-rationale citations are separate from artifact citations. Strong available
citations do not repair invalid extras or alter the frozen citation gate. Full-query
judgment covers all requested constraints, exceptions, chronology, scope and
uncertainty policy. Original support differs from authored-key agreement and does
not establish globally complete evidence, proven minimal alternatives or natural
population accuracy.

## Aggregation and publication boundary

After all judgments pass case/hash/field/label/citation-bound checks, root may unblind
the condition key and compute descriptive marginal counts by field, status,
citation and full query, plus per-condition counts and no-write reasons. Keep 192
scheduled trials, actual written artifacts, auditable inputs and reviewed artifacts
as separate counts. Any intersection with frozen typed-answer agreement is explicitly
descriptive and must not become a regraded accuracy or completion endpoint. Publish
only fictional cases/fragments, safe hash provenance, judgments and bounded counts
after independent extraction verification and a separate privacy/link review; raw
native diagnostics, account information, absolute private paths and the private
collection remain private.

Visible task/source IDs, content, verbose headers, source volume and retrieval
policy strings can cue assignments. Opaque labels blind the provided condition/key
boundary; they do not guarantee anonymity or condition concealment. Related authored
templates, one LLM judgment per artifact, shared partition context and possible
shared model biases limit generalization. No new provider calls, reviewed artifacts
or semantic results exist when this prospective plan is prepared.
