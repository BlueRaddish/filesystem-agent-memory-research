# Synthesis: organize for recoverable decisions and successful continuation

## The research question

The useful question is whether a new agent can discover and apply the important context needed for its next action. A filing system helps only to the extent that it improves this outcome. Human readability, maintenance effort, storage integrity, and retrieval cost matter, but none alone establishes accurate memory.

Here, **important context** means evidence whose omission or misinterpretation could materially change the justified answer or action. It can include an active goal, governing constraint, correction, scoped exception, dependency, failed attempt, required verification, or unresolved ambiguity. Importance is task-dependent. A historical detail irrelevant to today's action can become essential when explaining a change tomorrow.

The aspiration to load all important context is a useful objective. No reviewed method establishes a general certificate that an agent has found literally every important fact in an arbitrary collection. The practical response is to define required facts for evaluable tasks, measure material omissions, expand retrieval when dependencies remain unresolved, and report the boundaries of the evidence inspected.

## What the evidence supports

The detailed reviews provide the source-specific findings and limitations. The following conclusions synthesize them; they are not pooled causal estimates.

| Conclusion | Evidence and its limit | Implication to test |
| --- | --- | --- |
| Attractive organization is not an accuracy certificate | A filesystem-memory study separates search economy from answer quality; its workloads and agents bound the finding. [AM13](https://arxiv.org/html/2607.26637v1) | Evaluate task correctness alongside navigation effort |
| Compact navigation can coexist with original evidence | SeCom and ReadAgent retain routes from search representations or gists to source passages. [AM07](https://arxiv.org/html/2502.05589v3), [AM11](https://arxiv.org/html/2402.09727v2) | Make summaries expandable and test when expansion is needed |
| Current authority and historical retention are different properties | Temporal memory systems explicitly represent change; extracted structures still depend on construction quality. [AM10](https://arxiv.org/html/2501.13956v1), [AM16](https://aclanthology.org/2026.acl-long.749.pdf) | Preserve what changed and identify what governs the present task |
| Context length and useful evidence are different measurements | Long-context studies use different tasks; literal-match success does not establish reliable reasoning over distractions. [RC07](https://aclanthology.org/2024.tacl-1.9/), [RC09](https://arxiv.org/abs/2502.05167v3) | Test position, distractors, paraphrases, and connected dependencies |
| Relevance, sufficiency, and actual source use need separate checks | Sufficiency and attribution research distinguish these questions. [RC11](https://arxiv.org/abs/2411.06037), [RC18](https://staff.fnwi.uva.nl/m.derijke/wp-content/papercite-data/pdf/wallat-2025-correctness.pdf) | Inspect complete supporting evidence and contradictory evidence |
| Human organization offers mechanisms, not an LLM winner | PIM studies and creator frameworks concern different interfaces and purposes. [OR03](https://onlinelibrary.wiley.com/doi/full/10.1002/asi.20738), [OR09](https://fortelabs.com/blog/para/) | Treat project grouping and facets as testable navigation choices |
| Byte integrity and provenance support recovery and audit but do not certify truth | BagIt and provenance standards address integrity and lineage. [OR15](https://www.rfc-editor.org/rfc/rfc8493.html), [OR17](https://www.w3.org/TR/prov-dm/) | Verify publication separately from semantic fidelity |

This leaves considerable design freedom. It does not justify replacing all files with a graph, retaining every interaction forever, or loading the entire archive for every request. It also does not justify discarding evidence merely because a summary is convenient.

## The four failures to distinguish

**Preservation failure:** a correction or qualifier never reaches the durable record. Better search cannot recover missing material. A stored transcript may preserve speech while omitting the tool result needed to establish whether an action succeeded. Capture boundaries must be explicit.

**Discovery failure:** the evidence survives but is not found. Exact identifiers, semantic paraphrases, temporal filters, topic links, neighboring passages, and project indexes offer different access paths. Combining them is a candidate intervention; the right combination depends on the corpus and query.

**Interpretation failure:** the agent finds the evidence and applies the wrong version, scope, role, or authority. A newly rewritten summary can be stale. A proposal can resemble a decision. A broad policy can coexist with a narrow exception. More retrieved text does not resolve these distinctions automatically.

**Action failure:** the agent understands the record but does not execute the required check, updates the wrong artifact, or claims success without evidence. QA accuracy alone cannot establish dependable continuation.

These layers can interact. An omission attributed to retrieval may originate in extraction. A generated current-state view may encode the needed fact but omit the context required to apply it. Diagnose using both stored artifacts and the agent's observable evidence access, rather than inferring the cause from the final answer alone. EvalMem motivates operation-level diagnosis, while its oracle access is an evaluator privilege. [AM14](https://arxiv.org/html/2609.22231v1)

## A minimal filesystem design to test

The following is a proposed design, not a proven standard. Start with a small number of components and add complexity only for a demonstrated failure.

1. **A discoverable entry point.** State what the collection covers, where active work lives, how to find sources, and what timestamps mean. Expose current goals, governing constraints, unresolved questions, and next actions. Give the entry point an incorporated-evidence boundary so a successor can detect recent records not yet summarized.
2. **Recoverable source records.** Preserve the relevant observations, decisions, attempts, and verifications with stable identities and provenance. Define what is excluded. Preserve the versions needed to reconstruct material changes, within an explicit retention and access policy.
3. **A current-state projection.** Maintain a short account of the presently governing state. Each material claim points to its supporting record and relevant superseding or qualifying records. Unknown dates or authority remain unknown. Treat the projection as a derived artifact that can be audited and rebuilt.
4. **Simple, complementary navigation.** Use shallow locations and exact full-text search first. Add scoped metadata, semantic retrieval, or links when a measured gap warrants them. Multiple project associations can avoid duplicating the source. Renaming a folder should not erase source identity.
5. **Verified maintenance.** Publish changes through a recoverable write process, check that the committed bytes are accessible, and check material claims against evidence. Byte checks and semantic checks answer different questions. When a source changes, review dependent projections where their relationships are known.

A small project can express these roles in three or four Markdown files plus source records. A larger system may need structured indexes, version-aware links, and transaction controls. The role distinction matters more than the particular extensions or directory names.

Useful fields include an identifier, record role, source, scope, observed time, effective time when known, supersession or qualification relationships, verification status, and the evidence incorporated into a derived view. Adopt only fields that answer actual questions or prevent demonstrated mistakes. Empty metadata and invented precision both create false confidence.

## Where PARA fits

PARA's project/area/resource/archive distinction can provide a comprehensible top-level location and an activity signal. It does not, by itself, express whether a statement is authoritative, historical, proposed, verified, or applicable to a specific action. A resource can support multiple projects; an archived episode can explain an active constraint; an active project can contain an obsolete draft.

The appropriate first experiment is to keep the role-based filing scheme and test the entry point, current-state view, source links, and retrieval policy. Replacing the taxonomy before diagnosing failures changes many variables at once. If repeated misfiling or navigation failures remain, compare shallower structures, controlled facets, or stable-ID indexes under matched conditions. Human PIM offers useful hypotheses, with different reader behavior and familiarity as explicit transfer limitations. [OR04](https://onlinelibrary.wiley.com/doi/10.1002/asi.22906), [OR05](https://flamenco.berkeley.edu/papers/flamenco03.pdf)

Archiving should affect presentation and selection according to a declared policy. Moving a file alone does not remove it from a broad search. Retention, prominence, and authority are separate: demoting an item can reduce clutter while preserving it; declaring it superseded changes its role for current decisions. GrayArea supplies a human-interface example of demotion, not an agent accuracy result. [OR06](https://www.microsoft.com/en-us/research/publication/its-not-that-important-demoting-personal-information-of-low-subjective-importance-using-grayarea/)

## Accuracy before token economy

Optimize first for material constraints preserved, applicable evidence found, correct state interpretation, and verified task outcomes. Measure tokens, latency, and maintenance effort alongside those results. A cheaper method that loses a critical exception is a regression; a larger prompt that increases obsolete-source use can also be a regression.

Compare systems in two ways: under matched resource budgets, and at an accuracy target with resource use allowed to vary. The first isolates efficiency tradeoffs; the second better reflects a fidelity-first objective. Record raw evidence availability, reader/tool settings, failed runs, and ingest costs. Do not mix published product scores from different protocols into a causal ranking.

Full context is an important baseline. It can reveal whether selective retrieval introduced an omission. It is not an oracle reader: interpretation and distraction failures can remain. Oracle evidence is a separate diagnostic condition, and must not leak into ordinary fresh-agent trials.

## Biological memory and human practices

The [biological review](biological-memory.md) adds evidence on distinct memory roles, contextual binding, event organization, replay, updating and forgetting. The [human-practice review](human-memory-practices.md) examines retrieval tests, corrective feedback, spacing, cue design, discrimination and external reminders. These broaden the candidate mechanisms; their human or animal findings do not establish an optimal agent filing system.

The [transfer review](brain-agent-transfer.md) translates selected functions into minimal implementations and proposed comparisons. It also reviews HippoRAG and HippoRAG 2 as existing brain-inspired retrieval work. For this project, an economical experiment is source-linked episodes and current state plus externally checked retrieval probes. Measure later unfamiliar-reader behavior rather than assuming that repeated summaries strengthen memory. A fixed reader's weights do not change merely because a file is reread.

Biological inspiration should remain subordinate to the project's fidelity objective. Retaining evidence while changing its current eligibility is different from deleting it; reconstructing a plausible account is different from recovering the applicable instruction. Candidate maintenance schedules should be tested around changing evidence and handoffs rather than importing a human learning interval directly.

## Research agenda

The [evaluation protocol](../evaluation/protocol.md) turns these proposals into falsifiable checks.

The [filing hypotheses](filing-hypotheses.md) specify eight candidate interventions with matched controls and disconfirmation criteria. They prioritize source-linked current views, discriminating task/scope cues and discoverable obligations, then test eligibility and maintenance on changing evidence. These are proposed experiments; no improved agent outcome is claimed.

The highest-priority questions are:

- Does a source-backed current view improve unfamiliar-reader continuation, and how often does it become stale?
- When does adding lexical, semantic, temporal, or link expansion improve complete evidence retrieval rather than merely top-k relevance?
- Which critical qualifiers survive repeated summaries, corrections, and reorganizations?
- How do missing entry points, renamed locations, conflicting drafts, and concurrent updates affect handoffs?
- Can a system recognize unresolved authority or incomplete evidence and ask a focused question instead of making a confident error?
- How much maintenance is justified by the reduction in material mistakes?

The repository currently provides evidence synthesis and a protocol. A stronger follow-up would use preregistered comparisons, independently created tasks, unfamiliar readers, auditable failure analysis, and negative results. The proposed next step is to make important decisions recoverable and test whether a fresh agent can actually use them.
