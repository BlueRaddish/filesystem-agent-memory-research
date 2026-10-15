# Prospective state experiment

Sealed before outcome collection, 2026-10-15 UTC. This is a new engineered
scaffold, not natural PARA validation or independent natural histories.

Generate 96 fictional access/release histories using independent seeded PRNG
instances (seeds 71000–71095). Seeds 71000–71023 are descriptive development;
71024–71095 are descriptive held-out. No outcome-dependent tuning is permitted.
All 96 cases run in all 12 arms: exact already-seen ledger off/on ×
complementary facet selection off/on × authored navigation edges real/absent/
shuffled. This is a paired census, not 1,152 independent histories.

Every history has 24 source records, each exactly 768 UTF-8 bytes. Source JSON
contains fictional IDs, facet, kind, tick, scope, actor, event value, provenance
links, discovery rank, and padding. A source policy defines the authorized actor;
an authoritative closed-log seal lists six scope-event IDs, three per facet.
Six other records have unauthorized actors; ten are unrelated-scope filler.
Closed log membership is authored source evidence, not evaluator-only truth.
The seal makes proof of absence possible in this deliberately closed world.
Source links point from older events to their replacements. Shuffling permutes
navigation targets only in selector input; original source bytes remain intact.
No arm changes candidate units, queries, source text or returned record bytes.

Each arm has four calls, two record slots/call, at most eight records and 6,144
source bytes. The exact ledger prevents repeated IDs. Complementary selection
penalizes repeated event facets by 30 rank units within each call. Source policy
and seal rank above all events; root event rank exceeds later event rank.
Discovered forward links receive a 200 rank-unit boost. Absent links receive no
boost; shuffled links use a deterministic bijection of existing targets. Ties
break by record ID. Without a ledger, previously selected records remain eligible.
Facets, ranks and links are deliberately authored retrieval aids.

The actual deterministic consumer parses selected original sources, validates
authority, and replays latest authorized scope events by tick. Complete task
proof requires policy, seal, and every sealed event (eight unique records).
It continues until complete or budget exhausted. Incomplete answers retain
explicit provisional status; safe authorization requires complete proof.
Report complete proof, correct two-field provisional answer, provisional false
authorization, safe false authorization, unique records, source bytes, and the
first round at which a naive policy-plus-one-event-per-facet sufficiency rule
would stop without complete proof. No LLM ability or natural retrieval is tested.

Evaluator truth is independently replayed from full source bytes. Selectors
receive only a SourceView (ID, facet, kind, rank, navigation IDs), with no gold,
answer, expected, required/support IDs, authority judgments or full-source truth.
Source log membership is parsed only by the consumer. Source generation, plan,
source partition and hashes are sealed in seal.json before census collection.

First meaningful selfchecks: currentness after revoke; absent/wrong edge behavior;
naive false-sufficiency detection; exact-byte reconstruction; selector field
boundary and hidden-truth perturbation. Preserve failures and amendments. Run
the real census and a separate audit consuming every stored packet. Export
compact JSON, source/reproduction code, tables, three PNG/SVG figure pairs,
factual report and command receipts. Bootstrap paired history differences with
fixed seed 9173, 2,000 resamples; descriptive intervals are scaffold-specific.

Verification route: `python evaluation/sprint-2026-10-15/state/state_lab.py seal`,
then `selfcheck`, `run`, `audit`, and `render`, in that order. `audit` independently
reconstructs selected source bytes, consumer outputs and complete census keys.
No old experiment, model/provider, install, config, commit, push or PARA writes.
