# Filing hypotheses for accurate continuation

**Status: proposed experiments, not measured agent benefits.** These hypotheses translate the public reviews into small changes to files, metadata, and maintenance. The objective is recovery of complete governing evidence by a reader unfamiliar with the collection. Efficient means reaching usable context and verified completion with reasonable discovery time, maintenance work, bytes, tokens, and tool calls. A cheaper answer that loses a critical exception fails this objective.

The starting point is ordinary source files and full-text search. Add one intervention at a time; neither a graph database nor a replacement folder taxonomy is assumed. Directory names below are illustrative. All examples are wholly fictional. The [synthesis](synthesis.md) explains the evidence boundaries, and the [evaluation protocol](../evaluation/protocol.md) supplies the testing contract.

## Shared experimental contract

Keep source content, reader version, tool behavior, authorization, tasks, and resource caps matched. Independently annotate governing evidence, valid alternative evidence sets, scope, chronology, critical prohibitions, unknowns, and observable completion criteria before testing. Retain all original evidence in organization comparisons. Brief-only, full-context, and evaluator-selected evidence conditions are separate diagnostics.

Every main trial starts in an isolated workspace with a genuinely new reader: no inherited conversation, provider-side memory, supplied schema briefing, prior access to this collection, prior trial output, or access to evaluator files and the original repository. Record the filesystem, network, history and provider-memory controls actually enforced; missing controls make a run a leakage-prone demonstration rather than fresh-reader evidence. This operational condition cannot establish that the base model never encountered a familiar filing method during pretraining. Compare a discovery-only entry naming locations, its removal, and schema-taught onboarding separately. Use new fictional project names and held-out task formulations. A changed process with shared history is insufficient isolation.

Measure preservation, discovery, interpretation, and action separately. Record time to the first useful governing evidence and to a complete sufficient evidence set; the latter prevents a fast partial hit from looking successful. Inspect actual file edits and verification outcomes. Predeclare rare prohibitive constraints as critical: violating one fails the task regardless of average savings. Report critical errors, complete continuation, historical reconstruction, justified abstention, correction lag, broken links, maintenance effort, stored bytes, tokens, and calls. Include failed runs and ingestion, writing, and repair effort across evolving histories.

Run matched-budget and fidelity-first comparisons. In the latter, predeclare a complete-task success target and critical-error tolerance, permit expansion under a declared stopping rule and resource ceiling, and report unresolved dependencies. Measure cost to the target and retain runs that fail to attain it. Preregister a practically meaningful improvement threshold and sampling plan for each primary outcome. Disconfirmation below means a sufficiently precise comparison excludes that improvement, or a repeatable critical regression defeats the fidelity requirement. An underpowered null is inconclusive. Resource savings qualify only when the declared correctness requirement is met.

## H1. A source-linked current view improves handoffs without replacing episodes

**Intervention and prediction.** Add one `current.md` beside retained episodes. Each material statement has a source ID and precise source position; governing constraints, unresolved conflicts, verified results, and next actions remain distinguishable. Record covered source IDs, revisions or exact spans, plus known gaps; neither a latest-seen ID nor an edit time establishes complete incorporation. Predict better complete continuation and faster discovery than sources alone, while preserving historical explanations.

**Motivation.** ReadAgent keeps gists expandable to original passages; this is a navigation mechanism, not a tested evolving-project handoff. [AM11](https://arxiv.org/html/2402.09727v2)

**Matched comparison.** Compare source-only, sources plus an unlinked view, and sources plus the same linked view. Match view wording in the latter pair. A view-only diagnostic exposes missing qualifiers but does not establish the link effect. Ask fresh readers to resume a fictional export task after an interrupted attempt, then explain why its earlier destination changed.

**Negative test and tradeoff.** Recently rewrite the view while deliberately leaving a later authoritative correction unincorporated. Include a rare exception absent from its main paragraph. Extra prominence can create misplaced trust, and links cost maintenance.

**Disconfirmation.** Reject the fidelity prediction if linked views cause reproducible critical stale-rule use or historical loss. Reject the efficiency prediction if complete-evidence discovery time does not meaningfully improve at matched correctness. Count source expansion behavior rather than assuming readers follow links.

## H2. Problem cues and explicit scope outperform generic topical labels

**Intervention and prediction.** Add a short header containing a stable record ID, affected artifact, project scope, known aliases, and the problem that prompted the record. Keep unknown fields explicitly unknown. Use natural discriminating phrases such as “handles duplicate identifiers in the import step,” rather than accumulating generic tags. Predict fewer wrong-project selections and better discovery from paraphrased task descriptions.

**Motivation.** Human PIM research identifies project and context attributes; its interface evidence does not establish an agent filing winner. [OR03](https://onlinelibrary.wiley.com/doi/full/10.1002/asi.20738)

**Matched comparison.** Give both conditions identical source bodies, IDs, and search tools. Compare useful cue headers with equally long generic topic headers; separately ablate scope and aliases to identify their contributions. Run exact-identifier, alias, and problem-description tasks. Include two fictional projects using similar terminology; the task prompt does not reveal the storage vocabulary.

**Negative test and tradeoff.** Remove an alias, introduce ambiguous scope, and add a plausible but erroneous inferred cue in a separately labeled robustness condition. More descriptors can increase collisions and impose correction work. Source-derived cues and generated cues should be analyzed separately.

**Disconfirmation.** Reject the cue prediction if complete required-source coverage and wrong-project selection fail to improve meaningfully on held-out paraphrases. A benefit limited to repeating the header's exact words does not support unfamiliar-task discovery. A critical exclusion hidden by an incorrect scope filter is a fidelity regression.

## H3. Decision capsules with neighboring evidence beat arbitrary chunks

**Intervention and prediction.** Create a small capsule for a decision, attempted action, or correction: trigger, accepted outcome, scope, verification status, source span, and links to preceding and following source positions. Preserve the intact underlying record. Predict that capsules recover complete decision context more often than isolated turns or fixed-length chunks.

**Motivation.** SeCom studies coherent segments; human narrative research studies event boundaries. Neither establishes the proposed capsule design. [AM07](https://arxiv.org/html/2502.05589v3), [BM08](https://www.dpmlab.org/papers/Neuron17.pdf)

**Matched comparison.** Use the same retained records and total evidence budget. Compare capsules, fixed-length units, and session-sized units with the same retrieval method. Separate boundary selection from added capsule metadata in an ablation. Ask readers to recover a decision and continue its interrupted implementation.

**Negative test and tradeoff.** Place a correction immediately outside the apparent event boundary and a governing exception much farther away. Include a capsule whose agent success claim conflicts with an adjacent tool failure. Neighbor expansion can add distraction; local adjacency cannot stand in for every dependency.

**Disconfirmation.** Reject the completeness prediction if capsule retrieval does not improve complete evidence-set coverage and continuation, or if it repeatedly severs corrections from their targets. Match retrieved bytes in one comparison and allow variable expansion in another; a larger package alone should not be credited to better boundaries.

## H4. One canonical record plus project links reduces divergence

**Intervention and prediction.** Store shared evidence once under a stable ID. Project indexes contain a link and one sentence explaining its local relevance. A small ID-to-path mapping survives renames; source versions remain addressable. Predict fewer inconsistent copies after corrections and less maintenance work without worse cross-project discovery.

**Motivation.** Luhmann's reflective account uses fixed addresses and links; it provides practice testimony, not controlled agent-performance evidence. [OR11](https://luhmann.surge.sh/communicating-with-slip-boxes)

**Matched comparison.** Compare canonical records with independently maintained full copies in project folders. Keep source content and initial project associations equivalent, and preserve origin IDs in both conditions. Apply identical corrections and folder renames, with equal maintainer budgets. Give unfamiliar readers tasks beginning from different projects.

**Negative test and tradeoff.** Break one project link and move the canonical file. Include a genuinely project-specific exception that must remain local rather than being promoted into a shared rule. Canonical storage introduces an access dependency, and repairing references can cost more than updating a tiny duplicate.

**Disconfirmation.** Reject the maintenance prediction if correction propagation and revision effort do not improve meaningfully. Reject the broader method if required-source discovery or critical scope accuracy worsens after moves. Lower storage bytes alone are insufficient; independent copies may outperform links where access is unreliable.

## H5. Current eligibility should be separate from historical retention

**Intervention and prediction.** Add record role, applicable scope, effective interval when known, and explicit `supersedes` or `qualifies` links. Current views demote superseded instructions while historical queries retain access to them. Folder activity is a separate signal. Predict fewer obsolete-rule actions without poorer reconstruction of earlier decisions.

**Motivation.** THEANINE retains earlier memories in timelines; conversational evaluation does not establish arbitrary authority resolution or resumed execution. [AM12](https://aclanthology.org/2025.naacl-long.435/)

**Matched comparison.** Keep every source in both stores. Compare explicit eligibility relationships with dates and archive locations alone, using the same reader and retrieval policy. Include present-action and past-state tasks over the same fictional change history; score both before combining outcomes.

**Negative test and tradeoff.** Import an old authoritative document late, place a still-governing exception in an inactive folder, and add a newer unapproved proposal. Include comparable-authority conflict with no justified winner. Wrong validity metadata can suppress exactly the evidence needed to challenge a convenient current answer.

**Disconfirmation.** Reject the prediction if current critical stale-rule errors do not meaningfully fall, historical reconstruction worsens, or unknown authority becomes unjustified certainty. A default current filter must permit evidence expansion for unresolved conflicts. Correctly choosing the newest timestamp does not establish the method's intended benefit.

## H6. Update-triggered view maintenance reduces exposure to stale state

**Intervention and prediction.** Give derived views a source dependency list and explicit incorporation coverage, including known gaps. Contiguous covered ranges are valid only where ordering and coverage are established. A committed governing correction marks dependent views dirty; maintenance checks their claims against sources before clearing that mark. A handoff exposes pending incorporation. Predict shorter correction lag and fewer stale continuations than equal-budget periodic rewriting.

**Motivation.** Systems profiling exposes asynchronous freshness tradeoffs; provenance standards represent derivation. Neither guarantees correct projection repairs. [AM15](https://arxiv.org/html/2606.06448v2), [OR17](https://www.w3.org/TR/prov-dm/)

**Matched comparison.** Replay identical evolving evidence through update-triggered, handoff-triggered, and fixed-period schedules. All schedule arms use the same dependency-map and incorporation-coverage mechanism; test their presence separately. Coverage values reflect the evidence actually incorporated by each arm. Match maintainer, review budget and evidence available to readers at common evaluation checkpoints. Record source versions available and inspected at every maintenance event. Different schedules naturally expose maintainers to different updates: report this as a whole-policy effect; claim a timing-only effect only in a separate comparison matching review count and update exposure. Use fresh readers between updates, not just after final cleanup.

**Negative test and tradeoff.** Supply bursts of irrelevant updates, interrupt a write, omit one dependency link, and introduce an ambiguous correction. Stable collections reveal needless work; frequent triggers can create backlog. Include an equal-budget source-inspection control to test whether timing beats simply doing more review.

**Disconfirmation.** Reject the schedule prediction if stale exposure and critical obsolete-rule use fail to improve at comparable maintenance effort. A final clean snapshot cannot rescue long unsafe intervals. Any repair that invents a governing assertion is a fidelity failure; a dirty marker is only a warning, not repaired state.

## H7. Bounded dependency expansion improves complete evidence recovery

**Intervention and prediction.** Give task records a short list of known prerequisites, supporting source links, and unresolved slots. For a fictional conversion task these might cover format, scoped exception, prior failed attempt, and required check. Retrieval begins with exact search, then follows relevant dependencies under a declared cap. Predict better complete-task evidence coverage than fixed top-k relevance alone.

**Motivation.** Sufficient Context distinguishes available evidence from reader errors; its QA notion does not enumerate every action prerequisite. [RC11](https://arxiv.org/abs/2411.06037)

**Matched comparison.** First test dependency links with identical tools and reader instructions. Separately compare expansion and fixed top-k policies while holding those links constant. Match returned bytes in one condition; permit fidelity-first expansion in another. Test a weakly matching bridge fact and a dependency requiring evidence from another project.

**Negative test and tradeoff.** Omit a prerequisite, create a link cycle, and supply a tempting irrelevant dependency. Include missing evidence where a focused clarification is correct. Generated prerequisite lists can falsely suggest closure; expansion consumes time and can import obsolete material.

**Disconfirmation.** Reject the prediction if complete evidence-set coverage and verified continuation fail to improve, or confidently incomplete actions increase. Report cap exhaustion and unresolved slots. A good relevance score, a satisfied generated checklist, or additional reads cannot certify that no undiscovered governing condition exists.

## H8. Discoverable obligation records improve interrupted-task continuation

**Intervention and prediction.** Put pending obligations in a small `pending.md` linked from the entry point. Each row states trigger, authorized action, prerequisites, cancellation condition, and observable fulfillment evidence. Define unfamiliar terms near their use. Predict fewer missed checks and false completion claims after interruptions.

**Motivation.** Human reminder experiments test external intention cues; their discussion distinguishes triggering from remembering action content. OAIS addresses reader understandability. These motivate, rather than validate, agent handoffs. [HM15](https://samgilbert.net/pubs/Gilbert2015QJEP.pdf), [OR14](https://ccsds.org/Pubs/650x0m3.pdf)

**Matched comparison.** Compare structured obligations with identical obligation content in ordinary prose at the same discoverable location. Separately remove the entry point and test a schema-taught reader. A fictional local task requires a check only after a particular artifact changes; the harness inspects whether it actually ran.

**Negative test and tradeoff.** Cancel an obligation, leave a premature completion mark, and add an unfulfilled trigger. Include vocabulary absent from the reader's generic task prompt. More visible rows can produce repeated work or distract from current constraints; reminders do not create new authorization.

**Disconfirmation.** Reject the action prediction if actual trigger-appropriate checks and complete continuation do not improve, or canceled and unauthorized actions increase. Remembering the obligation in prose is insufficient. Report orientation cost and performance without the entry point so familiar navigation is not mistaken for robust onboarding.

## Priority and scientific limits

Start with H1, H2, and H8: they test source-backed orientation, discriminating discovery, and actual continuation with small file changes. Then test H5 and H6 on changing evidence. Use H3 when source granularity causes omissions, H4 when copies diverge, and H7 when necessary dependencies remain undiscovered. Only combine independently promising interventions; rerun held-out tasks to detect interactions.

The repository has no original comparative results. Human, biological, standards, and conversational evidence motivate different mechanisms; none proves a best filing tree. These experiments require independently authored corpora, enforced fresh starts, adequate replication, and audited governing evidence. Even success would support the tested implementation and workload, not universal recovery of every important fact. Publish negative results and maintenance costs alongside gains.
