# Independently authored fictional challenge bank — 2026-10-13

This public bank contains **96 fictional history families, 1,110 records, and 288 tasks**. Family sizes range from nine to fourteen records: 9, 24, 15, 12, 24, and 12 families have 9, 10, 11, 12, 13, and 14 records respectively. Each family has a historical question, a current scoped question, and a separate follow-up question. The complete corpus resolves **240 tasks and requires a justified hold on 48**. Records include 990 original sources and 120 informal derived views.

An OpenAI language-model agent authored the sixteen decision mechanisms and their source prose, then used a deterministic local generator to create six parameterized variants of each mechanism. Names, exact identifiers, numeric parameters, source ordering, and source length vary. Record-role suffixes, task-role suffixes, and task array order are independently permuted per family. Variants retain their mechanism's historical/current logic. Variants 2, 4, and 6 additionally contain an authored final follow-up original; variants 1, 3, and 5 retain the unresolved follow-up. Every family declares `template_family`; **96 families are not 96 independent human-authored cases**. This is a designed stress-test corpus, not a representative natural filesystem corpus. Results cannot establish population performance, human usability, or performance on a user's private history.

The author did not read private PARA records, transcripts, prior study gold, or ranker results. All project names, crews, tokens, credits, authority structures, paths and historical events are invented. Relative `path` values are fictional category labels, not real filesystem locations. Original text and Unicode code points are retained in the JSON.

## Mechanisms and declared disjoint strata

Each family belongs to the single mechanism that generates its current scoped task. Related phenomena can appear as distractions in another stratum; that does not change membership.

| Template group | Stratum / main decision mechanism |
|---|---|
| queue-limits | Bounded settings with overlapping lane and alert exceptions |
| release-gates | Required gates, explicit rejection, and a complete no-waiver register |
| stock-reconciliation | Opening count, posted movements, quarantine, breakage, and unposted requests |
| room-arbitration | Registrar precedence, event-specific supersession, and authorized cancellation |
| codec-alias | Explicit Unicode alias registration plus device profile and override scope |
| retention-intervals | Raw-log versus summary scope, named holds, and future-effective authority |
| dependency-closure | Exhaustive unordered component sets, delegated overlays, and retirement |
| purchase-authority | Project allowance constrained by a cross-category resource charter |
| metric-denominator | Exhaustive trial categories and a denominator inclusion rule |
| release-rights | Invented rights terms and bundle-specific classified-panel exceptions |
| custody-chain | Physical custody established by exact seal identity and matched signatures |
| procedure-order | Retained baseline order, authorized insertions, and batch enrollment |
| full-digest | Exact full identifier constructed from signed base and suffix, versus clipped quotes |
| service-alias | Registered accent forms, unregistered cross-alphabet lookalikes, and request session |
| rollback-window | Strict threshold, closed-window endpoints, event class, and lane scope |
| map-page-chain | Exact map revision, matching page shards, and a complete ordered route |

The prose includes Markdown paragraphs and headings, sparse bullet notes, correspondence, tables, logs, chronology, ordered transformations, and conditional rules. Record order rotates deterministically and is not evidence precedence. Body lengths range from 31 to 531 whitespace-separated words; sixteen records exceed 500 words. Eighty operative support spans begin after a long background prefix. These are word counts, not a claimed tokenizer-specific measurement.

Families combine an older-authored future-effective order, a false-current informal card, and varied additional sources. Recent non-authoritative conversations, similarly named undertakings, and unknown but irrelevant materials details appear in different subsets. In stock, dependency, custody, and rollback groups, an additional live hub has **correct active-source revision bindings but incorrect retained prose**. Other informal cards expose their stale baseline incorporation. Room, purchase, procedure, and map groups add category-spanning authority-charter/source-location chains. Unknown cover colors and arrival minutes have no role in the rules; their absence should not force a hold on a supported ruling.

There are three unresolved modes: **18 tasks with missing original evidence or governing authorization, 15 with an available authority outside the requested scope, and 15 with actual competing coequal authorities and no resolving rule/order**. Known visible facts remain answerable in each mode. Conflicting originals explicitly share scope and effective date, neither supersedes the other, and capture time is not precedence. Incompatible-scope cases distinguish main undertaking from Annex, equipment from consumables, and exact registered input from a Unicode lookalike.

The other 48 follow-ups contain a genuine new original: a complete missing attachment, a governing authorization for the correct main/class/input scope, or a final signed adjudication explicitly superseding competing claims. Final originals arrive at 21:00Z on the as-of date; retained initial packet assertions describe the 18:00Z snapshot. They repeat every requested known fact and resolve the previously unsupported field, making a standalone sufficient source. Boolean resolutions include both positive and negative outcomes. Follow-up queries are neutral end-of-day requests, and the same contract asks for `hold_reason: null` when ready or a reason code when unresolved. The deliberately authored resolution/no-resolution variant coupling is an experimental design choice, not a natural outcome distribution; generation metadata must not be used to guess status.

Eighteen missing attachments remain actual dangling `links` to absent `Nxxx-X001` IDs. Their referring originals carry `declared_missing_links: [{id, reason}]` and name the missing reference in prose. These IDs are deliberately absent and never appear in gold evidence. Resolved variants supply the actual attachment original, map its ID with the other source-role IDs, and remove the missing marker. The checker accepts only explicitly marked missing edges; an unmarked unresolved reference is an error. Partial quotes, selected-step lists, missing profile records, and missing outcome shards supply different insufficiency patterns. Complete signed registers establishing *no waiver* or *no consent* are affirmative negative evidence; the absence of an attachment does not establish a negative outcome.

## Typed interface and exact original support

Records use `id`, `kind`, `revision`, `authored_at`, `title`, `scope`, `body`, `links`, `supersedes`, and `incorporates`. Optional public `valid_from` and `valid_to` dates appear only on applicable authority records and are grounded in their prose. Date endpoints are inclusive calendar dates. `authored_at` is not an effective date. A record's supersession relation does not erase it for a historical question or for an amendment that retains its baseline content.

Queries supply `answer_keys`, `critical_keys`, and `answer_contract`. Contracts describe field meanings, JSON types, exact strings, accepted reason/state enums where applicable, and ordered versus unordered list comparison. An unordered list is compared as a unique set; an ordered list is compared element by element. There is no general Unicode folding, case folding, synonym matching, number coercion, or loose semantic judge in the main typed contract.

`answer_contract.unresolved_policy` permits factual fields to be null with `status: hold` when the evidence actually supplied to the reader is insufficient. Such a hold requires a nonempty `hold_reason`. Every follow-up requests a nullable reason field: null means ready with no applicable hold reason, while a string code explains a hold. Historical/current questions permit a reason sidecar on partial-evidence holds. Full-context ready factual answers remain concrete. A factual null means “not established from supplied evidence,” and never silently means false, empty, zero, or not applicable.

Tasks have one or more original-source `evidence_sets`. Historical tasks and unresolved follow-ups have one sufficient set each. Resolved follow-ups have the independently sufficient final original as a singleton set. Every current scoped task has a rule/facts path and a genuinely sufficient independent, signed authority certificate. Certificates are source records because their governing authority delegates controlling status to them; they are not informal copied views. Procedure-order and service-alias primary paths require **three sources**, including retained original baseline/registration content. Their independent certificates remain sufficient alternatives.

`evidence_spans` is an array aligned with `evidence_sets`: alternative *i* contains exact spans for evidence-set *i*. A span is `{id, start, end}` with Python Unicode code-point offsets `[start, end)` into the unmodified original `body`. Compact operative blocks include authority, time, scope and facts. Long training context is excluded from gold support, and the operative tail offset is retained. A record ID alone must not receive passage-completeness credit when its decisive span was not supplied. Each task also has an authored `gold_rationale` explaining original support and inference. Gold answers, evidence sets, spans, rationales, and `audit_role` must remain outside the retriever/reader input. Audit roles exist solely for stratified reporting after task ID/order permutation.

## Split fixed before outcomes

The split unit is the complete `template_family` group. Order all sixteen template strings by ascending `SHA256(UTF-8(template_family + ':oct13-split-v1'))`. The first four groups are development and the other twelve confirmation.

- Development: queue-limits, service-alias, dependency-closure, map-page-chain; **24 families / 72 tasks**.
- Confirmation: the remaining twelve groups; **72 families / 216 tasks**.

The JSON records the full hash ordering and each family assignment. All six variants of a group stay together. This assignment was fixed before any method outcome. Confirmation uncertainty should resample the twelve held-out template groups, not treat 216 questions as independent observations. Holding out templates also holds out their strata, so held-out rule/mechanism generalization is confounded with task-stratum differences. Family-level summaries remain useful descriptive views, not independent sample-size inflation.

## Validation and support audit

Run from this directory:

```text
python bank_check.py --self-check
```

The dependency-free checker validates scale, unique IDs, present references and explicit missing-edge declarations, source/derived provenance, revision references, applicability date grounding, typed contracts, null semantics, list ordering, expected answer types, original-only evidence sets, exact span bounds, rationale references, and whole-template split assignment. Four intentional corruptions verify that incorrect answer types, out-of-bounds spans, derived-only evidence, and unmarked dangling links can fail the check. It reports a SHA-256 checksum of the exact bank bytes. Structural validation cannot prove that prose semantically entails an answer.

A separate agent, without viewing ranker outcomes, read all sixteen variant-one source/task sets and audited each primary and alternative source path. It identified and corrected three classes of gap before freeze: a no-issued-waiver statement did not establish lack of waiver authority; procedure insertions needed the retained original SOP; and exact canonical service spelling needed the original registry. It also corrected shipping-list versus enrollment terminology. An author arithmetic check removed an incorrect claim that a log exceeded every historical retention period; it exceeds the operative revised interval, and the active named hold still governs deletion. Parameterized variants were reviewed for propagation, exact spans and numeric consistency rather than reported as 288 independent semantic readings. The finalized audit receipt and bank checksum are recorded by the study's pre-run freeze procedure.

This bank deliberately provides clear authoritative certificates as alternatives. That can reward a method that finds a compact sufficient source; it is not evidence that all real records contain such certificates. A recurring authority/amendment/certificate scaffold and historical/current/follow-up task pattern remain, even after varying record counts, link topology, revision bindings, IDs, layouts, and resolution modes. Six variants in a template share much of their semantic structure, and readiness is coupled to the explicitly authored optional supplement. Independent domain/rule mechanisms do **not** establish independent natural filesystem topologies. These design choices must remain visible when interpreting a score.
