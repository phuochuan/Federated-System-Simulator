# Java E0 / E1 experiments

Entry points are in `ControlledExperiments`: `runReproducibilityAudit()`,
`runFairnessMatchedValidation()` and `runFairnessMatchedEvaluation()`.
`ResearchExperiments` orchestrates them through the existing `runPrepared`,
`RoundCoordinator`, SQLite repository and `RunResult` export path. F1–F5 and
L0–L5 keep their existing configurations/default measured-duration behavior.
The earlier Python `fairness_matched.py` runner is a legacy prototype; use these
Java modes for the protocol below.

## Run commands

Build once from the repository root, then keep that JAR and the Python environment
unchanged across E0, Phase A and Phase B:

```powershell
Push-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Pop-Location
.\.venv\Scripts\python.exe -m pytest ml-python/tests scripts/test_fairness_matched.py -q
```

Start one worker in its own terminal:

```powershell
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_TORCH_THREADS = '1'
.\.venv\Scripts\python.exe -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000 --workers 1
```

Run each stage separately in the Java terminal, from the repo root:

```powershell
$env:MINIFLS_WORKSPACE = (Get-Location).Path
$env:MINIFLS_WORKER_URL = 'http://127.0.0.1:8000'
$env:MINIFLS_DATABASE = Join-Path $env:MINIFLS_WORKSPACE 'artifacts/research.db'

# E0: 3 repeats × 2 policies × 2 duration modes = 12 runs / 840 rounds.
$env:MINIFLS_METHOD = 'reproducibility_audit'
$env:MINIFLS_AUDIT_CONFIG = 'configurations/reproducibility-audit.json'
$env:MINIFLS_RESEARCH_OUTPUT = 'artifacts/research/reproducibility-audit'
java -jar ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar

# After the report is written, stop that Java server before starting the next one.
# Phase A: 7 policies × 2 partitions × 3 training/scenario seeds = 42 runs.
$env:MINIFLS_METHOD = 'fairness_matched_validation'
$env:MINIFLS_MATCHED_CONFIG = 'configurations/fairness-matched-lambda.json'
$env:MINIFLS_RESEARCH_OUTPUT = 'artifacts/research/fairness-matched'
java -jar ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar

# Phase B: the locked fixed policy and M7, 3 NEW partitions × 5 seeds = 30 runs.
$env:MINIFLS_METHOD = 'fairness_matched_evaluation'
java -jar ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar
```

Java remains an HTTP server after the batch completes. Do not start another
coordinator against the same SQLite file while it is running. Using the identical
JAR for every stage avoids a `bootRun`/JAR classpath identity mismatch. If runtime
or protocol changes, choose a new output directory and rerun E0 for that build.
When changing E0 output, update E1's `auditReportPath` before creating its batch.
No round-count environment override applies to these new research protocols;
smoke requires an explicit config with `smoke:true`.

## E0 audit

Fixed λ=.7 and Adaptive initial λ=.3 use the current Non-IID manifest, seed45,
same training configuration and the same full-population exogenous scenario.
Three repetitions are run serially per policy in each of two separate modes.
Services are shared inside a Java batch; JVM/worker warmup is not silently treated
as controlled physical timing. A new snapshot owns each experiment's history,
credit and controller state.

Metadata includes actual Java executable/classpath content hash, Java version,
Git commit/status/diff hash, normalized config hash, Python/package versions,
CPU execution device, torch thread/determinism settings and Python source hashes.
`/runtime` rejects stale source files changed after worker import. Metadata is in
the persisted config and snapshot as well as exported reports. Dataset files are
checksum-verified at initialization/resume and after execution/reuse; manifests,
initial tensors and scenario hashes are retained.

`reproducibility-audit.json` and `.md` report pairwise first divergence for:
ordered selection, selected set, global tensor state, learning/fairness metrics,
lambda/credits, timing estimates, duration inputs and saved histories. Equal
base tensor/client/round-seed local updates are compared separately. History,
credit/controller state and timing estimates are replayed from saved events.
Missing model hashes are insufficient evidence, not an assumption of equality.
Different initial tensors or different tensors under equal training inputs are
reported and block the deterministic E1 gate; E0 does not abort solely because
the diagnostic observes a different model hash.

`timing.mode` defaults to measured when omitted. The explicit deterministic mode
uses `samples × epochs × secondsPerSample` before one CPU division and trace
jitter. The default research rate .0005 matches the existing cold-start prior;
it is a declared simulation assumption, **not hardware calibration**.
Measured `actualTrainingMs` is retained alongside `durationInputMs`. Only the
latter drives simulation and subsequent estimates in deterministic mode.

Deterministic replay covers decisions, local/global tensor hashes and learning
metrics on the tested runtime. Server/selector/fairness/evaluation overhead, RSS
and wall time remain physical measurements. `virtualSeconds` still includes
measured server overhead; the version with selector adds measured selector and
fairness overhead. Thus neither total virtual-time metric is promised bitwise
repeatable. E0 can identify timing-sensitive trajectories, but a pass is not a
proof of correctness or cross-platform/PyTorch-version reproducibility.

## E1: fairness-only matching and immutable lock

The config reuses `lambda-ablation.json`'s base/scenario/fuzzy settings. M1–M6
are fixed .60/.625/.65/.675/.70/.725; M7 is Adaptive initial .30. Engine,
uncertainty, normalization, credit recurrence, FedAvg, architecture, training,
100 clients and K=5 are shared. The main E1 protocol is deterministic duration;
measured-duration sensitivity belongs in a separate protocol/batch.

Partition RNG is independent of split seed42 and training/scenario seed.
Phase A prepares partitions1001/1002 and trains seeds42/43/44. Phase B prepares
partitions2001/2002/2003 and trains seeds42–46. Features, train/proxy/test pools
and scaler hashes must match across partitions. Manifests store `partitionSeed`
explicitly. Old manifests without it retain their existing semantics; reports
identify the original partition RNG as data seed+2. New partitions are held out;
this is not a claim of a completely new, historically untouched Covertype test
dataset.

Phase A performs initial and per-round evaluation only on proxy validation rows,
which are disjoint from training and test rows. It does not call test evaluation.
Policy selection reads **fairness only**, never Accuracy/Macro-F1/Loss:

| Comparison | Config tolerance | Aggregation of absolute paired gaps |
| --- | ---: | --- |
| Feasible selection coverage | .02 | maximum across partition/seed cells |
| Feasible completion coverage | .02 | maximum across cells |
| Feasible selection/opportunity Gini | .025 | mean across cells |
| Feasible completion/opportunity Gini | .05 | mean across cells |
| Max feasible selection staleness | 5 rounds | mean across cells |
| Mean feasible selection staleness | 2 rounds | mean across cells |

Observed feasible opportunity populations must have identical membership in each
pair. Every tolerance must pass. Among qualified fixed policies, minimize mean
absolute paired selection-Gini difference; break ties with smaller λ. Opposite
Gini deviations never cancel. These are operational tolerances, not a statistical
equivalence test. If none pass, export every gap and `NO_MATCH`; Phase B refuses
to run. A wider grid or new tolerances require a new exploratory protocol/output.

Phase A writes immutable `policy-lock.json`: selected fixed policy, all Adaptive
settings, complete protocol, runtime identity, Phase A report hash and lock content
hash. Phase B validates that evidence and those hashes before training; manual
policy/hyperparameter edits are rejected. It never retunes using held-out scores.
Recheck fairness on held-out results; if tolerance fails there, report a trade-off,
not a fairness-matched learning advantage. Keep all final checkpoints/outcomes,
including drift and low accuracy.

Phase B uses proxy for initial/per-round trajectories and calls test **only on
the final checkpoint of each run**. Final Accuracy/F1/Loss/recalls are test results;
tail mean/SD, maximum drop and time-to-target are explicitly labelled **proxy**
trajectory diagnostics. This avoids test feedback and mixed-split tail statistics.
The existing F/L modes still evaluate their original configured/default split.

## Reports, denominators, reuse and recovery

Each phase exports:

- `fairness-matched-summary.md` with descriptive mean ± sample SD, stability,
  paired differences, matching status and Pareto analysis.
- `fairness-matched-results.csv` and `.json`, including per-class recalls,
  target reach/sustainment, provenance and every required metric.
- Standalone PNG/SVG figures: `accuracy-gini-pareto`, `learning-stability`,
  `fairness-evolution`, `adaptive-behavior`. Plotting reads exported evidence only.
- `runs/<identity>/experiment.json`, `rounds.json`, `result.json`; SQLite retains
  the complete committed state for resume.

Summaries keep training/scenario seeds within each partition. Within-run tail SD
(last min(10,rounds) observations) is separate from between-seed sample SD (n−1).
Fewer than two observations yield N/A. Per-partition min final Accuracy supplies
the worst-case diagnostic. Paired differences are Adaptive−Fixed for each seed
and partition; no significance, equivalence or superiority claim is automatic.

Population coverage/never-selected counts use all100 clients. Static RAM-feasible
denominator is normally60; observed feasible opportunity denominator is exported
separately and can depend on policy. Selection/completion coverage and Gini are
distinct; completion Gini is reported for population, RAM-feasible population and
feasible completion/opportunity rates. Full credit distributions, applied lambda,
smoothed Gini and slots changed against raw TOPSIS on the same pre-round state
are retained in trajectory JSON.

Stable run identity incorporates normalized config, phase/replicate and runtime
content identity. Completed runs are reused only with matching config/runtime;
original Git/launch metadata is preserved. A conflicting immutable batch or lock
fails instead of overwriting it. Interrupted/failed runs are not resubmitted:
start the same JAR in API-only mode (`MINIFLS_METHOD=none`) with the same worker/DB,
resume using `POST /experiments/{id}/resume`, wait for completion, then rerun the
same batch command. Snapshot/history/credits are restored by the existing path.
Runtime, partition or scenario changes cause research resume to fail.

`STOP` in the research output prevents the next experiment from starting; the
currently active Java experiment finishes its committed run. Ctrl+C terminates
the coordinator; on next startup SQLite marks an in-flight run `INTERRUPTED`.
No source changes, resets, deletions or best-test-checkpoint substitutions occur.

## Small integration smoke

```powershell
.\.venv\Scripts\python.exe scripts/verify_research.py
```

This uses synthetic data, 3 rounds, isolated ports/database/output, 12 E0 runs,
completed-run reuse, 14 Phase A runs and 6 Phase B runs. Matching tolerances are
deliberately relaxed **only in the smoke config** to exercise both stages. It is
implementation evidence and cannot be used as research evidence or unlock a real
E1 protocol. The full Covertype matrices are user-run.
