# Postcollection analysis compatibility

This compatibility entrypoint was introduced after collection. At publication,
its actual analysis invocation has not been executed. Original collection and
failure evidence remain retained, and the main outcome analysis and all 26
PNG/SVG figure-pair reviews remain pending.

The original frozen analyzer failed with `KeyError: 'text'`. The reader producer
scored text-bearing observations in memory, then serialized the compact fields
`id`, `start`, `end`, and `source_hash`. The analyzer forwarded those compact
observations to a scorer that also expects `text`. This is a consumer format
mismatch; it does not establish missing source exposure or an outcome failure.
The original failed continuation receipt is retained at SHA-256
`ae0eec80725e8fe6ffc189bd24992501205560dd3d1e5cde6fa03ff0ff77b1b9`;
its analysis stderr is retained at
`f648968f2c7b53faacec090245e656b202ede1e478af682548bbb8f4850f51ed`.

The full raw execution audit reports `passed` at
`2026-10-14T13:58:04.702968 UTC`. Its exact JSON SHA-256 is
`474cad80ed8f3286f11555fc945516735f6a7cec406bf13bc6112e98f0d9ee72`,
and the accepted auditor source SHA-256 is
`649640c0faae4a6bd9f60854a13e78c13613340fc81665ec3bb1418207c48f75`.
The retained execution route also has a root-observed numeric exit 0. The raw
audit reconstructed 114,048 packets, 12,096 rankings, 378 timing observations,
192 artifacts and checker replays, 509 accepted local freshness calls,
48 discovery histories, 12,800 mechanical maintenance events and 173 historical
baseline blobs. One reader failure remains recorded. These counts describe the
audit census, not semantic accuracy or a completed analysis. The raw JSON,
source/control records and actual process return are execution evidence;
this disclosure and its checksums alone are not proof of execution.

The new [compatibility entrypoint](analysis_observation_compatibility.py) scopes
only the reader's support-function alias to the frozen analyzer's existing
normalization helper. The helper validates the document ID, UTF-8 body hash,
and half-open Unicode character bounds before recovering the exact body slice.
Retained text must already equal that slice. Original and derived document
handling remains the frozen helper's behavior.

All 32 original frozen inputs, collected result files, failed invocation,
rankings, packing, artifacts, scoring implementations and statistical
specification remain unchanged. The original freeze SHA-256 is
`fda01f88f50dbb6e66a312ca9ab775c8603643ebe8b7f74b596a7250bc39524c`.
No artifact or input is rewritten by this compatibility boundary. The complete
original analysis argv is forwarded unchanged. Frozen `analysis.json` metadata
continues to name the original analyzer; separate private provenance names the
wrapper, audit, input bindings, alias semantics and invocation state. Exceptions
propagate. A unique provenance directory is required and cannot be reused.

The wrapper source SHA-256 is
`9cab6cb9f3a55a68db2015855005d24de51c80ab8d85e25f7abbf003f6b3ad12`.
Before an explicit run, the trusted caller supplies that exact source hash and
the exact accepted raw audit JSON hash. The guard checks a passed audit with the
accepted verifier and original freeze, actual boolean private-execution and
cache checks, and frozen packer replay enabled. It binds the four current main
result file hashes to the audit and verifies all 32 frozen inputs. These are
trusted-caller fixity checks, not cryptographic attestation that an audit ran.
Root review separately binds the original invocation's working directory,
complete argv, accepted audit and current result hashes before execution.

Fictional source and consuming tests passed for the observation boundary,
source/audit rejection, unchanged argv, separate provenance and propagated
failures. Independent review confirmed the reviewed normalization helper alias
and unchanged scorer logic. An earlier test-harness wording mismatch is retained
separately; Python 3.13 rejected malformed JSON with a different diagnostic, and
the corrected fixture checks the rejection type. Python 3.10 grammar parsing
passed and hashing streams 1 MiB blocks; a Python 3.10 runtime was not exercised.
Neither fixture checks nor a passed execution audit establish semantic support,
population accuracy, a unique winning policy or causal timing effects on a
shared host. Actual analysis and figure inspection remain separate gates.

The source-only checks, from the repository root, are:

```sh
python evaluation/study-2026-10-13/analysis_observation_compatibility.py --self-check
python evaluation/study-2026-10-13/check_reader_review.py --self-check
```

The separately accepted [mechanical reader-review checker](check_reader_review.py)
has source SHA-256
`16107e4e83ddb623c404e667024c460605bfda67fcd8133e32e49f94cf8cecf5`.
Its fictional self-check creates no semantic judgments. Actual blinded artifact
review requires a separately accepted preparation and remains unexecuted.

The compatibility command has this shape; tokens after `--` must be the complete
original analyzer argv, including its program name. Exact private execution
paths and invocation receipts remain outside this public disclosure.

```text
python analysis_observation_compatibility.py --run --study STUDY_DIR --source-sha256 WRAPPER_SHA256 --audit-json RAW_AUDIT_JSON --audit-sha256 ACCEPTED_RAW_AUDIT_SHA256 --provenance-dir NEW_PRIVATE_PROVENANCE_DIR -- analyze_results.py ORIGINAL_ANALYSIS_ARGUMENTS
```
