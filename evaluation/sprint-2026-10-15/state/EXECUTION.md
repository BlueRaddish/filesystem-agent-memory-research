# Execution record

Completed 2026-10-15 UTC; this record was assembled at 06:24 UTC from actual
tool results and saved receipts. Commands ran through captured shell pipes;
no child processes, desktop shells, models or provider calls were launched.
The only changed repository scope is this newly created state directory.

An initial directory discovery exited 1 because neither proposed state output
directory existed. It found no predecessor files to recover or overwrite.
This is not a collection failure. No census, analysis or check failed; no
post-result retrieval-policy, scoring, source, seed or budget change was made.

Commands ran from the repository root in this order. Every listed command
exited 0. The precollection seal was sent to the coordinating agent before
selfchecks or collection. All stages use the frozen source except the separate
postcollection verification checker described below.

| Command suffix | Actual result | Retained evidence |
|---|---|---|
| `state_lab.py seal` | 96 source histories; plan/code/source partition sealed | seal.json, sources.json |
| `state_lab.py selfcheck` | 10 specified boundary/currentness checks passed | selfcheck-receipt.json |
| `state_lab.py run` | 1,152 trials; 96 histories × 12 arms | results.json, run-receipt.json |
| `state_lab.py audit` | All 1,152 packets/outputs and 2,304 source widths passed | audit-receipt.json |
| `state_lab.py render` | 36 cohort-arm table rows, 18 paired effects, three PNG/SVG pairs | render-receipt.json, tables.json, paired-effects.json |
| `independent_check.py` | All 1,152 independently replayed; five corruptions rejected | independent-check-receipt.json |
| `check_utility.py` | All 12 arm utility rows matched source replay | utility-table.json |

Each command prefix is `python evaluation/sprint-2026-10-15/state/`.
The independent checker was added after collection to strengthen verification;
it imports no experiment code and changes no frozen inputs or outcomes.
After root review its default route was made read-only; an explicit
`--receipt` flag retains the optional receipt-writing route. The read-only
route and explicit receipt route were both executed successfully. The original
frozen experiment source was not edited. A postcollection utility table derived
from existing outcomes records safe true grants and abstention costs; it changes
no outcome, ranking, proof rule, budget, or source record.
It reconstructs selected-event state separately from full-source authority
state. An invented grant in a revoked case, incorrect proof flag, altered packet
hash, safe authorization without proof and an invalid census arm are rejected.
Root review identified that the initial checker required only row/unique/seed
counts, not exact per-seed arm membership. Current data independently passed;
the checker was hardened to exact Cartesian keys without changing outcomes.
The initial checker and three-mutation receipt are retained privately.
This is an independent implementation, not an
independent human review or a new naturally generated task bank.

Frozen hashes:

| Input | SHA-256 |
|---|---|
| PLAN.md | f66ffca3bc993937303d90ca78159cbc5da22fb8f4719b2a0dbd4aca39cfc920 |
| state_lab.py | 4803ad88c3539251e1063e68561bd240f0c707ae8261f15a0d0dab2ff576e62e |
| sources.json | e9788c047383f2946d95a4006ccb803d6a8e9542d36df5bb23e87a23eb04099a |
| results.json | b76a975cd802f653c7e5f889415e74398b3e2bdc973f2dc5eff15b2070e2e4a1 |

`artifact-manifest.json` records SHA-256 and byte count for all delivered files
except itself; its entries include figures, data tables and verification code.
JSON outputs use compact object/array serialization, not JSONL. The 4,608 calls
deliver 9,216 source slots and 7,077,888 total source bytes; repeated slots count
against budget. The consumer only authorizes with proof; provisional decisions
are explicitly identified. All sources and actors were generated fictionally.

All three PNGs were opened individually after rendering. Titles, legends, arm
labels and axes were readable; the same plotting call writes paired SVGs.
No old experiment or repository-wide expensive audit was rerun. The historical
README's broad scan and earlier audit are root-owned; this lane's targeted
reconstruction provides evidence only for the new state scaffold. Real users,
external tools, live authorization, natural filing systems and LLM readers are
outside the executed scope. No PARA, commit, push or global-config writes ran.
