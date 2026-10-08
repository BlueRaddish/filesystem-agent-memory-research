# Human retention and retrieval practices

Human learning research offers useful ways to think about access failures, misleading confidence, and cue design. It does **not** establish that a filesystem agent benefits from human study routines. The strongest transfer is to ask whether a future reader can find and correctly use the evidence, then measure that behavior. An attractive note or successful write is insufficient evidence of future retrieval.

## Scope and review depth

This structured scoping extension covers **23 works**, with a public-source cutoff of **2026-10-08**. It combines foundational experiments, quantitative syntheses, and clearly labeled theoretical commentary. The [source catalog](../sources/human-memory-practices.json) records status, access date, limitations, and actual inspection depth. Searches targeted the named practices and their boundary conditions; this is not a systematic review, exhaustive search, or new meta-analysis. No private material or agent experiment contributes to the findings.

Selected full-text sections were inspected for HM05, HM06, HM07, HM09, and HM14–HM18. The remaining records are primary abstracts or publisher previews, except HM21, for which the abstract and indexed primary discussion were inspected, and HM23, for which the abstract and indexed primary methods/results/discussion were inspected after direct full-text access failed. For HM07, inspection covered the abstract, definitions, and theoretical framing rather than complete statistical methods. Abstract-only coverage does not support claims about uninspected controls or publication-bias adjustments. Full-text inspection also does not mean reproduction, independent reanalysis, or verification of every referenced study. Recent syntheses HM19 and HM20 are included as abstract-level updates.

Throughout this review, **human evidence** means a finding or interpretation in the cited work. **Engineering hypothesis** means a proposed application requiring a separate agent evaluation. Study-phase performance, delayed retention, transfer to new questions, and completion of a future intention are distinct outcomes.

## Retrieval practice, feedback, and the comparison condition

**Human evidence.** Roediger and Karpicke's prose experiments found that restudying could outperform testing after five minutes, while testing without feedback improved retention at longer delays. Confidence favored restudy despite its poorer delayed performance. The time of measurement changes the conclusion. [HM01](https://pubmed.ncbi.nlm.nih.gov/16507066/)

Rowland's meta-analysis supports a testing advantage over restudy, with larger benefits for initial recall than recognition tests. Its abstract discusses several possible explanations rather than identifying one settled mechanism. Retrieval effort is a contributor, not a complete causal account. [HM02](https://pubmed.ncbi.nlm.nih.gov/25150680/)

Butler and Roediger found that both immediate and delayed feedback improved later cued recall and reduced intrusions from multiple-choice lures relative to no feedback. A practice test can introduce misleading alternatives as well as useful retrieval opportunities. [HM03](https://pubmed.ncbi.nlm.nih.gov/18491500/)

A 2025 synthesis compared retrieval with stronger elaborative activities, rather than plain rereading. It reported a small overall retrieval advantage and a feedback-dependent pattern; elaboration did better when feedback was absent. The comparator materially changes what “effective” means. [HM19](https://link.springer.com/article/10.1007/s10648-025-10076-6)

A June 2026 meta-analysis distinguishes retention of tested material from benefits to subsequently learned material. It reports that many free-recall comparisons mix these direct and forward effects, with larger effects in mixed designs. This cautions against treating all testing results as one phenomenon. [HM20](https://pubmed.ncbi.nlm.nih.gov/42258276/)

**Engineering hypothesis.** A retrieval rehearsal should begin with a realistic future question, search the store, open supporting records, and check the answer against a source. It can expose absent evidence, poor indexing, stale state, or a reader's failure to interpret available evidence. Merely rereading a summary cannot distinguish these causes. Record the failure before editing; otherwise a polished replacement can hide the original defect.

Feedback should come from a reference with defined authority: a verified execution result, a dated correction, an authoritative document, or a fixture's ground truth. Another generated answer is not automatically an independent reference. Keep observed facts, inferred explanations, and proposed repairs distinguishable. In evaluation, compare the rehearsal's benefit with spending the same time or tokens on source inspection and ordinary maintenance.

## Spacing, cramming, and lag

**Human evidence.** Cepeda and colleagues synthesized distributed verbal practice across hundreds of experiments. Their analysis treats the gap between learning episodes and the delay until the final test jointly: the gap associated with best retention increases as the target retention interval increases. [HM04](https://pubmed.ncbi.nlm.nih.gov/16719566/)

Their later fact-learning experiment varied gaps and tested retention over much longer intervals. Performance rose and then fell as the gap increased; an indefinitely longer gap was not better. Its schedules, learning criterion, and factual material bound any numerical prescription. [HM05](https://labs.biology.ucsd.edu/rifkin/courses/bieb100/f14/Cepeda_et_al_2008_Psychological_Science_Spacing_Effects_in_Learning_A_Temporal_Ridgeline_of_Optimal_Retention.pdf)

**Engineering hypothesis.** Human spacing results do not justify a daily cron job, an exponential schedule, or a universal forgetting coefficient for files. A durable file does not lose bytes because it went unread. Its usefulness can decline through changed facts, broken links, competing records, mismatched vocabulary, or changing tasks. Those are separate maintenance problems with different clocks.

Test change-triggered reviews against fixed intervals under equal maintenance budgets. Candidate triggers include a corrected constraint, a renamed entity, a superseded decision, a failed retrieval, or an approaching obligation. A periodic audit may still help discover silent failures, but its interval should follow observed risk and cost. Record the last **verification** separately from the last read: opening an old assertion does not make it current.

## Interleaving depends on what must be learned

**Human evidence.** Kornell and Bjork found that interleaving different artists' paintings improved classification of new examples, although participants often preferred blocked presentation. Here interleaving also creates spacing, so the experiment does not isolate every possible explanation for the advantage. [HM06](https://web.williams.edu/Psychology/Faculty/Kornell/Publications/Kornell.Bjork.2008a.pdf)

Brunmair and Richter's quantitative synthesis found substantial variation by material: visual category tasks benefited more consistently, expository text results were uncertain, and some word tasks favored blocking. Similarity within and between categories helps define when comparison is useful. This is not evidence for indiscriminate topic switching. [HM07](https://pubmed.ncbi.nlm.nih.gov/31556629/)

Little and Nepangue's 2025 category experiments report that the relative value of blocking and interleaving depended on an instructed memorization or rule-finding strategy, with the pattern extending across a delay. Artificial letter-string categories limit direct educational or agent generalization. [HM21](https://pubmed.ncbi.nlm.nih.gov/40426440/)

**Engineering hypothesis.** A retrieval audit can deliberately compare confusable records: two similarly named projects, an old and current policy, or an approved action and a proposal. Its purpose is discrimination, not biological category learning. Keep each source identifiable instead of blending their content into one summary. During evaluation, vary confusability independently from corpus size and measure whether contrastive questions reduce wrong-entity and wrong-version answers. Blocking may be preferable when the reader first needs a coherent procedure or dependency chain.

## Elaboration, self-explanation, and organizational cues

**Human evidence.** Bisra and colleagues' synthesis found benefits from prompting learners to explain causal or conceptual relationships across multiple instructional conditions. The result concerns human-produced explanations during learning; it does not imply that every explanation is accurate or that extra elaboration is always worth its time. [HM08](https://link.springer.com/article/10.1007/s10648-018-9434-x)

Dunlosky and colleagues assessed practices across learner characteristics, materials, and outcome measures. Their review discusses prior knowledge, implementation quality, time demands, and limited durability evidence for explanatory techniques. Utility ratings are contextual judgments about the reviewed human literature, not universal rankings for every task. [HM09](https://acs.ist.psu.edu/ist521/dunloskyRMNW13.pdf)

Bower and colleagues found that presenting categorized words hierarchically improved free recall compared with random presentation; the effect was smaller for recognition. Their proposed retrieval-plan account concerns organized human learning, not evidence that nested folders outperform search in an agent store. [HM22](https://www.sciencedirect.com/science/article/pii/S0022537169801246)

The method of loci places imagined items along a familiar spatial route. Dresler and colleagues compared human memory athletes with controls and tested six-week training against active and passive controls. Training improved word-list recall and yielded more athlete-like fMRI connectivity patterns. The four-month assessment re-encoded a list, so durable performance does not demonstrate uninterrupted retention of original words. Its male training sample and constrained tasks limit generalization. [HM23](https://pmc.ncbi.nlm.nih.gov/articles/PMC5439266/)

**Engineering hypothesis.** Preserve why a decision was taken, which constraint it satisfies, and which source supports that relationship. A brief rationale can give a future reader routes from a changed requirement to the relevant decision. Generated causal links remain hypotheses until checked; plausible explanations can overwrite uncertainty if they are stored as facts.

An overview can provide a retrieval plan without containing every detail. Test a compact index with stable links against exhaustive summaries, holding retained evidence constant. Assess whether readers locate the necessary original material and recover exceptions, dependencies, and negative constraints. A shorter overview may be useful, but compression should be judged by what future questions it loses as well as what it saves. A consistent traversal route is another testable cue design; human spatial mnemonic results do not prove an agent should use a spatial interface or any particular folder layout.

## Encoding specificity and cue overload

**Human evidence.** Tulving and Thomson's encoding-specificity account relates effective retrieval cues to how an episode was encoded. Their recognition-failure findings challenge the idea that recognizing an item is invariably easier than recalling it. Only the primary abstract and publisher preview were reviewed here. [HM10](https://www.researchgate.net/publication/232454634_Encoding_specificity_and_retrieval_processes_in_episodic_memory)

Watkins and Watkins tested a cue-overload account of interference: recall declined as more material shared a functional category cue. The indexed primary abstract describes controlled list experiments. It does not provide a numeric limit for tags, folder contents, or search results. [HM11](https://doi.org/10.1037/0278-7393.1.4.442)

**Engineering hypothesis.** Capture cues a later task is likely to supply: entity names and aliases, the triggering problem, affected artifact, decision date, status, and scope. Evaluate natural paraphrases as well as the note's exact wording. Adding more generic labels can create ambiguity; adding a discriminating attribute can help select the correct episode. Neither outcome follows automatically from a human cue theory.

Avoid assuming that the original author and the next reader share a naming convention. A fictional handoff test can ask an unfamiliar reader to find a decision using the problem description alone. Separate failures of candidate retrieval from failures of selection among retrieved candidates. Measure the value of extra cues against their storage, update, and distraction costs.

## Source monitoring and misleading confidence

**Human evidence.** Johnson, Hashtroudi, and Lindsay's source-monitoring framework treats judgments about information's origin as fallible attributions based on experiential features and criteria. It distinguishes having information from correctly identifying where it came from. This is a theoretical synthesis, not a provenance-system experiment. [HM12](https://pubmed.ncbi.nlm.nih.gov/8346328/)

Koriat and Bjork's paired-associate experiments examine competence illusions when judgments are made with the answer present, although it will be absent at test. The perceived relationship of an already visible answer to its cue can mislead predictions of later recall. [HM13](https://pubmed.ncbi.nlm.nih.gov/15755238/)

**Engineering hypothesis.** Store explicit provenance rather than asking a model to reconstruct origin from prose style. Distinguish user instructions, observed outcomes, third-party claims, model inferences, and unresolved proposals. A source pointer must resolve to the specific evidence, and its authority must match the question. Multiple summaries derived from one observation remain one evidence lineage.

Treat confidence as an output to evaluate, not a substitute for evidence. Measure unsupported certainty, appropriate abstention, and correctness conditioned on confidence. Test with convincing distractors and inaccessible or contradictory sources. Require answers to identify both the claim and its supporting record; then inspect whether the cited material actually supports it. Fluent answers with citations can still select the wrong source.

## External offloading and prospective reminders

**Human evidence.** Risko and Gilbert review using the environment to change a task's cognitive demands. Their metacognitive framework includes mistaken evaluations and both costs and benefits of offloading. Successful access to an external aid and retention without that aid are different measurements. [HM14](https://samgilbert.net/pubs/Risko2016TiCS.pdf)

Gilbert's intention-offloading experiments found that people used external reminders adaptively with load and interruptions, and reminders improved target accuracy. The work distinguishes triggering a future action from remembering what to do; links to everyday intentions were limited. [HM15](https://samgilbert.net/pubs/Gilbert2015QJEP.pdf)

**Engineering hypothesis.** An obligation record needs an actionable trigger as well as content. A due date buried in an archive cannot be assumed to appear at the relevant moment. Consider a record with a condition, intended action, owner, current status, and evidence of fulfillment, connected to the authorized scheduler or task-entry workflow.

Evaluate reminder delivery, interpretation, and completion separately. Detect repeated completed reminders, missed cancellations, stale owners, and conditions that never fire. A reminder should prompt checking the current obligation before acting. Its existence does not establish permission for a new external action, and delivery alone does not establish execution. Compare event-based cues and scheduled checks under realistic interruptions.

## Generation effects and the limits of difficulty

**Human evidence.** Slamecka and Graf's experiments found better memory for words generated under supplied rules than for words read. This is constrained generation with known targets. It is not a finding that inventing explanations, filling gaps, or producing more text makes that text trustworthy. [HM16](https://www.researchgate.net/profile/Peter-Graf/publication/232485723_The_Generation_Effect_Delineation_of_a_Phenomenon/links/53f5eedf0cf2888a7491f9cb/The-Generation-Effect-Delineation-of-a-Phenomenon.pdf)

Bertsch and colleagues synthesized generation effects across many studies and found meaningful moderator variation. Different generation rules, tests, and designs do not yield one invariant benefit. A pooled human-learning result is a starting point for boundary questions, rather than a software recipe. [HM17](https://mcdaniel97.github.io/Publications/Bertsch%20et%20al.%202007.pdf)

Bjork and Bjork's theoretical commentary distinguishes immediate accessibility from durable learning and emphasizes that difficulty must activate useful processes within a learner's capabilities. Obstacles that cannot be productively overcome are not made beneficial by being difficult. This is commentary, not a new controlled comparison. [HM18](https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2021/01/RABjorkELBjorkJARMAC2020ForPostingSingleSpaced.pdf)

**Engineering hypothesis.** Generating a question, candidate answer, or concise explanation may uncover missing information, but each claim needs feedback against evidence. Deliberately making an agent's search harder has no established benefit. Preserve accessible source material and minimize unnecessary barriers. If a self-generated cue improves retrieval, establish that gain through comparison with a source-derived cue under equal budgets.

## Mechanism is not implementation

Human study interventions operate in a learner whose internal memory can change. In the filesystem setting considered here, the model weights are fixed between calls. Searching, viewing, or rereading files **does not strengthen model weights without training**. Future behavior can change because files, indexes, prompts, tools, or loaded context change. Those are observable implementation effects, not evidence of synaptic rehearsal or consolidation.

This distinction supplies a useful control: repeat an audit against an unchanged store with a fresh reader. If performance improves only when the previous conversation is present, the benefit may reside in transient context. If a repaired index helps fresh readers, the benefit can be attributed more specifically to the external representation. Keep model version, available tools, task wording, and retrieval budget fixed when making that comparison.

## Proposed ablations and success criteria

The following are research proposals, not tested results. Use fictional or explicitly authorized corpora with independently specified evidence and state transitions. Hold source content and total budgets constant whenever possible. Run maintenance questions separately from final test questions to avoid teaching directly to the evaluation.

| Hypothesis | Matched comparison | Measure that could reject it |
| --- | --- | --- |
| Retrieval audits expose useful defects | Question-first audit versus equal-budget source review | Fresh-reader evidence recall and task completion fail to improve |
| Checked repairs outperform unchecked rehearsal | Reference-based correction versus generated self-confirmation | Unsupported claims or regressions increase |
| Review timing should follow change risk | Event-triggered versus fixed-period review | Stale-answer rate, missed obligations, and maintenance cost show no advantage |
| Discriminating cues improve refinding | Entity/status/problem cues versus generic labels | Wrong-entity selections and search cost remain unchanged |
| Provenance reduces source confusion | Claim-specific lineage versus unlinked summaries | Wrong-source attribution and unsupported certainty do not fall |
| Contrast helps confusable cases | Paired contrast questions versus independent questions | Current-versus-superseded selection does not improve |
| External triggers recover obligations | Triggered records versus identical passive records | Delivery succeeds but completion or cancellation accuracy does not |

Report retrieval coverage, correct source selection, current-state accuracy, appropriate abstention, obligation completion, tool calls, tokens, latency, and repair cost separately. Include negative cases: unavailable evidence, ambiguous entities, conflicting dates, canceled tasks, and unsupported causal stories. A correct final answer can coexist with an unhealthy store, while a healthy store can be mishandled by its reader. These experiments must establish agent performance directly; human study benefits cannot stand in for that evidence.
