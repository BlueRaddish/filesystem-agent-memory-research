# Supplemental blinded source-entailment review

All **123 actual reader artifacts** were reviewed; the other **21 scheduled trials
had no artifact and remain primary failures**. Three fresh-context LLM reviewers
each handled 41 cases, one reviewer per case. This is post-collection supplemental
evidence, with no human adjudication, duplicate ratings or reliability estimate.
It does not replace any frozen outcome or create an adjusted accuracy score.

Reviewers judged all requested fields, status, actual citation entailment and
full-query coverage. 66 artifacts have every requested
value and status judged supported by the available original evidence;
37 of those fail authored exact-answer
matching. That intersection identifies candidates for wording/type/convention
inspection, not automatic global equivalence or task success.

## Blinding, inputs and review procedure

The execution audit prepared an exact packet for every auditable actual artifact.
Arm, retrieval engine, primary score and authored expectations were withheld during
judgment. Packets contained only query, requested answer keys, the artifact's
requested fields/status/citations, and original sources actually exposed before
the final write. They excluded derived views and navigation content. Search
fragments remained fragments; strictly later and same-write-turn observations
were excluded. The condition key was withheld until all judgments were durable.
Content, header cues and source quantity can nevertheless make assignments inferable.

Assignments were balanced by encoded packet size without outcome stratification.
Each reviewer received 41 disjoint packets. Every input hash, requested-field
census and judgment source ID was checked. Long full-collection cases were read
in explicit ranges or a lossless representation of exact already-read text and
suffixes; individual source hashes and reconstruction checks retained coverage.
Reviewers reported initially truncated displays where applicable and reread them;
no incomplete display was accepted as full evidence.

The four labels are **supported**, **contradicted**, **not_established** and
**not_auditable**. They describe entailment within supplied originals, not all
retained or globally governing facts. Missing values or evidence may prevent an
answer without proving a false claim. A conservative evidence-bounded hold can be
supported even when it does not resolve the requested query. Unavailable artifact
citations can be noted in limitations; judgment citations point only to supplied
sources used to support the rationale. Supporting available citations do not
repair invalid extras or change the frozen source-ID gate.

## Descriptive counts

Columns are independent review judgments/intersections. They are not a regraded
completion rubric. N retains the scheduled denominator, including absent artifacts.

| Block/arm | N | Reviewed | All values/status supported | Supported exact-answer mismatches | Full query supported | Citation entailment supported | No artifact |
|---|---:|---:|---:|---:|---:|---:|---:|
| diagnostic/full_collection | 12 | 12 | 12 | 7 | 12 | 12 | 0 |
| diagnostic/oracle_evidence | 12 | 12 | 12 | 7 | 12 | 12 | 0 |
| discovery/raw_filesystem | 12 | 2 | 1 | 1 | 1 | 1 | 10 |
| discovery/retriever_filesystem | 12 | 1 | 0 | 0 | 0 | 0 | 11 |
| main/bm25_000 | 24 | 24 | 10 | 3 | 9 | 16 | 0 |
| main/bm25_111 | 24 | 24 | 11 | 7 | 11 | 15 | 0 |
| main/mixedbread_111 | 24 | 24 | 9 | 6 | 9 | 16 | 0 |
| main/routing_rescue_111 | 24 | 24 | 11 | 6 | 11 | 19 | 0 |

Across reviewed artifacts, 6 have at least one
requested value/status judged contradicted; 65 have
full-query support and 91 have citation-entailment
support. These marginal counts must not be added or substituted for primary
success. Per-field and marginal label counts are:

```json
{
  "answer_judgments": {
    "not_auditable": 11,
    "not_established": 107,
    "supported": 426
  },
  "citation_judgment": {
    "contradicted": 6,
    "not_auditable": 4,
    "not_established": 22,
    "supported": 91
  },
  "full_query_judgment": {
    "contradicted": 5,
    "not_established": 53,
    "supported": 65
  },
  "status_judgment": {
    "contradicted": 6,
    "not_established": 5,
    "supported": 112
  }
}
```

## Inspectable mismatch examples

- R005 returns `14:20 on October 12` where exact matching expects `14:20`.
  The reviewer finds the supplied original evidence supports the qualified time.
- R104 returns `retain` where exact matching expects `retain source input order`.
  The reviewer reads this action in the supplied source/query context.
- R117 returns `both exterior doors latched` and
  `only through the passed north filtered vent`; the expected strings are
  `both latched` and `north filtered vent`. The available originals support those
  qualifiers according to the blinded judgment.

These are clear candidates for convention sensitivity. Other mismatches include
lists represented as prose, authority IDs instead of names, and `null` versus
negative/unknown statements. Those can reflect different output contracts or
epistemic meanings and must not all be dismissed as wording. Incomplete evidence,
missing acceptance receipts, unjustified holds/readiness and absent artifacts
remain separate concerns. Exact source bundles were non-exhaustive, so supported
alternative citation sets also need independent gold adjudication.

## Reproducible record and limits

[semantic-review.json](semantic-review.json) publishes the fictional packets,
original whole texts/fragments, all per-case judgments/rationales, post-review
case-to-trial links, preserved field errors and descriptive intersections. It
contains no private host paths, authentication or native traces. Reviewer method
and packet hashes bind the private collection receipts without publishing them.
`python check_review.py` checks the 123/144 census, artifact identity, requested
keys, supplied judgment citations, frozen reader-file hash and recomputed count
intersections; it does not judge semantic claims or alter primary scores.

One LLM rating per case, related authored templates, potentially inferable
conditions, original-only review and shared model biases limit interpretation.
There is no corrected population accuracy estimate, independent human gold,
semantic engine ranking or repair of fresh-discovery failures. The next study
should preregister explicit answer types/action vocabulary and review labels,
adjudicate alternative sufficient sets, and obtain human checks and duplicate
ratings. [Primary report](REPORT.md), [execution audit](AUDIT.md),
[frozen reader results](reader-results.json).
