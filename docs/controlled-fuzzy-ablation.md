# Controlled fuzzy uncertainty ablation

The requested **manual Uvicorn + IntelliJ, full225-run study without a separate
Covertype pilot** is documented in [the full IntelliJ guide](intellij-controlled-ablation-full.md).
Select **Controlled Fuzzy Ablation Full**. It uses a distinct explicit protocol
and full-policy lock; the staged pilot/confirmation workflow below remains available.

Read the [pre-implementation audit](controlled-fuzzy-ablation-audit.md).
Protocol version: `controlled-fuzzy-width-v1`. Historical publications, policy
locks and runtime identities are not modified by this study.

## Question and treatment

Does nonzero TFN uncertainty improve client selection over its own deterministic
limit? A1 is the primary control. A0 is a conventional TOPSIS reference whose
normalization/distance differ; A1-A0 measures formulation differences.

| Policy | Production selector | Width |
| --- | --- | --- |
| A0 | CrispTopsisEngine | zero (middle values only) |
| A1 | FuzzyTopsisEngine | exactly zero |
| A2 | FuzzyTopsisEngine | fixed .1 |
| A3 | FuzzyTopsisEngine | unchanged history_based |
| A4 | FuzzyTopsisEngine | unchanged error_calibrated |

All use shared extraction, .40 time cost/.35 reliability benefit/.25 previous-loss
utility benefit weights, identical availability/RAM/deadline filtering and integer
ID ties. Pure `fuzzy_topsis` disables credit/adaptive lambda. Widths change TFNs,
their normalization, ideals and distances through the same unchanged formulas.
Time width is relative; benefits use absolute width with [0,1] clipping. A4 uses
nearest-rank q=.8, window32, minimum5, prior.1, cap.45. Utility keeps prior.1.
No policy sees injected-noise magnitude, future outcomes or held-out scores.

`criterionUncertaintyWidths` records actual requested/capped widths before endpoint
clipping. TFN endpoints are recorded separately. Observations, profiles, counts
and residuals are snapshotted before each selection. End-to-end selection histories
may diverge; their influence on later criteria/feasibility is part of the treatment.

Reliability means **accepted given selected and executed**, with Beta(1,1).
Denominator and binary calibration label align on committed executed clients;
there was no target-definition correction. Worker success, simulated completion,
dropout, deadline rejection and server acceptance remain distinguishable. No
unselected/missing outcome is assigned a negative label.

## Matrices and evaluation

| Stage | Alphas | Partition seeds | Training seeds | Research runs | Rounds |
| --- | --- | --- | --- | --- | --- |
| Pilot | .1,.5 | 5001,5002 | 42,43 | 40 | 2,800 |
| Proposed confirmation | .1,.5,1 | 6001,6002,6003 | 42-46 | 225 | 15,750 |

Each batch adds two 2-round executing-build reproducibility audits, separately
labeled and excluded from research comparisons: pilot totals42 runs/2,804 rounds,
confirmation227 runs/15,754 rounds. Default U0 retains availability.9, dropout.05
and jitter.1; it is not a noise-robustness matrix. Observation controls/noise
definitions are identical across the five policies. Changing scenario requires
a separate immutable batch/config and corresponding pilot/confirmation lock.

Training: Covertype, 100 clients, K5, 70 rounds, MLP54-256-128-7, FedAvg,
epoch1, batch32, LR.01; splitSeed42; sequential local training; deterministic
virtual duration .0005 seconds/sample. Data preprocessing fits scaler on train.
Pilot evaluation is proxy-only, including its final checkpoints. Confirmation
uses proxy trajectories and test only at the final round. No best-test checkpoint
is selected. Pilot is implementation/diagnostic screening; all five policies are
retained regardless of the direction of proxy effects.

New partition seeds are checked against recorded repository manifests/protocols/
configs before batch creation and inventory is preserved in partition-reservation.json.
The inventory has repository-visible scope; users must disclose assignments made
outside this workspace. Split seed stays fixed: new client assignments reuse
previously inspected train/proxy/test pools. They are not untouched test examples.

## Primary startup commands (repository root, Windows PowerShell)

First start Java; its readiness wait allows up to600 seconds for the worker.
Then start Python in the second terminal. Stop prior services using the same ports
before starting these dedicated launchers. Workspace locks reject duplicates.

Command 1 - Java coordinator and study controller:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_controlled_fuzzy_java.ps1
```

Command 2 - Python worker:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_controlled_fuzzy_worker.ps1
```

The default is pilot with **one run admission and70 round reservation per invocation**.
The first two admissions are the separate 2-round audits, so the first two launches
can stop before research training. Repeating the same commands reuses committed
work. Choose a larger explicit budget when desired; no source editing is needed.

## Preflight, stages and budgets

Java options:

- `-Mode preflight`: resource/matrix/reservation report only; no worker needed,
  no datasets/model training. It builds/pins the Java JAR and source identity.
- `-RunBudget N -RoundBudget M`: admission limits, including audits. Zero removes
  that limit for pilot. Remaining rounds are reserved before admission; healthy
  runs are not interrupted mid-round to meet a budget. Example overnight pilot:
  append `-RunBudget 5 -RoundBudget 350` to the Java command.
- `-Stage confirmation`: selects the dedicated confirmation config and output
  pointer. Apply the same stage option to the worker command.
- `-AcceptConfirmation`: mandatory only for confirmation training, after reviewing
  pilot diagnostics and confirmation preflight. A positive run/round budget is also
  required. There is no automatic full225-run launch.
- `-Mode report-only`: disk-only report/plot generation with no worker or training.
- `-OutputRoot <workspace-relative-path>`: new batch family; use the same root in
  both terminals. Do not point it at a legacy output. Custom confirmation roots
  must still reference the intended completed pilot via `pilotPointer` in their
  config before that batch is created.

Pilot and confirmation configs live in `configurations/controlled-fuzzy-ablation-*.json`.
Parameters are immutable after creating a batch. To change scientific settings,
use a new output root and a versioned design. Confirmation verifies the completed
pilot's scientific controls, original source/runtime, all-five policy lock and
predeclared alpha/partition/seed axes. It does not tune on held-out outcomes.

Preflight v2 estimates checkpoint/receipt/evidence storage as2.02MB per research
round at K5, plus160MiB per dataset partition,256MiB report/build/log allowance,
four audit rounds and the8GiB free-space reserve. Measured maxima from the prior
completed study justify300KB per checkpoint/receipt and220KB per SQLite round.
It reports full-matrix and current-admission estimates separately. Approximate
runtime uses a bounded sample of actual recent physical round times, with sample
count and limitations. Memory remains one Uvicorn, torchThreads1, Java heap512MiB
plus Python/OS/IDE. Paging does not replace adequate physical memory. Smaller
admission budgets do not reduce the final accumulated storage requirement.

## Offline replay

Before research training, sample up to100 immutable pre-round decision states,
stratified by row order across the completed evidence database. Replay all five
on identical profiles/history and assert identical point criteria. Persist the
actual replay inputs, scores/TFNs/widths/counts, Spearman score rank correlation,
Kendall tau-b, top-K overlap/Jaccard/changed clients, mean score differences and
selector time. Undefined correlations are null. Width sensitivity uses
0/.05/.1/.2/.3/.45 through A2 against A1 on the same states. Selection-change
frequencies are in offline-summary.json. Replay artifacts are checksum pinned
and reused; corruption fails closed. This is decision evidence, not FL outcomes.

Selector timings are physical diagnostic measurements, affected by JVM warmup,
fixed replay order and machine load; they are not a randomized microbenchmark.

## Recovery and integrity

Reuses research_watchdog, Workflow/FrozenE3Controller admission/completion checks,
the original Java coordinator/repository transactions and Python idempotent
receipts. The copied JAR remains immutable throughout each batch. Source/runtime
and dataset identities are checked; recognized transport failures and exact
checkpoint recovery-budget errors have bounded recovery. Interrupted snapshots
are checked against contiguous SQLite commits and actual worker tensor hashes
before resume. A fresh attempt reexecutes only the uncommitted round; orphan
artifacts are retained. Conflicting requests, corrupt checkpoints, incompatible
runtime/protocol and scientific errors stop instead of bypassing checks.

Watchdogs preserve a sliding restart budget, reject occupied service ports and
never restart completed workflows. Idle-sleep inhibition is scoped to the active
controller; manual sleep, power loss and disk exhaustion cannot be repaired by
HTTP retry. Do not delete checkpoints/SQLite/pointers to fix an integrity failure.
Graceful/abrupt coordinator stops resume from the last committed snapshot.

Output pointers:
`artifacts/research/controlled-fuzzy-ablation/{pilot,confirmation}/active-batch.json`.
Unique batch folders contain status.json, logs/, experiments.db, source/build/
runtime identities, traces, datasets and final checkpoint identities. Global/local
checkpoints use existing `artifacts/models/ca-*` paths. Repeat the same two commands
with the same stage/options to resume. Completed-run reuse verifies final artifacts.

Verify **completion.json status COMPLETED**, status.json workflowStatus COMPLETED,
and integrity-report.json passed=true with40/225 completed research runs (plus
the two audit runs), no failed/pending runs. BUDGET_REACHED is a deliberate stop,
not full completion; BLOCKED requires inspecting lastError. Report-only sets
REPORT_ONLY_COMPLETED without asserting that training is complete. No incomplete
study gets a pilot-validation-lock.json or confirmation completion marker.

For a read-only checksum/SQLite/evaluation verification, run the venv Python with
`scripts/verify_controlled_batch.py <batch-folder>`. It verifies frozen source/JAR,
every completed checkpoint/receipt byte hash, round continuity, final-only test
splits and offline evidence checksums. It does not train or require a worker.

## Reports and interpretation

`controlled-fuzzy-ablation-report.md` includes the required question section and
actual positive/negative/tied paired effects. JSON/CSV preserve learning quality,
per-class/minority recall, proxy trajectories/tail SD/maximum drawdown/target
rounds, fairness/selection counts/coverage/staleness, deadline/completion rates,
virtual time, physical time and selector overhead. Minority classes are the two
least frequent training classes, defined without test performance.

Primary: A2-A1, A3-A1, A4-A1. Secondary: A3-A2 and A4-A3. A1-A0 is formulation
diagnostic. Pair by alpha, partition, training seed and scenario. Seed repeats and
alpha variants sharing a partition seed are conservatively clustered. Report
run-pair mean/median/SD and counts, then per-partition means and standardized
partition effects. Exploratory Student-t intervals use independent partition
means only with >=3 partitions; three clusters are weak evidence and normality
is unverified. No seed-level significance or automatic superiority conclusion.

Calibration CSV/JSON separate physical duration, simulated effective duration,
signed/relative prediction error, selected-only Brier/calibration bins, width,
history maturity, caps and empirical TFN support coverage. Coverage is not a
nominal confidence statement. Failed/partial configurations remain visible.

`figures/` contains PNG and SVG for all ten requested views. Standalone plotting:
use `scripts/controlled_ablation_plots.py <batch-folder>` with the repository venv.
It reads only CSV, and empty evidence is explicitly labeled.

## Verification

Run Java `test bootJar`, Python pytest including `scripts/test_controlled_ablation.py`,
and `scripts/verify_controlled_ablation.py` in the existing validated environment.
The latter uses synthetic data/private ports and tests preflight, audit budget,
Java crash/resume, completed reuse, paired identities, final-only test, source
rejection, reports and figures. Existing `verify_fuzzy_recovery.py` tests worker
death during training, Java interruption and equality to uninterrupted reference.
Smoke evidence is not a Covertype research result.
