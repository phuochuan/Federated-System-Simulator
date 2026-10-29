# Held-out Pareto Trade-off Evaluation

This is **PARETO_COMPARISON**, following completed Phase A **NO_MATCH** evidence.
It does not relax matching tolerances, relabel Phase A, or modify the old matched
evaluation guard. Phase A, F1–F5 and L0–L5 outputs remain unchanged.

The research question is whether adaptive feedback offers a better observed
learning/fairness/stability/efficiency trade-off across held-out partitions.
There is no weighted score and no automatic overall winner.

## Locked policies and inherited protocol

| Policy | Source in Phase A | Selection | Lambda |
| --- | --- | --- | ---: |
| P1 | M3 | fuzzy_topsis_fair | fixed .650 |
| P2 | M4 | fuzzy_topsis_fair | fixed .675 |
| P3 | M6 | fuzzy_topsis_fair | fixed .725 |
| P4 | M7 | adaptive_fuzzy_topsis_fair | initial .300 |

The complete fuzzy settings, weights, normalization/uncertainty configuration,
credit recurrence and adaptive parameters are inherited unchanged. Adaptive
rate=.05, target Gini=.55, smoothing=.8, lambda bounds0–1, maximum update=.05
remain as in Phase A. Source report/lock file hashes are pinned in
[`configurations/pareto-tradeoff.json`](../configurations/pareto-tradeoff.json).

The source must be a complete NO_MATCH validation matrix, with valid policy lock
and matching initial tensor, scenario and manifest hashes within every paired
cell. New settings are compared to the source lock before training. Source run
exports provide full manifest checksums. Held-out features/labels/split hashes
must match the source pools, while partition RNG seeds must be disjoint.

Covertype, Dirichlet alpha=.5, split seed42, held-out partition seeds2001/2002/2003,
training/scenario seeds42–46, 100 clients, K=5, 70 rounds, FedAvg,
`mlp_54_256_128_7`, epoch1/batch32/LR.01 and the shared heterogeneous scenario:
**4 ×3 ×5 =60 runs**. Policies are shuffled with a fixed seed within each cell;
comparisons verify full manifest, initial tensor, initialization seed and every
population scenario event. The inherited Phase A matching settings remain in
the input as historical context; they do not select or gate these four policies.

## E0 and immutable provenance

The existing successful E0 certifies its **historical** build/runtime. Adding this
mode changes the Java build hash and plotting source hash. A fresh E0 on the new,
frozen Java/Python/runtime is therefore required before real held-out training.
The gate checks complete audit counts, three repeats in each of four policy/mode
groups, state/timing replay, conditional training replay, compatible settings and
exact runtime identity. A smoke audit cannot unlock a real Covertype experiment.

`pareto_preflight` records `ready:false`, a blocker reason and
`determinismClaimed:false` if E0 is absent, incompatible or failed. It starts no
training. `heldout_pareto` enforces the same gate and refuses to train while
blocked. It never silently treats an old audit as evidence for a new binary.

`pareto-tradeoff-config.json` is an immutable policy/protocol/runtime manifest,
created before held-out work. `pareto-execution-manifest.json` additionally locks
the successful current E0 report hash. Source Phase A and current E0 evidence are
rechecked before final reporting. Changing the policies, protocol, source evidence
or executing build requires a new output directory, not rewriting old metadata.

## CLI / IDE commands

Build once, then keep the same JAR, Java version, Python environment, retry policy
and launch style for E0 and Pareto. Do not switch between IDE/Gradle and `java -jar`
halfway through: classpath content is part of runtime identity.

```powershell
Push-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Pop-Location
.\.venv\Scripts\python.exe -m pytest ml-python/tests scripts/test_fairness_matched.py -q

# Config creation only: this does not start E0 or the 60 runs.
.\.venv\Scripts\python.exe scripts/prepare_pareto.py
```

The preparation script reads the completed source Phase A, pins its hashes and
creates a NEW folder `artifacts/research/pareto-<timestamp>/` containing:

- `e0-input.json`, inheriting the same training/controller/scenario settings.
- `pareto-tradeoff-input.json` with P1–P4 fixed before held-out execution.
- `preflight.properties`, `e0.properties`, `pareto.properties`, `workflow.properties`.
- One-argument files for each stage, using `--spring.config.additional-location`.
- A path for a new SQLite database, preserving all old results.

Use `--phase-a-root <path-to-e1>` if the completed source batch is elsewhere.
Default source: `artifacts/research/retry-20261028-183037/e1`.

To launch all three stages with one Run action, paste the argument from
`workflow-program-argument.txt` into IDE Program arguments. Mode `pareto_workflow`
calls these existing Java methods, sequentially in the same process:

```java
matrix.preflightHeldoutParetoEvaluation();
matrix.runReproducibilityAudit();
matrix.runHeldoutParetoEvaluation();
// Or call the wrapper containing the three calls:
matrix.runParetoWorkflow();
```

Use either the three calls or the wrapper. Preflight may report E0 missing;
the workflow then creates E0 evidence. Audit errors stop the sequence, and the
Pareto stage independently enforces the successful current-build audit gate.
Completed compatible runs are reused by the existing runner. The stages share
one coordinator and worker and must not run concurrently. Keep all configured
input/output paths from the same prepared profile folder.

Start the updated worker in another terminal, from repo root:

```powershell
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_TORCH_THREADS = '1'
.\.venv\Scripts\python.exe -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000 --workers 1
```

Use the generated ONE argument at a time in IDE **Program arguments**, without
surrounding quotes, clearing conflicting old MINIFLS path/database overrides.
Explicit modes bypass the application's manual E0→Phase A→matched-evaluation
sequence. Its default manual sequence remains available.

For standalone CLI, substitute the actual generated folder below:

```powershell
$paretoJar = 'ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar'

# No training: check evidence and report blockers.
java -jar $paretoJar --spring.config.additional-location=file:///D:/research/federated-system/artifacts/research/pareto-<timestamp>/preflight.properties

# If blocked on E0, run this explicitly; it is not launched by the prep script.
java -jar $paretoJar --spring.config.additional-location=file:///D:/research/federated-system/artifacts/research/pareto-<timestamp>/e0.properties

# Only after E0 passes; this is the user's explicit command for all60 runs.
java -Xmx2g -jar $paretoJar --spring.config.additional-location=file:///D:/research/federated-system/artifacts/research/pareto-<timestamp>/pareto.properties
```

Stop the Java server after each stage before starting another against the same
DB. Changing heap size alone does not change classpath content identity. Research
round exports stream to disk, and reports read individual rounds through a byte
index instead of retaining every run's full round history in the Java heap.
One run's round history is still loaded during export; choose a suitable heap for
your machine. Worker CPU/RAM are simulated resources, not container enforcement.

If an older build fails with `OutOfMemoryError` during `runPrepared` export,
the completed database run may still be reusable with that same build and a
larger heap (for example `-Xmx2g` in IDE VM options). Check its status before
resuming. Rebuilding changes `javaBuildHash`: prepare a fresh research workflow
and E0 evidence for the new build rather than bypassing provenance checks or
editing existing evidence.

Alternatively use `MINIFLS_METHOD=pareto_preflight` or `heldout_pareto` with
`MINIFLS_PARETO_CONFIG` and `MINIFLS_PARETO_OUTPUT`. Default output is
`artifacts/research/pareto-tradeoff`; its new E0 is expected under `e0/`.

## Outputs and metrics

At the selected Pareto output root:

- `pareto-tradeoff-config.json` — immutable policies, inherited protocol,
  historical Phase A status/evidence and current runtime identity.
- `pareto-tradeoff-results.json` and `.csv` — all outcomes, metrics/provenance,
  per-partition summaries, paired differences, full fairness/credit/lambda history.
- `pareto-tradeoff-frontier.json` — partition and seed-cell frontiers, dominated,
  nondominated and unassessed policies, cross-partition summaries/consistency.
- `pareto-tradeoff-summary.md` — readable trade-offs and conditional conclusions.
- `pareto-tradeoff-plot-data.csv`, `pareto-tradeoff-trajectory-data.csv`.
- PNG/SVG: Accuracy–Gini, Accuracy–virtual time, Accuracy–tail SD, fairness/Gini
  evolution and applied lambda/smoothed Gini/credit summaries through rounds.
- `pareto/runs/<identity>/`: experiment/rounds/result exports.
- `pareto-preflight.json/.md`, execution manifest and `pareto-completion.json`.

The completion marker is written only after the reports and figures finish.
Initial/per-round evaluation uses proxy; test is evaluated only at the final
checkpoint. Final Accuracy, Macro-F1, Loss and class/worst-class recalls are test
metrics. Last10-round accuracy mean/SD, Macro-F1 tail SD, maximum consecutive
drop, final-round accuracy change and target reach/sustainment use **proxy**.
Tail means never replace final test accuracy; the initial evaluation is excluded
from consecutive-round drops. Unreached targets remain null/censored, not zero.

Population coverage uses all100 clients. RAM-feasible population (normally60)
is distinct from clients with valid feasible opportunities. Feasible selection/
completion coverage, opportunity-adjusted Ginis, staleness and never-selected
counts use the explicitly exported opportunity denominator. Selection fairness
and completion fairness are reported separately. Credits are retained in full;
slots changed use raw TOPSIS Top-K on the same pre-round history.

Large drops are flagged at a predeclared10 percentage-point proxy-trajectory
threshold. All low-final-accuracy and drifting runs stay in results; there is no
best-test-checkpoint replacement or outcome-dependent exclusion.

## Pareto interpretation

Maximize Accuracy, Macro-F1, feasible selection coverage and feasible completion
coverage. Minimize feasible opportunity-adjusted selection Gini, proxy accuracy
tail SD and virtual seconds including measured selector/fairness overhead.
Dominance requires no worse on every objective and strictly better on at least
one. Equal vectors do not dominate each other. No arbitrary epsilon or weighted
score chooses a winner. Missing/nonfinite objectives are **UNASSESSED**, not
automatically nondominated. The2D Accuracy–Gini frontier can be assessed separately
when an unrelated objective is missing; partial-seed averages are not silently
used as complete partition means.

First report means ± sample SD across the five training/scenario seeds within
each partition, alongside P4−P1/P2/P3 paired differences for every cell. Tail SD
is within-run variation, not between-seed SD. Cross-partition summaries are
equal-weight means of partition means, with SD across partition means labelled
descriptive heterogeneity; the15 cells are not declared independent replicates.
Partition-specific frontier status and Adaptive-vs-Fixed dominance relations
show any inconsistency, even when aggregate means appear favorable.

Sample-mean dominance/non-dominance does not establish statistical superiority,
equivalence or generalization. The same historical Covertype train/proxy/test
pools are reused: held-out **partitions** are disjoint from Phase A, not a newly
unseen dataset test pool. Deterministic training-duration rate .0005 remains an
uncalibrated simulation assumption. Wall time and server/selector/fairness
overhead remain measured, so total virtual+selector time is not bitwise fixed.

## Resume, reuse and smoke

Completed identities are skipped only when config/runtime provenance matches.
The identity also includes the locked Pareto protocol hash, keeping P runs separate
from M/L/F results. Original metadata is preserved on reuse. For FAILED/INTERRUPTED
runs, start the same build in API-only mode with `MINIFLS_LAUNCH_ENABLED=false`
and the same DB/worker settings, call `POST /experiments/{id}/resume`, wait for
completion, then rerun the Pareto command. Snapshot/history/credits recover through
the existing path. Uncommitted partial-round checkpoints are not substituted
for committed models. Config/source evidence changes refuse reuse.

```powershell
# Isolated synthetic3-round smoke only, never the60-run Covertype matrix.
.\.venv\Scripts\python.exe scripts/verify_pareto.py
```

The smoke checks the real protocol's E0 blocker without training, runs a small
synthetic E0/pilot, proves NO_MATCH can feed a separate Pareto comparison, injects
one failed round, resumes via SQLite/API, verifies8 held-out smoke runs and reruns
them without duplicate commits. It also verifies the locked policies, reports,
split labels and figures. Smoke evidence cannot certify a real research batch.
