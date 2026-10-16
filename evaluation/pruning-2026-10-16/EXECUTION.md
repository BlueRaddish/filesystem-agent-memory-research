# Execution and verification

One accepted full collection completed with exit code zero, without rerunning or
changing frozen conditions. The original `run/execution.json` deliberately says
`COLLECTED_NOT_INDEPENDENTLY_AUDITED`; later independent acceptance is recorded
separately and does not rewrite that execution receipt.

| Item | Identity / count |
| --- | --- |
| Accepted seal file SHA-256 | `b5bddbda9073ad9ef8961c5c6ab3e5d964a3c5e5c7b61a5cc0002320cf70458b` |
| PLAN SHA-256 | `10ce93197fa97437a3b511e34b5cabfefd760666ba2f584f6f63f9e4be002b77` |
| Source-only core SHA-256 | `09415169c94bcdd28c04f9b4036373e4af1d988e26f6785969bb2d4159032d6d` |
| Collector SHA-256 | `007ba66f8b9847a4a61ffffa836ae50e50a7dcf8c26939c81c5dd32e22b9d131` |
| Self-checks | 19 passed |
| Workload | 32 worlds, eight shared-backbone overlays, two seeds, two matched densities |
| Query schedule | 32 epochs, eight checkpoints, four tasks; 1,024 queries |
| Arms | Seven policies × three archive modes × three discovery methods = 63 |
| Complete query-arm rows | 64,512 |
| Exact active-set checkpoints | 16,128 |
| Maintenance rows | 64,512 |
| Source instances | 6,024 (density-pair duplicates included) |
| Scientific figures | Six PNG/SVG pairs, all six PNGs individually inspected |

Before full collection, static review found unordered set iteration in floating
BM25 accumulation. Query terms were sorted, all 19 self-checks rerun, and the
precollection seal replaced once. The superseded seal is retained privately.
No full-run outcome existed before this correction. No sealed source changed
after acceptance.

After figure inspection, Figure 5's colorbar was moved outside the data cells.
Only its PNG and SVG changed; all other ten exports were byte-identical. The
old pair and manifest are preserved privately. No numeric data changed.

## Read-only checks

From this directory, the frozen interface check is:

```sh
python pruning_lab.py --self-check
```

This prints the checks and writes no output. Independent replay completed for
all 64,512 trials, 258,048 calls, 64,512 maintenance rows and 16,128 snapshots,
with nine rejected corruption controls. Independent table derivation checked
54,896 numeric fields across 3,591 cells with five rejected controls. The
[acceptance record](ACCEPTANCE.json) links the retained receipts. A successful
self-check is not a substitute for full output reconstruction.

```sh
python audit_pruning.py --run run
python check_pruning_tables.py --run run --tables tables.json
```

These commands are read-only by default. A new receipt can be requested
explicitly; existing receipt destinations are refused. The separate
[reader report](READER-REPORT.md) documents the later 48-answer follow-up,
its source bindings and seven independently rejected corruption controls.

## Reproduction in an isolated new directory

The original actual commands were:

```sh
python pruning_lab.py --self-check
python pruning_lab.py --seal
python pruning_lab.py --run run
python analyze_pruning.py run tables.json
python render_pruning.py tables.json figures
```

`--seal`, `--run`, analysis and rendering are **generation commands**, not
read-only checks. They refuse already existing destinations. An existing seal
must remain unchanged; it is verified by the collector. For an independent
reproduction, copy the sealed sources and seal to a disposable directory and
choose a new output path:

```sh
python pruning_lab.py --self-check
python pruning_lab.py --run reproduced-run
python analyze_pruning.py reproduced-run reproduced-tables.json
python render_pruning.py reproduced-tables.json reproduced-figures
```

Python 3.10 or later is required; the collector and analysis use the standard
library. Scientific rendering uses the installed Matplotlib/NumPy runtime.
No provider calls, downloads, private corpus or machine-specific paths are
required. CPU and elapsed times vary, so whole-run byte identity is not expected
for those timing-bearing receipts. Per-source hashes, world/query generation,
deterministic rankings and non-timing results have fixed definitions.

## Stream schema and accounting

All compressed files are UTF-8 JSON objects, one per line, inside deterministic
gzip framing (`mtime=0`, no embedded filename). Source-bank and gold JSON are
stored separately. The manifest records each file's SHA-256 and compressed /
uncompressed sizes. Trials contain no gold answers: they retain identity,
source-only answer, actual selected IDs and four calls' pre-call reader states,
store choices, selected scores, candidate work, dependency probes and framed
byte charges. Scores are written only after the complete trial stream closes.

Snapshots retain the exact active ID set, its canonical digest and the prior
access-ledger digest. Each arm starts with an empty ledger. The fixed query
order increments a per-arm sequence once per query; every actually selected ID
increments its count once and records that sequence as its latest access. Cold
selections are buffered for next-epoch quota admission. Maintenance rows retain
promoted eligibility IDs, arrivals, removals, scoped operations, active and total
retained source bytes, and measured retention CPU duration.

Source metadata is intentionally clean and supplied. Gold is complete-source
replay; the reader sees returned source text only. The separation is logical in
one process, not OS isolation. Source-only search pretokenizes the complete
authored bank, but candidate pools and document frequencies use only arrived,
available originals. Future-content perturbation checks establish this boundary
for the exercised fixtures, not a security sandbox.
