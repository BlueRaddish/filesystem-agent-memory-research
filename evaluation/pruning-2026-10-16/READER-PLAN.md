# Source-only reader follow-up

This prospective supplement implements the optional follow-up in the sealed
[main plan](PLAN.md). Its sampling and context assignment are fixed before root
inspects deterministic outcome tables. It tests interpretation of supplied
packets, separately from autonomous navigation or maintenance.

Twelve probes use the last six scenarios in the sealed collector's order, seed
zero, high density, epoch 32, with the current and standing queries. The four
fixed cells are `all|off|global`, `ttl8|off|global`,
`ttl8|scheduled_cold|global`, and `latest_dependencies|off|linked`.
There are 48 planned packet answers; no outcome-based substitution or retry is
allowed. A failed or missing answer remains in its planned denominator.

For scenario index `f` (zero through five), task `t` (current zero, standing one)
and cell `a` (zero through three), context assignment is
`(2*f + t + 2*a) % 8`. Each of eight fresh reader contexts receives six packets,
one from each scenario, with opaque case IDs and without arm labels, gold,
full histories, deterministic answers or project navigation. Each packet is the
exact concatenation of rendered original sources in actual selected order, at
most 8,192 UTF-8 bytes. Query text and common instructions are additional prompt
bytes, measured separately. A context receives only one packet per underlying
scenario, preventing within-context access to another arm of the same history.
Contexts are not independent model families or human readers; six answers in
each context share state. Fresh conversation context is not OS isolation or
proof of an empty runtime.

Readers return value or null, governing source ID or null, source IDs cited,
whether the supplied sources support their answer, missing referenced IDs and a
short explanation. They may abstain when the packet lacks an answer. They must
use only that case's packet, not other cases or outside tools. The reader has
read/write tool access to the staged input and output files; these instructions
are a logical boundary, not an operating-system sandbox.

The fixed target is `gpt-6.1-sol`, requested through the collaboration tool.
Record the requested identity and actual tool/context IDs; a request does not
independently attest backend implementation. No model settings are tuned from
answers. Source packets are fictional and exclude private vault contents.

Mechanical scoring compares returned values and cited IDs with the already
sealed complete-source truth. Report value agreement, complete gold support
actually present in the packet, and complete citations drawn only from that
packet separately. Also report abstention and invalid/missing outputs. A
source-supported abstention can be appropriate despite failing a task whose
answer was unavailable; it must not be described as a fabricated answer.
Mechanical citation matching does not establish semantic entailment or human
truth. No new semantic adjudicator will regrade the original deterministic
study. Aggregate results are exploratory paired observations on the twelve
fixed probes, not a population accuracy estimate or architecture ranking.

The report must distinguish planned, staged, executed and accepted counts and
retain original output bytes. Staging checks exact source hashes, trial census,
all 48 distinct assignments and the absence of condition/gold fields from reader
inputs. Inputs, outputs, opaque mapping, sampling manifest and collection errors
are retained. A read-only checker must reject invented citations, duplicate
case IDs and a changed packet digest. Never overwrite or retry a completed
reader batch to improve its answer.
