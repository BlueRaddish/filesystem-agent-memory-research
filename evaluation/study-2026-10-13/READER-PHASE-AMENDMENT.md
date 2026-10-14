# Operational amendment: oracle/discovery readers before direct readers

**Prospective; NOT EXECUTED.** The resumed one-worker neural grid failed a native
allocation under a nearly exhausted system commit limit after the user returned
on October 14 UTC. Existing grid checkpoints remain retained; no main readers had
started when this amendment was designed. This amendment permits a separate
lightweight cohort of the frozen 24 oracle and 48 discovery jobs before the 120
direct readers and neural grid finish. It changes resource scheduling and global
block/time order, not any task, prompt, model configuration, artifact contract,
source packet algorithm, failure envelope or primary scoring endpoint.

## Exact consuming path

[run_reader_cohort.py](run_reader_cohort.py) selects jobs only by frozen schedule
`block in {oracle, discovery}`, preserving their relative order from the original
192-job randomized schedule. Fixed concurrency is two workers. Submission order
is preserved; concurrent execution/completion times are not a serial ordering
guarantee. No job is selected by a score, readiness, answer, failure or retrieval
result. The original source functions `trial`, `invoke_recorded`, source tools,
typed scoring and writing run unchanged.

The worker `execute` exists only inside the frozen CLI's main branch. The helper
verifies the exact core freeze and all 32 listed file pins (33 anchors including
the freeze bytes), then extracts exactly one undecorated `FunctionDef execute`
from the cryptographically pinned reader source. It compiles that AST with the
original imported module globals and the same work/checkpoint/command/runtime/
fingerprint values as the frozen CLI. No copied scoring or recovery implementation
is introduced. The function's AST and exact source-segment digests are retained.
This method deliberately depends on that exact frozen source layout; a future
shared-worker refactor belongs to a new study. Unverified arbitrary code is never
extracted. Core files and their freeze remain unchanged.

## Before calls and on interruption

`--prepare` performs no reader calls. It binds this helper, this amendment, all
core anchors, the exact selected schedule, function identity, runtime-public file,
private adapter command, current Python process image, adapter/wrapper sources,
pinned native binary and existing cohort checkpoint bytes in a new private
`reader-cohort/manifest.json`. All runtime paths must remain outside the repository;
source hashes must match the frozen runtime-public fingerprints. The command is
the existing Python `-X utf8` wrapper-source argv; no shell interpolation is used.
Without importing either private module, restricted literal AST checks link the
executed wrapper's `BASE` to the supplied adapter, the adapter's `ROOT` to its
source directory and its `EXE` to the supplied pinned binary. Hash-equal files at
unexecuted alternate paths do not satisfy these dependency links.
The command's interpreter alias string and canonical identity remain separate
from the readable process-image path/hash. On Windows, `GetModuleFileNameW(NULL)`
identifies the running Python image; an App Execution Alias is not treated as
readable executable bytes. This binding does not attest future alias routing.

Root must independently review the exact new files and private manifest, freeze
their method, publish the amendment, and issue private exact-manifest
`review-clearance.json` before `--run`. This helper and its author do not issue
that clearance. An explicit manifest SHA is required for execution. Actual 72
trials, with at most 408 response calls (24 oracle plus 48 times eight discovery
responses), remain a separate consuming-path verification, not a result
established by compilation, source review or fake fixtures.

The original worker returns existing checkpoints verbatim, including recorded
errors, instead of rerunning them. The original pending-call mechanism retains
unknown interrupted calls and cached rejected calls without a scored retry. The
coordinator additionally checks checkpoint byte hashes and exact job/fingerprint
identity, saves private progress atomically with flush/fsync, and requires explicit
`--resume` after a started stage. A checkpoint saved just before coordinator
interruption can be validated and recorded as recovered; it is not regenerated.
All original error/fault semantics and scheduled denominators stay intact.

One coordinator must own these reader checkpoints. Its exclusive local lock
prevents another instance of this helper; it cannot lock the separate frozen CLI
or another host. A hard kill leaves the lock for root to inspect and remove only
after confirming no live cohort process. Failed state persistence or mutated
inputs/checkpoints stops the coordinator; it does not license restarting calls.
On a future, validation or persistence error, cancel all unstarted queued trials
before waiting. Already running original jobs may finish their bounded response
loop; retain their actual checkpoints. A private coordinator-failure receipt
records failure phase/class, cancelled and unsubmitted/not-started counts and
retained checkpoint hashes. It does not invent failed rows for unstarted jobs.
If failure-receipt persistence also fails, existing original checkpoints still
remain on disk, with the coordinator incomplete and no automatic retry.
No native account data, host paths, call traces or raw diagnostics are published.

Completion writes only a **private 72-job cohort receipt**. It never writes a
premature public `reader-results.json` or claims the full 192 readers are complete.
Later the unchanged frozen CLI reuses these 72 checkpoints and executes the 120
direct readers, with a fresh explicit coordinator/resource guard. The historical
resource wrapper rejects reader artifacts and must not be presented as compatible
with that later resume. No new guard or actual run is established by this amendment.

## Interpretation and verification limits

Oracle diagnostics and discovery observations now occur earlier than direct
readers. Global block/time order and shared-host load are confounded in
between-block comparisons; this is a disclosed operational amendment, not the
original global random order. Within the discovery factorial, frozen assignment,
relative submission order, task/source conditions and primary scoring are retained.
Two workers differ from the frozen default six, so no identical latency/workload
claim follows. Local freshness remains the frozen protocol's claim and does not
attest remote provider erasure or absence of hidden caches.

Verification reuses the repository route `python scripts/check_repository.py`
and the original frozen consuming worker in this helper's `--self-check`. The
self-check uses fake trial/transport functions and temporary private fixtures for
normal writes, cached errors, mutated source/checkpoint rejection, false cached
calls and interrupted pending calls. It performs no actual bank-outcome review,
model load or provider call. Real 72-trial completion, runtime acceptance, actual
artifact/source exposure and final 192-reader assembly remain unreached until
explicitly authorized collection and independent outcome audits.
