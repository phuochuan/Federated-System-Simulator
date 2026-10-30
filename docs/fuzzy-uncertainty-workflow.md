# Fuzzy MCDM uncertainty workflow

The dedicated configuration is `configurations/fuzzy-uncertainty.json`. Launch
the two `scripts/run_fl_research_*.ps1` scripts from the repository root. They
use the existing `.venv` and Java/Gradle installation. No new Python packages
are required beyond the validated environment. Full experiments run sequentially
with one Uvicorn process, one Torch thread, and a 512 MB Java heap.

## Protocol and counts

The scientific target is fuzzy client selection, without fairness credit or
adaptive lambda. C1 is conventional Crisp TOPSIS; C2 is the existing fuzzy
engine with zero-width triangles; C3 uses fixed width; C4 uses the unchanged
history-based width equations; C5 uses past prediction residuals.

All use estimated time (.40 cost), smoothed reliability (.35 benefit) and
previous-loss utility (.25 benefit), the same feasibility rule and ascending
client-ID ties. Conventional Crisp uses column Euclidean normalization,
weighted column extrema as ideals and Euclidean distances across criteria.
Zero columns are uninformative and identical alternatives score .5. The fuzzy
engine uses maximum benefit / reciprocal cost normalization and sums vertex
distances. Its zero-width limit generally differs from conventional Crisp.

The default pilot has 24 E2 runs (4 policies x 3 scenarios x 2 seeds), plus six
C5 runs in E4. E4 reuses C3/C4 validation results. Two additional audit runs of
two rounds test repeatability under the executing Java/Python build before the
pilot. They are labeled separately and excluded from research summaries.

Default training: Covertype, 100 clients, K=5, alpha=.5, validation partition
2001, seeds 42/43, 70 rounds, MLP 54-256-128-7, FedAvg, one epoch, batch32,
LR=.01. Validation uses the proxy split; the test split is never requested
by audit, E2 or E4. Availability/dropout/jitter are .9/.05/.1; RAM requirement
600 MB and deadline 10 seconds match the existing heterogeneous simulator.
Deterministic timing uses .0005 seconds/sample; physical worker timings remain
separate observations. These are simulated device conditions, not calibrated
hardware claims.

U0 adds no observation noise; U1/U2 add bounded relative observation noise of
10%/30%. Independent hash channels generate timing and reliability errors;
neither policy name nor experiment ID enters them. Controls for each channel
are separate. U3 optionally biases a stable 30% subset by +/-20%, with stable
signs. Add U3 to `scenarios` in a **new batch protocol**: that adds eight E2
diagnostic runs and two E4 runs, separately labeled. Fuzzy widths never read
the injection magnitude or future scenario outcomes.

The existing full-population ScenarioTrace generator supplies paired availability,
dropout and jitter events. Trace files are persisted and verified on resume.
Actual measured worker runtime, deterministic simulation input, simulated
effective duration and completion outcomes are exported separately.

## Residual calibration and policy lock

After a round completes, each executed client appends its absolute relative
effective-duration forecast error (denominator max(predicted, 1e-9)) and its
absolute completion-probability error. These bounded windows are committed in
the same snapshot transaction as the round. At selection, C5 uses the nearest-rank
80th percentile of its last 32 errors, requiring at least five past observations.
Otherwise it uses prior .1. Widths are capped at .45. Reliability widths are
absolute; timing widths are relative. Utility retains its .1 prior width
because this protocol does not assert a validated utility prediction target.

These triangles are decision representations, not nominal confidence intervals.
Reports include empirical interval coverage and maturity diagnostics. Sparse,
selected-only histories limit calibration and prevent population-wide claims.
The original `history_based` formulas are preserved.

The predefined validation screen includes C5 in confirmation only when all six
paired C5/C4 validation runs complete, mean final **proxy** accuracy difference
is nonnegative, and at least 50% of executed C5 observations have five prior
residuals. This is screening, not a superiority or significance test. C1 and C4
are always retained. No held-out result contributes to this decision.

`policy-lock.json` and `confirmation-protocol.json` are immutable. Default full
confirmation has 3 alphas x 3 independent partitions x 5 training seeds:
135 runs with C5, or 90 if it is not promoted. Training/model and scenario seeds
are paired across policies. Partitions 3001/3002/3003 are distinct from validation.
Only the final round requests test evaluation. All intermediate trajectories
remain proxy metrics. There is no best-test-checkpoint selection.

## Modes, budgets and resume

Set `mode` in the dedicated JSON to `pilot` (default), `full`, or `report-only`,
then use the same two launcher commands. Mode is excluded from scientific
identity; switching pilot to full preserves the saved validation policy lock.
Changing scientific settings requires a different `MINIFLS_FUZZY_OUTPUT` root.
The scripts deliberately reject a changed protocol or source tree in an active
batch. Completed legacy F/L/E/Pareto evidence is never written by this workflow. Completed checkpoints and receipts acquire immutable byte checksums after final-tensor verification; later reuse verifies those identities. Actual initialized tensor hashes are checked across paired seeds.

`runBudget` and `roundBudget` limit admissions per invocation; zero means no
limit. Budgets reserve all remaining rounds of a run before starting it, so a
budget never interrupts an otherwise healthy round. Environment overrides
`MINIFLS_FUZZY_RUN_BUDGET` and `MINIFLS_FUZZY_ROUND_BUDGET` may be changed on
resume without changing the immutable scientific protocol. `retryBudget` limits
experiment recovery. `readinessSeconds`, `recoverySeconds`, request timeout and
watchdog limits are in the dedicated configuration. Java transport attempts,
backoff and optional jitter also support the existing `MINIFLS_WORKER_*` variables.

`artifacts/research/fuzzy-uncertainty/active-batch.json` points to the uniquely
named batch. Re-running the same commands resumes it. Do not remove the pointer,
database, checkpoints, receipts or manifests to resolve a mismatch. A genuinely
new study uses a fresh output root. Wrapper OS locks prevent simultaneous
workers/coordinators within the workspace; active ports also prevent accidental
duplicates. A copied batch JAR is used for every coordinator restart.

Successful pilot/full completion writes `completion.json` and exits zero.
`status.json` distinguishes `COMPLETED`, `BUDGET_REACHED`, `RETRYABLE_FAILURE`
and `BLOCKED`; budget stops also exit zero and explicitly request resume.
Fatal/provenance/integrity failures exit 20. Transient controller failures exit
75 and may restart within the sliding watchdog budget. Unexpected process
crashes also count toward that budget. A successful workflow is never restarted.

Java's existing checkpoint-producing RPC retries preserve serialized parameters
and operation IDs. The worker's existing request hashes and durable receipts
return the original committed response. Reused IDs with changed parameters and
ambiguous checkpoint-without-receipt states remain fatal. Interrupted rounds
resume from the last SQLite transaction with a fresh attempt ID. Orphan files
are preserved; the workflow performs no automatic checkpoint cleanup.

Runtime identity is checked before run/resume and before checkpoint operations;
a restarted worker must match the original source/dependency/runtime identity.
Only transport failures, 502/503/504 and the exact busy 409 are retryable. A coordinator shutdown interruption of an uncommitted worker request can also resume safely from SQLite.
Other 409, 400, malformed JSON, numerical failures and provenance mismatches
stop. SQLite uses WAL and FULL synchronization. Low disk prevents a batch start;
disk write errors stop safely. A committed-round progress deadline also stops a dead experiment if a SQLite failure prevents its terminal status from being persisted; the controller does not poll RUNNING forever. Watchdogs cannot keep the machine awake, restore
lost power or create disk capacity.

## Evidence and reports

All new reports are in the batch directory. `logs/java.log` and `logs/worker.log`
rotate at 8 MB with five backups. Batch/run state transitions and JSON/CSV
reports use atomic replacement; critical Python writes flush and fsync.

`e0-uncertainty-measurement.*` and `e0-observations.csv` explicitly distinguish
missing outcomes, physical execution and virtual effects. Historical evidence
databases are opened read-only, and only immutable pre-round observations are
used. The default historical path is `artifacts/minifls.db`; adjust the evidence
list **before creating a new batch** if historical data lives elsewhere.

`e1-crisp-fuzzy-ablation.*` and `e1-ranking-comparison.csv` contain a bounded
100-state replay sample at widths 0/.1/.3, using the production engines. Replay
does not train, alter models or advance selection histories. The first ten decision states per E2 run also compare its observed ranking with the U0 ranking of that same saved state in `ranking-robustness-vs-noise.csv`; correlations use common candidates and feasible pool sizes are exported. This is a bounded offline diagnostic. `plot-data-index.json` maps all requested plot axes to CSV columns. Strict rankings
use ID tie breaks; tied coefficient counts are exported. Replay is diagnostic,
not an end-to-end counterfactual estimate.

E2/E4 JSON/CSV/Markdown, E3 results and `fuzzy-mcdm-research-summary.md` preserve
actual outcomes and incomplete status. `accuracy-vs-rounds.csv` includes proxy
accuracy, loss, Macro-F1, virtual time and opportunity Gini. Final result CSVs
include noise level, partition identity, stability and per-class recall. Sample
SD/ranges are descriptive; correlated seeds within a partition are not treated
as independent partition replicates. No conclusion claiming superiority is
automatically generated.

## Validation commands

Java: `ferderatedsystem/gradlew.bat -p ferderatedsystem test bootJar --no-daemon`.
Python: `.venv/Scripts/python.exe -m pytest ml-python/tests scripts/test_fairness_matched.py scripts/test_fuzzy_uncertainty.py -q`.
Workflow smoke: `.venv/Scripts/python.exe scripts/verify_fuzzy_uncertainty.py`.
Existing receipt fault injection: `.venv/Scripts/python.exe scripts/verify_worker_retry.py`.
Existing fuzzy lifecycle/resume integration: `.venv/Scripts/python.exe scripts/verify_fuzzy.py`.
Smoke outputs are synthetic and separate from research evidence.
