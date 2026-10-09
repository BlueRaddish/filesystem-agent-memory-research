# Filesystem Agent Memory Research

How should persistent files help an unfamiliar agent recover the context needed to continue work accurately?

This project is a public, source-grounded research review of agent memory, retrieval, personal information management, digital preservation, biological memory, and human learning practices. It prioritizes **preserving important details, resolving changing state, and succeeding after a fresh start**. It studies PARA alongside other organizational approaches without assuming that any folder taxonomy is an optimal memory architecture.

**Initial review cutoff: 2026-10-08 UTC. Pilot execution: 2026-10-09.** This is an AI-assisted structured scoping review with an original fictional continuation pilot: 80 main reader trials, six exploratory onboarding trials, five engineered filesystem traces and four separately reported transport diagnostics. It is not an exhaustive systematic review, a peer-reviewed publication or a validated benchmark. Sources have different publication statuses and review depths, recorded in their catalog entries.

## Start reading

| Document | Purpose |
| --- | --- |
| [Pilot report and 12 figures](evaluation/study-2026-10-09/REPORT.md) | Actual outcomes, a stale-correction failure, unfamiliar-reader controls, scoring/transport limits and next experiments |
| [Interactive pilot viewer](evaluation/study-2026-10-09/index.html) | Portable HTML with trial filters, correction lineage and maintenance timelines; download and open to interact |
| [Independent pilot audit](evaluation/study-2026-10-09/AUDIT.md) | Reconstruction of all 86 main/onboarding receipts and separately labeled posthoc convention sensitivity |
| [Synthesis and recommendations](research/synthesis.md) | Conclusions, evidence boundaries, a minimal design, and open questions |
| [Filing hypotheses](research/filing-hypotheses.md) | Eight minimal interventions, matched comparisons, failure cases, and fresh-reader tests |
| [Agent memory](research/agent-memory.md) | Evidence, current state, procedures, temporal updates, and agent handoffs |
| [Retrieval and context](research/retrieval-and-context.md) | Lexical and semantic search, long context, sufficiency, compression, and attribution |
| [Organization and retention](research/organization-and-retention.md) | Human PIM, folders/tags/facets, PARA, stable IDs, and preservation standards |
| [Recent and complementary evidence](research/recent-evidence.md) | Additional 2025–2026 studies, versioned artifacts, context restoration, and engineering reports |
| [Biological memory](research/biological-memory.md) | Memory systems, episode/context binding, consolidation, replay, updating, and forgetting |
| [Human memory practices](research/human-memory-practices.md) | Retrieval practice, feedback, spacing, cues, discrimination, calibration, and external reminders |
| [Applying human and biological ideas](research/brain-agent-transfer.md) | Existing brain-inspired retrieval systems, candidate implementations, transfer limits, and falsifiable experiments |
| [Methodology](research/methodology.md) | Selection, source verification, evidence categories, and limitations |
| [Annotated bibliography](sources/README.md) | Human-readable index of the machine-readable source catalogs |
| [Fresh-agent evaluation protocol](evaluation/protocol.md) | Test retention, discovery, interpretation, and actual continuation separately |
| [Fictional fixture](examples/README.md) | A small, inspectable example of correction and source-authority traps |

## Working conclusion

The literature does not establish a universally best folder structure or memory product. A useful direction to test is **recoverable source evidence, a maintained current-state view, and simple navigation that can expand back to the sources**. Correctness also depends on the writer, retriever, reader, and execution environment. An organized collection can still contain an inaccurate summary; a perfect lookup can still select an obsolete rule.

The project distinguishes evidence preservation from retrieval, retrieval from interpretation, and interpretation from action success. Its proposed improvements are hypotheses with failure cases and measurements, rather than an architecture ranking.

The first pilot passes the frozen rubric in **60/80 main trials**. A disclosed source audit accepts **77/80 checked artifacts** after accounting for underspecified output conventions; neither count is a population accuracy estimate. One reader receives all required originals yet retains a superseded setting through successful structural checks. The pilot motivates testing source-version incorporation and correction-specific checks; it does not identify a winning folder taxonomy or justify a production migration.

The biological and human-practice extension examines functions worth translating rather than treating agent files as a replica of a brain. Evidence-checked retrieval probes, distinctive cues, episode-plus-state views, and explicit future obligations are candidate interventions. Human learning benefits and brain-inspired metaphors do not establish that these improve agent continuation; the transfer review specifies comparisons that could test them.

## Check the repository

Python 3.10 or later; the checks and reader/maintenance runners use the standard library. Regenerating pilot figures additionally needs Matplotlib.

```sh
python scripts/check_repository.py
python scripts/make_fixture.py /path/to/new-empty-trial-directory
python evaluation/study-2026-10-09/run_study.py selfcheck
python evaluation/study-2026-10-09/replay_maintenance.py --self-check
```

The first command checks catalog structure, citation mappings, local links, publication hygiene, and fixture references. It does not validate every scientific claim or prove absence of sensitive information. The second stages only the fictional agent-facing memory and task prompt for a trial; it excludes evaluator materials. Read the [protocol](evaluation/protocol.md) before using it.

## Scope and contribution

Public primary sources are linked rather than mirrored. The original prose, examples, and scripts use the [MIT license](LICENSE); third-party works retain their own rights. See [methodology](research/methodology.md), [privacy](PRIVACY.md), and [contribution guidance](CONTRIBUTING.md). Public corrections and extensions are welcome, especially matched experiments, negative results, and research that tests unfamiliar readers and changing evidence.
