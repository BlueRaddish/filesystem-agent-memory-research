# Fictional memory fixture

Every record and entity in this fixture was created for this project. It is not anonymized or reconstructed from a real user's memory. The small corpus demonstrates version, scope, and verification traps; it is not representative enough to establish model performance.

Use the [fresh-agent protocol](../evaluation/protocol.md). Stage the agent-facing subset into a new empty workspace:

```sh
python scripts/make_fixture.py /path/to/new-empty-trial-directory
```

The result contains `TASKS.md` and `memory/` only. Run tasks in separate fresh trials when measuring them independently. Restrict the agent to the staged workspace; the public repository contains evaluator answers and must remain inaccessible during a valid trial. The staging script provides no operating-system sandbox or provider-memory isolation.

The default current-state brief deliberately stops before a correction, despite having a later file-level edit date. The evidence also contains a scoped legacy exception, an earlier failed check, and a prohibition on upload. A reader should reconcile the relevant records rather than treating the brief's modification date or an assistant success claim as decisive.

Evaluator-only material is [the requirement ledger](../evaluation/fixture-gold.json). It is public for inspectability and is not copied into the trial. The example requires only local text creation and inspection, with no services, credentials, or network actions.
