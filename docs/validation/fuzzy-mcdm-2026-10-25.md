# Fuzzy selection implementation validation — 2026-10-25

Workspace: `D:/research/federated-system`, Windows, Java/Spring Boot and Python 3.13/PyTorch CPU. These are implementation checks, not a 70-round research result.

| Command | Result |
|---|---|
| `cd ferderatedsystem; .\gradlew.bat test bootJar --no-daemon` | BUILD SUCCESSFUL; 39 tests, 0 failures/errors/skips |
| `.\.venv\Scripts\python.exe -m pytest` | 15 passed; 1 existing Starlette/httpx deprecation warning |
| `.\.venv\Scripts\python.exe scripts/verify_fuzzy.py` | PASS; real Python training, Java selection, SQLite persistence and TXT export |
| `git -c safe.directory=D:/research/federated-system diff --check` | Passed; Git emitted line-ending notices |

Java suites: ControlledExperimentsTests 9; ExperimentResultTests 4; FerderatedsystemApplicationTests 1; FuzzyCoordinatorTests 2; FuzzySelectionTests 14; PaperExperimentsTests 3; PoliciesTests 4; ScenarioTraceTests 2. The coordinator test iterates all three fuzzy methods and two baseline methods using deterministic timing fixtures, compares uninterrupted execution to a new coordinator resumed after two committed rounds, and checks exact selected/accepted IDs, scores, deficits, lambda and fairness state.

The final real-service smoke used synthetic data, 100 clients, K=5, Non-IID alpha=.5, seeds42/43, 3 rounds per F1–F5 experiment (10 runs, 30 matrix rounds). Independent Python scalar calculations verified fuzzy normalization, weighted ideals, vertex distances, CC, final scores, credit accrual/repayment and adaptive feedback from saved round JSON. Actual initial tensor hashes and complete exogenous traces matched across all five methods per seed. Baseline snapshots contained no scheduler state.

An additional live adaptive experiment was interrupted after committed round1. Both Java and Python processes were restarted. The experiment resumed from the SQLite snapshot and completed round12; committed metrics were unchanged, the first resumed selection used the persisted credit balance and all twelve rounds passed independent numerical/state replay. This is separate from the F matrix and does not contribute to its statistics.

Local evidence:

* `artifacts/fuzzy-smoke/d1faf7afab/summary.json`
* `artifacts/fuzzy-smoke/d1faf7afab/test.db`
* `artifacts/fuzzy-smoke/d1faf7afab/services.log`
* `artifacts/comparisons/20261025-205750-cd429ee2/F-fuzzy-client-selection.txt`
* Per-experiment config, result and full round evidence in the report batch's `runs/` directory.

These artifacts are local outputs under the repository's existing artifact ignore rules. The script regenerates equivalent checks in a new folder. Measured durations and consequently history-dependent rankings on fresh runs can differ; exact deterministic resume is tested with fixed observed timings, while the real restart smoke verifies state continuity. The 5-seed, 70-round Covertype study was **not run**. Synthetic smoke metrics cannot establish superiority, significance or convergence.
