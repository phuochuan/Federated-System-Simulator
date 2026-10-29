# Fixed Lambda Ablation validation — 25 October 2026

These checks validate implementation, not the research hypothesis about adaptive versus large fixed lambda.

| Command | Result |
| --- | --- |
| `cd ferderatedsystem; .\gradlew.bat test bootJar --no-daemon` | BUILD SUCCESSFUL; 46 tests, zero failures/errors |
| `.\.venv\Scripts\python.exe -m pytest` | 15 passed; one existing Starlette/httpx deprecation warning |
| `.\.venv\Scripts\python.exe scripts/verify_fuzzy.py --lambda-ablation` | PASS: L0–L5, two seeds, three rounds each, 12 real-training experiments |
| `.\.venv\Scripts\python.exe scripts/verify_fuzzy.py` | PASS: regression F1–F5, two seeds, three rounds each, 10 real-training experiments |

Both HTTP smokes used their own ports, Python workers, Java processes and SQLite files. They verified identical actual initialized weights and full exogenous traces per seed, mathematical score/credit/controller replay, feasible selection, and same-history raw-TOPSIS replacement counts. Each smoke additionally interrupted an adaptive experiment after committed round1, restarted both services and resumed from SQLite through round12 without changing committed metrics.

Lambda-specific checks verified that L0 has zero replacements, L1–L4 retain their configured lambdas at every round, only selection/initial lambda differ between row configs, other configuration or trace changes are rejected, and invalid bounds fail before any training. Numerical report tests independently check tail mean/sample SD, maximum drop, signed final-round change and replacement ratios; failed batches export INCOMPLETE without a final summary. No assertion requires adaptive to outperform fixed lambda.

Local L evidence:

* `artifacts/lambda-smoke/11855a6313/summary.json`, `services.log`, `test.db`
* `artifacts/comparisons/20261025-232329-a5c0f6bb/L-fixed-lambda-ablation.txt`

Local F regression evidence:

* `artifacts/fuzzy-smoke/4e27ea588f/summary.json`, `services.log`, `test.db`
* `artifacts/comparisons/20261025-232712-32bcd9d4/F-fuzzy-client-selection.txt`

Artifacts are local ignored outputs. The scripts regenerate independent batches. The full 30-experiment, 70-round Covertype ablation and additional partition studies were **not run**. Follow the [predeclared protocol](../lambda-ablation.md); do not pool synthetic smoke results with research results or tune on reported test scores.
