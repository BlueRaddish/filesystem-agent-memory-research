# Prospective longitudinal pruning experiment

Status: prospective, before collection. This is a new AI-authored synthetic,
deterministic mechanism experiment. No production memory is deleted or moved.

## Question and units

When a memory collection grows, which query-blind retention policies reduce
active search work without losing current, historical, dormant or qualifying
source evidence? Does a separately charged immutable archive change that tradeoff?

Eight engineered workload scenarios have two seeded parameterizations and two noise growth
rates each: **32 worlds**, **32 epochs**, checkpoints every four epochs, four
queries per checkpoint (**1,024 queries**). Periodic corrections, old standing
constraints, dormant reactivation, historical rollback, cross-project
dependencies, lexical near duplicates, topic/access shift and expiring exceptions
are overlays on a shared authored backbone (old guard, version history and
bundle/license dependency). They are not eight independent causal mechanisms or
structurally held-out confirmation data. No outcome tuning is permitted after
sealing. Seeds are not independent mechanisms; queries and arms are repeated
measures within worlds. Independently authored topologies remain future work.

## Crossed interventions

Seven retention policies: retain all; age TTL eight epochs; LRU 96 records; LFU
96 records; latest revision per supplied project/key; latest plus transitive
explicit source dependencies; deterministic seeded random demotion to 96.
All are query blind. They receive only arrived source metadata and past actual
selected-record access, never the query bank, gold, future records or answers.
TTL includes records whose age is exactly eight and evicts older records.
LRU ties use created time then ID; LFU ties use last access, created time then ID.
Random demotion uses a stable seeded hash over epoch and source ID. Latest uses
source-visible effective time, created time and ID. These two deliberately naive
compaction policies ignore expiry when choosing what to keep: an expired latest
exception can discard its still-applicable older base. Dependency guarding alone
does not make compaction expiry-aware. They do not infer future usefulness or
retain every historical variant. A later-imported correction has an earlier effective time.

Each policy crosses three archive modes and three discovery routes: global BM25;
supplied-project-index BM25; supplied-project-index BM25 plus real dependency
expansion (depth two, maximum eight expansions per call). **63 arms**, **64,512
query trials**. These are abstract organization/access-path simulations, not OS
filesystem implementations or latency comparisons. A layout-only renaming
negative control leaves global rankings unchanged.

Retention executes once per epoch, after arrivals and before any checkpoint
query is disclosed. In the three quota policies, actual cold-source reads are
buffered and become eligible for promotion at the next epoch's retention, then
the same 96-record cap applies. Promotion preserves original source age. Other
policies do not promote archive reads. Each arm
has its own endogenous access ledger. Query order is fixed current, standing,
historical, dependency/exception. This is a policy-plus-feedback trajectory,
not a common external popularity trace. At each checkpoint the exact active IDs,
active-set digest and access-ledger digest are retained.

## Retrieval and budget

Every arm has **8,192 rendered UTF-8 bytes** and at most **four calls**, with up to
six new records per call. Whole original records, compact source framing and
dependency expansions all consume the same returned-byte budget. There is no
free discarded text or source preview. A candidate that cannot fit is skipped;
later smaller unseen records may fit. All-retained global search has genuine
unseen paging across all four calls.

Calls one and two search the active store. At call three, `unresolved_only` arms
switch calls three and four to a nonempty cold store only when the source-only reader
is unknown or has an explicit unresolved dependency. `scheduled_cold` arms always
reserve calls three and four for a nonempty cold store, including when an active
answer appears complete. Otherwise all four calls continue active paging.
Archive-off arms always page active. The trigger is
observable and never uses gold correctness or missing gold IDs. Referenced IDs
are exact source-visible retrieval cues. Global search may resolve them through
exact-ID lookup; project routing restricts discovery to the supplied project;
linked routing can follow explicit cross-project references. Cold and active
candidate scans, calls, expansion probes and returned bytes are charged.

BM25 tokenization and scoring constants, tie breaks and source-size distribution
are fixed in code. Within-pool document frequencies are used. Candidate scoring
work is counted separately from maintenance operations and measured aggregate
CPU time; work counts are not speed estimates. Candidate counts include the
scoped documents examined by each call; term work is candidate count times query
term count. They omit index construction/tokenization, document-frequency passes,
sort comparisons, parsing and Python overhead. Bodies include short and longer
records, original source hashes, stable IDs, created/effective/expiry times,
project/key/value and explicit dependencies. All search metadata is supplied
source information, not learned extraction.

## Reader, gold and outcomes

The deterministic reader consumes only returned original source records and the
query (project, key, as-of time, lexical cue). It parses assertion text, chooses
the latest applicable effective record, excludes expired records, and requires
its explicit dependencies recursively. Later-created corrections override
earlier imports at the same effective time. The independent complete-source
replay defines the gold governing record and required dependency closure.
Source selection and gold scoring are logically separated in one process, not
OS isolation. There is no LLM answer or real human continuation claim.

Primary outcome: correct deterministic value **and** all gold required sources
returned and source-only reader dependency checks complete. Also report value
correctness, stale values, unknown answers, unresolved qualifiers, missing
required records under logical archive-off loss, historical/dormant/rare task
loss, active and retained original bytes, candidate work, maintenance operations,
calls and rendered bytes. With archive on, every original is retained in the
immutable archive; active byte reduction is not total storage reduction.
Archive off is logical irreversible unavailability for that arm; evaluator
originals remain preserved and do not become retriever-accessible.

All outcomes are paired within each query/world and shown by mechanism, task and
epoch. No population significance or count of independent trials is inferred
from repeated arm/query rows. Paired differences against retain-all within the
same retrieval/archive condition are descriptive.

The low/high density pair shares all governing sources and its entire query
schedule; only distractor counts differ (three versus eight arrivals per epoch).
Standing and fixed-as-of diagnostic questions repeat unchanged at every
checkpoint, except the topic-shift mechanism's declared standing-query schedule.
Question as-of times and arrived-source corrections remain explicit, so density
and age effects are not conflated with silently changed questions.

## Freeze, checks and collection

Before collection: run `python pruning_lab.py --self-check`, write `seal.json`
binding this plan and both executable source modules, and obtain root acceptance.
No full run until acceptance. `--run` refuses an existing output directory and
verifies the seal. The source bank and queries are stored once; trial rows store
compact IDs, source-only decisions, work counters and scores. Large row streams
use deterministic gzip (`mtime=0`, no embedded filename), with compressed and
uncompressed byte counts retained. Gold is stored
separately and not passed to retention, retrieval or reading interfaces.

Self-checks must cover future-query capability exclusion, TTL boundary, LRU/LFU
eviction, old dependency preservation, cold recovery, stale/wrong-answer controls,
expiry/base restoration, imported earlier-effective correction, source hashing,
byte cap, capable unseen paging and layout invariance. Independent review will
audit actual collection and all endpoints. Five or six scientific PNG/SVG pairs
are rendered from retained tables, then inspected. A runnable independent audit
and mutation checks remain required before acceptance.

## Limits

This tests engineered mechanisms, supplied clean metadata, deterministic source
interpretation and a chosen retention quota. It does not establish natural PARA
performance, optimal quota or TTL, semantic retrieval quality, production
deletion safety, real filesystem latency or broad human memory principles.
No model/provider calls are made. The outcome report must expose weak or failed
baselines, archive costs and policy failures, not only aggregate improvements.

## Optional reader follow-up, not part of this deterministic run

Twelve predeclared probes use the last six workload scenarios listed above, seed zero, high
density, epoch 32: their current and standing-query tasks. Four cells are fixed:
all/global/off; ttl8/global/off; ttl8/global/scheduled_cold; and
latest_dependencies/linked/off. Their 48 source-exact packets may be supplied to
fresh blinded LLM-reader contexts, with condition names and gold hidden. This
would be a separately accepted, separately reported downstream experiment; it is
not executed or claimed by this lab. Packet reconstruction uses selected source
IDs in actual call order and the frozen rendered wrapper. No probe selection
changes based on deterministic outcomes are allowed.
