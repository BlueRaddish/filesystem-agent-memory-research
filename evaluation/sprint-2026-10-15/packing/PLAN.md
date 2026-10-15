# Exploratory context expansion, October 15

This is a post hoc mechanism experiment on the already published October 13 bank.
Historical results and the two-window ceiling motivated the policies. It is not
preregistered confirmation, independent replication, or a fresh-reader experiment.
The source and this plan are hashed before this lane computes new gold-span results.

The census is all 216 confirmation queries from 72 authored histories in 12 related
template groups. Each query uses its original 144-document collection, the exact
saved top 32 candidates from body BM25 and entity RRF, and 4,096, 8,192 and 16,384
UTF-8 bytes. Five policies produce 6,480 packets. Rankings will be extracted from
hash-verified public ranking shards; no ranker is retrained or rerun.

All policies use the frozen depth-two closure (16 new records per seed) and identical
compact source wrappers. Two windows calls the frozen closure_passages policy.
Radius 3 and radius 8 keep its two lexical anchors, expand their context radius,
merge overlaps, and retain its window-pass/document-order scheduling. Whole body
packs complete bodies in that same closure order. Residual gaps first preserves the
exact two-window packet, then tries each uncovered contiguous gap in each already
selected document, in closure order. Gaps are indivisible, and oversized ones are
skipped. None uses gold spans, required IDs, expected answers or semantic feedback.

Every byte budget includes rendered wrappers and separators. Equal budgets do not
mean equal actual bytes or equal source text. Body, wrapper/separator and unused
bytes will be reported. Every packet is retained as reconstructible source offsets
plus packet digest; source content remains in the unchanged public bank.

The primary descriptive endpoint is containment of any complete authored
sufficient-span alternative. Whole-original bundles, original-ID coverage and
packet utilization are separate diagnostics. Authored alternatives need not cover
all semantically sufficient possibilities. These metrics do not measure answer
accuracy or reader success. Query-level paired gains and regressions will accompany
rates; per-template results expose dependence. No population significance test or
independence claim will be made for the repeated packet cells.

Execution order: (1) fictional self-checks with normal and known-bad cases;
(2) seal code, input identities and plan; (3) build all packets with answer-free
policy inputs; (4) evaluate source spans; (5) independently reconstruct all packets,
check byte bounds and exact slices, and recompute all endpoints; (6) render three
scientific PNG/SVG pairs with exact plot tables and inspect every PNG. Keep failures
and any amendment. Never silently overwrite an existing run or historical file.

Limits: the bank, supplied aliases/links and templates were authored synthetically;
the agent already knew prior aggregate results. This small corpus and three fixed
budgets do not establish general optimality, production speed, natural-vault
onboarding, long-term memory quality or benefits from an LLM decision controller.
