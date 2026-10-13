# Blind semantic bank review

The completed blind review rederived all 288 tasks across all 96 authored fictional histories. A separate comparison performed after the judgments were saved found exact typed answer and status agreement for 288/288 tasks, status agreement for 288/288, and zero mismatches. The judgments contain 240 `ready` results and 48 `hold` results. All 387 cited support spans have valid Unicode code point bounds and name present original source records.

This is a supplemental coherence check under one LLM's judgment and the supplied normal answer contracts. It is not semantic proof, human validation, a citation entailment test, a comprehension test, or a representative population accuracy estimate. The authored bank, authored keys and primary study scores remain unchanged.

The complete public comparison is in [bank-semantic-review.json](bank-semantic-review.json). It preserves every prediction, original-cited rationale, ambiguity flag and reason, original support span, authored expected answer, and recomputed agreement result. Each case has its blinded input hash, a separately computable canonical judgment hash, and an attested original raw judgment byte hash. Its source prose is in [challenge-bank.json](challenge-bank.json).

## Review method and blinding

One LLM agent reviewed full source packets sequentially across the 96 cases and saved one judgment file per case. Task context was shared across cases; this was not a fresh independent test session for each case. The underlying model identity and configuration were not independently attested, so no exact model identity or distinct model-family independence claim is made.

The reviewer received source prose, record metadata, declared links, queries and typed answer contracts. Authored expected answers, gold rationales, declared evidence support sets and spans, stratum, template family, split, variants, experimental arm IDs, and the private case-to-family key were withheld until the original blind review was complete. Original record/task identifiers and clues in the prose remained visible. The opaque case labels therefore describe a blinded input boundary, not anonymous or clue-free histories.

Cases were assigned `CASE-001` through `CASE-096` by ascending SHA256 of the UTF-8 string `blind-bank-v1:` followed by the family ID. Record and task fields crossed that boundary through explicit allowlists. The portable checker independently rebuilds all 96 input payloads and the original manifest from the public bank, including their exact UTF-8 serialization and hashes.

The reviewer used the requested contract, including exact identifiers, ordered sequences, component sets, raw unreduced fractions, effective dates, scope and the hold policy. Earlier authored/import times were not treated as effective times. Present final governing originals could close earlier packet gaps or reconcile coequal orders. Unsupported values remained null while established partial facts were retained.

## Comparison results

| Check | Result |
| --- | ---: |
| Authored fictional histories reviewed | 96/96 |
| Tasks rederived | 288/288 |
| Exact typed answer and status agreement | 288/288 |
| Status agreement | 288/288 |
| Mismatches | 0 |
| Ready judgments | 240 |
| Hold judgments / ambiguity flags | 48 / 48 |
| Original support spans with valid bounds | 387/387 |

| Hold reason in the reviewer judgments | Tasks |
| --- | ---: |
| `required_source_missing` | 18 |
| `scope_not_established` | 15 |
| `conflicting_authority` | 15 |

Examples illustrate what was preserved in the judgments; they are not additional independently validated semantic findings:

- `CASE-003 / N035-T1` holds the release status because original release A (`N035-R001`) and continuation B (`N035-R004`) are coequal and unreconciled. Release discussion remains true.
- `CASE-014 / N040-T2` is ready because the final governing experimental overlay (`N040-R005`) supplies the formerly absent exhaustive requirements before the query cutoff. The earlier draft's visible component remains a separate fact.
- `CASE-035 / N064-T1` records physical holder `crew-4D` from the matched receipt (`N064-R002`), while the earlier dispatch's destination was `crew-4C` (`N064-R011`).
- `CASE-074 / N034-T1` is ready with `hold_released: false` because the final adjudication (`N034-R001`) expressly settles the earlier conflict. An explicit negative decision differs from an unsupported value.

## Portable verification and provenance

Run from this study directory:

```text
python check_bank_semantics.py
```

[check_bank_semantics.py](check_bank_semantics.py) uses the standard library and the frozen [artifact_contract.py](artifact_contract.py) and [study_common.py](study_common.py) helpers. It checks the frozen bank/helper hashes; the allowlist-based opaque input ordering and exact blinded payload/manifest reconstruction; all case/task census links; strict answer contracts and boolean types; authored-key comparisons; canonical judgment hashes; original-source evidence identities; and Unicode code point span bounds. Its runnable negative checks reject the wrong input digest, out-of-range or boolean span bounds, derived-record citations, duplicate JSON keys, and an integer substituted for a boolean. `--self-check-only` runs those small checks without loading the package.

The checker returned `PASS` for the published comparison: 96 cases, 288 tasks, 288 typed answer/status matches, zero mismatches, and 387 bounded original-source spans. Coordinate and schema checks do not establish that cited prose entails a rationale or every answer. The checker does not compare citations to authored support bundles or validate comprehension.

| Provenance anchor | SHA256 |
| --- | --- |
| Frozen public fictional bank | `280e6be3f7380ed9c0bc1dbe3ec75dfba136113f230d08751e0f316b67cf9760` |
| Rebuilt original blinded input manifest | `937bf53974a31306f78c670325ed72a753b49b7d07aa9d393f3d17b401d9a66d` |
| Retained private input-only receipt | `85a08a278fbd7a8802fb32809aed664c6f793ad1fe370ed22788363691b9835d` |
| Retained separate private comparison | `e7317e3972592170405c4ba1566b57361c06ce166da68d0162a7fc8e07d84c3f` |
| Public comparison package | `b3549e2a444fbc0166c53019576a17ddbe217cf52f5e4d2d3950fdbe90cca3b9` |

Original raw judgment bytes and their execution proof are retained privately without alteration. Per-case raw hashes in the package are attestations linked to that proof; the public checker does not reconstruct or independently verify unavailable raw bytes. Public serialization can reorder object keys, so the package separately exposes a canonical judgment hash computed from each public `review` object using the documented deterministic JSON recipe. That canonical hash and the raw byte attestation have distinct meanings.

All 96 histories are authored fixtures. Full-packet review with shared cross-case context does not estimate behavior on new populations, partial retrieval, or fresh per-case sessions. The 288/288 agreement supports the stated coherence comparison and these packaging checks only.
