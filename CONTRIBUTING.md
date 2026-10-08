# Contributing

Useful contributions include a missing primary source, a source-version correction, an unsupported-claim correction, an adjacent result with a clearly stated transfer limit, a matched experiment, or an auditable negative result.

For a source addition, add its structured record to the appropriate catalog and cite its ID with its direct primary URL. Record publication status, version where useful, actual review depth, and a specific limitation. Distinguish author reports from independent reproduction. Update the generated bibliography by running:

```sh
python scripts/check_repository.py --write-bibliography
python scripts/check_repository.py
```

For an experiment, state the task and gold evidence, memory conditions, reader/tool/model versions, budgets, repetitions, missing/failed runs, leakage controls, metrics, and failure analysis. Do not report an LLM judge's score as verified action success. Publish only materials you have permission to share; synthetic examples must be clearly labeled.

Keep changes focused. Prefer standard-library checks over new dependencies. Do not mirror papers, figures, or third-party datasets merely because they are publicly readable. Do not include personal account data or local machine paths. Review [publication privacy](PRIVACY.md) before submitting.

This repository accepts original contributions under its MIT license. Third-party referenced works remain under their own licenses and copyright.
