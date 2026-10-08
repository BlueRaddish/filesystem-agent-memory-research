# Applying biological and human memory ideas to agent files

Human memory research offers candidate functions to borrow: preserving specific episodes while extracting reusable knowledge, finding material through multiple cues, distinguishing sources, checking recall, and supporting future intentions with external reminders. It also exposes failures to avoid. Complementary-learning theory and source-monitoring theory motivate two of these distinctions; neither evaluates agent files. [BM02](https://stanford.edu/~jlmcc/papers/McCMcNaughtonOReilly95.pdf), [HM12](https://pubmed.ncbi.nlm.nih.gov/8346328/) The [biological review](biological-memory.md) and [human-practice review](human-memory-practices.md) document the evidence and its boundaries. This section proposes translations into filesystem workflows and tests that could reject them.

The transfer target is an agent using persistent external records, not a model retrained on its experiences. Writing a file, revisiting a record, or running a retrieval test changes the external system only if the process updates an artifact, index, procedure, or execution policy. It does not by itself alter the reader model's weights. That distinction determines what an experiment must measure.

## Transfer a function and evaluate its implementation

Hassabis and colleagues' 2017 perspective argues for borrowing goals, algorithms and representations while allowing artificial implementations to depart from neural detail. It discusses memory among several historical examples. That is a research strategy, not evidence for a particular filesystem layout. A biological observation can motivate an intervention; an agent experiment must establish whether that intervention helps the intended task. [BT01](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/ai-and-neuroscience-a-virtuous-circle/Neuron.pdf)

For each analogy, ask four questions: what problem the organism or human learner faced; which behavior or mechanism was actually measured; what the agent implementation changes; and what competing explanation a controlled test should rule out. Similar terminology is not sufficient. A folder is not an anatomical region, graph traversal is not a neural recording, and retrieval success on a question is not verified continuation of work.

The project's goal also matters. Exact, auditable recovery of a critical instruction can justify preserving detail even when a human strategy generalizes or deprioritizes it. Biological plausibility is one source of ideas. It does not override access boundaries, retention requirements, or evidence fidelity.

## Existing brain-inspired retrieval work

**HippoRAG**, published at NeurIPS 2024, explicitly borrows a hippocampal-indexing analogy. It extracts a knowledge graph and uses query-seeded Personalized PageRank to retrieve passages. Multi-hop QA comparisons support this implementation in its tested settings. Its error analysis identifies extraction, graph search, and loss of contextual cues; larger-scale behavior remains unvalidated. The experiment tests retrieval software, not whether graph nodes reproduce biological memory or make project handoffs dependable. [BT02](https://proceedings.neurips.cc/paper_files/paper/2024/file/6ddc001d07ca4f319af96a3024f6dbd1-Paper-Conference.pdf)

**HippoRAG 2**, published at ICML 2025, adds passage context, query-to-triple matching and LLM filtering labeled recognition memory. It evaluates factual, discourse and associative QA, with component ablations and corpus expansion. This is useful evidence that an inspired design can be tested beyond its original niche. The configured benchmarks do not establish faithful neural simulation or current-state resolution across evolving files. Its non-parametric adaptation accesses external information rather than continually training the reader. [BT03](https://proceedings.mlr.press/v267/gutierrez25a.html)

These examples make the avenue concrete without making it mandatory. Compare an inspired system with source-preserving lexical, dense, hybrid and linked-file baselines using the same corpus, reader and task. A graph should earn its complexity through observed improvements. Benefits could come from additional context, extraction or filtering rather than from the biological analogy.

## Candidate translations

The biological and human-practice reviews supply the motivation for this table. Each implementation and predicted benefit below is a **project hypothesis**, not a measured transfer result.

| Motivation | Minimal agent implementation | Benefit to test | Failure or alternative explanation |
| --- | --- | --- | --- |
| Specific episodes and generalized knowledge have different roles | Keep source episodes alongside a source-linked current view and reusable procedures | Generalization without losing exceptions or change history | Summaries invent a rule, erase a qualifier, or become stale |
| Event boundaries and context help organize experience | Segment records around a decision or action while preserving neighboring messages and ordering | Retrieve a complete decision rather than isolated fragments | A boundary splits the correction from the claim it changes |
| Distinctive cues and source binding help disambiguate recall | Store stable IDs, aliases, task scope and source/verification roles | Find the correct record among similar projects and versions | Broad tags or aliases increase ambiguity; metadata is guessed |
| Several cues can lead to related evidence | Combine exact identifiers, paraphrases and bounded link expansion | Recover a missing bridge fact or dependency | Expansion introduces irrelevant or obsolete evidence |
| Retrieval attempts and feedback can expose gaps | Probe the store with maintenance questions, check sources, then repair omissions or navigation | Improve later held-out evidence recovery | Repeatedly generating the same wrong answer creates false confidence |
| Distributed practice prompts revisiting material | Recheck a maintained view after relevant updates and at defined handoffs | Detect drift before a successor acts | Time passes but nothing changes; the proposed schedule adds no useful signal |
| Interleaving can require discrimination | Test similar constraints from different projects in mixed order | Select the applicable rule and reject a tempting near match | The agent learns the test set or needs an explicit scope field instead |
| External reminders support future intentions | Put pending checks, triggers and completion criteria in a discoverable action record | Execute an obligation at the right point and verify it | The checklist survives but is never read, or a premature completion mark hides the task |
| Demotion can reduce competition among records | Separate active eligibility from retained historical evidence | Reduce obsolete-rule use while preserving reconstruction | An archive location is mistaken for invalidity, or broad search ignores the tier |
| Retrieval and revision can change what is represented | Audit derived views after a correction and retain their source lineage | Propagate an update without rewriting the original event | Repeated regeneration produces unsupported consensus |

These functions can often be tested with ordinary text files. Start with an explicit entry point, source references and a few externally graded probes. The fact that a brain uses richly interconnected activity does not establish that a new database or graph is necessary for a small collection.

## Rehearsal needs a feedback target

A useful retrieval check asks whether the system can recover a governing decision, its exception, its source and its verification status. Compare the answer with original evidence or an independently audited key. If it is wrong, diagnose whether the detail was omitted, not found, misunderstood or incorrectly acted on. Then repair the appropriate layer.

Generating more summaries from a faulty view is a different operation. Agreement among derived texts can reflect shared dependence on the same error. A maintenance process should record the evidence used for a correction, avoid manufacturing independent corroboration, and preserve unresolved conflicts when authority cannot be established.

Human retrieval practice and agent retrieval maintenance also have different success measures. A human-learning study can measure later recall or transfer after practice. A filesystem experiment should measure changed record quality, index coverage, evidence selection, state interpretation and action outcomes in a new reader. Fluency in the maintenance agent's answer is an insufficient substitute.

## Spacing is a hypothesis about maintenance rather than elapsed time alone

Human spacing schedules concern a changing learner and a later learning test; the reviewed quantitative synthesis considers practice gaps jointly with the final-test delay. [HM04](https://pubmed.ncbi.nlm.nih.gov/16719566/) In an external-memory system with a fixed reader, calendar time alone need not change the stored bytes or their usefulness. An analogy becomes concrete when intervening events create something to inspect: a correction, changed scope, completed action, broken link or stale projection.

Compare update-triggered maintenance, handoff-triggered maintenance and a periodic schedule against an equal-budget control. Match the number of checks where possible, distinguish update exposure from timing, and record how long governing corrections remain absent from the current view. No reviewed human spacing result specifies an optimal cron interval for agent files.

A record that is important and stable may need little repeated rewriting. A rapidly changing instruction may need immediate incorporation rather than waiting for a spaced review. Importance, volatility and the consequence of a miss should be stated inputs to a proposed policy, not inferred from age or access frequency alone.

## Experiments that would test the translation

Use the existing [fresh-agent protocol](../evaluation/protocol.md) and keep maintenance probes separate from final test tasks. Otherwise a process can build an answer bank that inflates performance without improving general retrieval. No experiment below has been run as part of this extension.

1. **Episodes plus a current view.** Compare source-only, view-only and source-plus-view conditions on independently authored tasks containing scoped exceptions and later corrections. Measure historical reconstruction, current authority, omitted qualifiers and complete continuation. Keep the allowed source corpus constant.
2. **Distinctive cue design.** Compare generic topic labels with explicit record identity, aliases and scope. Test exact strings, paraphrases, alias changes and cross-project near matches. Include a control with the same amount of unrelated metadata so extra text alone is not credited as useful organization.
3. **Retrieval checks with source feedback.** Compare no maintenance, summary rewriting, and retrieval probes followed by evidence-checked repairs at matched budgets. Evaluate new formulations and tasks excluded from maintenance prompts. Record which files or indexes changed and whether those changes support the improved result.
4. **Maintenance timing.** Hold the number of reviews fixed while varying their placement around updates and handoffs. Evaluate on equivalent evolving histories, measuring correction lag, obsolete-rule use and complete task success. Separate schedule effects from merely receiving more recent evidence.
5. **Discrimination across similar records.** Compare mixed and grouped maintenance tasks with matched examples and exposure. Test a held-out project or rule combination. Inspect whether improvement comes from learned scope cues and whether cross-project errors increase.
6. **Reminders and future obligations.** Compare a structured trigger/check/completion record with equivalent obligations embedded in ordinary prose. Have a fresh agent perform a local task whose verification is due only after a particular change. Measure actual execution and the resulting artifact, including false claims of completion.

Report failures, critical omissions and unintended regressions. Tokens and latency remain useful secondary outcomes. A design that improves routine questions while losing one prohibitive constraint can fail the project's primary objective.

## Proposed next step

The most economical next experiment is to compare recoverable episodes with a source-linked current view, distinctive retrieval cues, and a small set of independently checked retrieval probes. This examines several plausible functions without pretending to reproduce a brain. Only add timing policies, graph structures or automated consolidation when a controlled failure shows why they are needed.

The research contribution should be a traceable argument from an observed phenomenon to an implementation and a falsifiable outcome. Biology and human learning broaden the design space; fresh-reader experiments decide whether a particular translation improves agent work.
