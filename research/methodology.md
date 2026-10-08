# Methodology and evidence boundaries

## Review type and scope

This is an initial **AI-assisted structured scoping review**, with a public-source search cutoff of **2026-10-08 UTC**. It combines targeted source lookup, keyword searches, and reference/project-page snowballing. It is not an exhaustive systematic review or meta-analysis. There is no preregistered search, independent duplicate screening of every source, complete exclusion ledger, or claim of literature saturation.

The research question is how persistent files and surrounding processes can support accurate context recovery and continuation by an unfamiliar agent. Selection includes agent memory construction and updates; retrieval and context use; conversational and interactive benchmarks; personal information management; creator-developed filing practices; and digital preservation, provenance, metadata, and version access.

Primary research papers, official standards, creator documentation, and first-party engineering reports are preferred. Sources are included for a concrete mechanism, evaluation method, adjacent failure model, or relevant counterexample. Creator advocacy and vendor experiments are explicitly distinguished from independent controlled evidence.

## Search and verification workflow

Search families covered terms such as filesystem agent memory, long-term memory evaluation, temporal updates and conflicting state, reasoning-intensive retrieval, long-context distraction and sufficiency, personal information management folders/tags/facets, digital preservation fixity, and provenance/versioning. Specific paper titles, arXiv identifiers, proceedings records, official project pages, and linked code were then checked directly. This describes the search strategy; it is not a complete reproducible log of every search-engine query or ranking.

Earlier public research links were reconciled into [an explicit link ledger](../sources/earlier-links.json). URL variants are retained as aliases rather than counted as distinct studies. Access-blocked links remain labeled as such; a blocked page is not treated as inspected evidence. An alternative primary record can support a paper's inclusion without making its inaccessible counterpart verified.

The four topic reviews were drafted in parallel from public sources. An additional reviewer checks scientific precision and another checks publication privacy. These are editorial checks by AI agents, not external peer review. The synthesis, catalog reconciliation, and publication checks are performed separately from those drafts.

## What each source record means

Machine-readable catalogs record a stable local ID, title, year, primary URL, source kind, venue/status, topics, evidence note, limitation, access date, and review depth. Some include alternate URLs or more precise version/status metadata. A consulted-version year for undated living documentation is labeled and is not asserted as its original publication year.

- **Abstract review** means the abstract or an institutional author summary was inspected; it does not support detailed claims about unavailable methods.
- **Full-text review** means selected relevant method, result, and limitation sections were inspected. It does not mean line-by-line verification, code audit, reproduction, or independent statistical reanalysis.
- **Official documentation/report review** means the described interface, practice, or first-party experiment was inspected. Its authority is limited to the relevant documented claim.

Exact `review_level` wording varies to disclose what was read. A preprint's declared acceptance is distinguished from a published proceedings record. Access dates do not imply that later versions cannot appear. The bibliography is generated from the catalogs; it is a navigation aid, not a second independent evidence review.

## Claim discipline

The reviews separate published observations, proposed mechanisms, documented capabilities, and this project's engineering inferences. Human-interface results do not become agent-performance findings. Byte integrity and provenance do not become truth guarantees. Conversational QA does not become task continuation. A correct citation does not alone demonstrate that the model actually relied on the cited evidence.

No headline scores are pooled into a cross-paper leaderboard. Models, corpus variants, tool budgets, answer formats, judges, and evaluation categories differ. Numerical results retained in individual reviews are scoped to the original experiment. Third-party papers are linked, with short original summaries; full texts, figures, benchmark data, and implementations are not redistributed here.

## Limitations and next review

Selection is relevance-driven and English-heavy. Search-engine availability, inaccessible pages, recent preprint churn, publication incentives, and first-party reports can bias coverage. Some empirical PIM papers are abstract-only. Public benchmarks may expose constructed conversations, annotation defects, model contamination, or simulator assumptions; those issues require dataset-level investigation beyond this review.

The repository does not publish private conversations, private filesystem inventories, private experimental statistics, or reconstructed personal examples. Its fixture is fictional and was created for this project. No comparative model experiment has been run or claimed here.

A stronger follow-up would preregister questions and eligibility criteria, freeze search dates and source versions, keep an exclusion ledger, have human researchers independently screen uncertain sources and audit claims, and run the proposed matched experiments. Corrections should update the relevant source record, dependent claims, and revision history rather than silently replacing conclusions.
