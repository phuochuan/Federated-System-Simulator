# Separate generalization and uncertainty robustness studies

Agreed sequence: 2 November 2026. This document is a research/operations plan;
it changes no executable source, active configuration, policy lock or batch
protocol. The robustness study is not yet configured, locked or executed.

## 1. Finish and freeze the existing E3

Active batch:
`artifacts/research/fuzzy-uncertainty/fuzzy-uncertainty-20261031-004757-b6b730`.

Keep its original source, copied coordinator JAR, runtime identity, datasets,
scenario traces and policy lock. Confirm C1/C4/C5 across alpha .1/.5/1.0,
partition seeds 3001/3002/3003 and training seeds 42/43/44/45/46, under U0.
This is **135 runs x 70 rounds = 9,450 E3 rounds**. The already completed
pilot/audit contributes another 32 runs and 2,104 rounds; reuse those records.

E3 evaluates generalization across Non-IID levels and independent client
partitions in the absence of *additional observation noise*. U0 retains the
original availability, dropout and timing-jitter simulation; it does not assert
perfect predictions or an absence of stochastic outcomes.

Training trajectories remain proxy-only. Final held-out metrics come from the
last committed round, never a checkpoint chosen by its test performance. Do not
change criteria, reliability calculations, widths or calibration settings while
this study is incomplete. Do not use its held-out scores to choose a new policy
or tune the following study.

### Verified resume state on 2 November 2026

- Eight E3 runs completed; the ninth has 62 committed rounds. Remaining E3 work:
  eight rounds of that run plus 126 untouched runs, **8,828 rounds** in total.
- No coordinator/worker was running when checked. The saved `RUNNING` marker
  was stale; its last update was approximately 58 hours old.
- All 66 recorded source-file hashes match; the copied JAR and installed worker
  package versions match the saved identities.
- The round-62 checkpoint and receipt exist; its tensor hash matches the
  committed metric. SQLite rounds are contiguous and match their snapshots.
- Observed E3 evaluation splits match the original proxy/final-test protocol.
- D: had 42.6 GiB free, versus the existing admission estimate of about
  18.79 GiB for the unfinished matrix. No deletion or guard reduction is needed.

Restart using the existing two PowerShell launchers. On coordinator restart,
the repository marks the interrupted run accordingly and resumes its last
committed snapshot. Round 63 must be executed as uncommitted work; an orphan
round-63 artifact is not permission to advance the authoritative checkpoint.
Run and round budgets may be supplied through the existing
`MINIFLS_FUZZY_RUN_BUDGET` / `MINIFLS_FUZZY_ROUND_BUDGET` environment overrides.
Leave the immutable batch protocol unchanged. Zero means no admission limit.

### Completion and freeze gate

Before changing source for stage 2:

1. Verify all 135 E3 runs are completed and have 70 unique, contiguous round
   commits, totaling 9,450 E3 rounds and 11,554 whole-workflow rounds.
2. Verify all completed-run identities, paired model/scenario seeds, independent
   partition identities, final checkpoints/receipts and evaluation splits.
3. Generate final reports, paired comparisons, per-alpha/per-partition summaries
   and anomalies. Report actual outcomes without an automatic superiority claim.
4. Freeze the original reports, protocol, policy lock, traces, runtime/source/build
   identities, final checkpoint identities and a consistent SQLite backup. Record
   publication checksums; preserve previous publications instead of replacing
   them. A completion/freeze marker may be issued only after these checks pass.

Recorded identities at the resume inspection:

| Artifact | SHA-256 |
| --- | --- |
| `protocol.json` | `8ddd72e2ffbe9f1ae4490c5fc7ef0935e1035c9d023221d1e5a08c2243c9d711` |
| `policy-lock.json` | `b49abb53512a77e42036c093834760925561b95b4875cc1c9f15dfea42273bde` |
| `build-identity.json` | `876c4545d380f03a290b60310003a6839b4bb9775a9394eb369aed312d16028e` |
| `runtime-identity.json` | `cfea5d06cb3a1a95537ec4c4cc7c7f67fac4575d3b5962631180b82786a86c66` |
| `source-identity.json` | `77f769f55cce1c638f502dffd4a2db7ca25d9dc8c65eff7bb4eec751578b879f` |

## 2. A new uncertainty robustness batch after the freeze

Use a distinct batch/output/database identity and a new executing-build audit.
Keep the historical E3 reports and protocol unchanged. Compare the fixed policy
set C1/C4/C5 under U0/U1/U2 with identical paired exogenous traces, initialization
and training seeds. All three policies must receive the same observable inputs
and criterion definitions; none receives the true injected noise or future
completion information as privileged knowledge.

Reserve partitions that were not used to choose methods or tune settings. Seeds
4001/4002/4003 are a proposed new family, subject to verifying their manifests and
non-use before locking. New partition identities describe new client assignments,
not automatically disjoint underlying Covertype examples; report that distinction.
Finalize and print the matrix and resource budget before execution. If the study
repeats all three alpha levels, three partitions and five training seeds from E3,
its additional three observation scenarios produce **405 runs / 28,350 rounds**.
This is a prospective count, not an approved or completed robustness matrix.

### Reliability correction and calibration diagnostics

Audit the existing implementation before defining the replacement:

- Define the reliability prediction target explicitly. Distinguish worker
  execution, simulated completion, deadline success and server acceptance.
- Align labels and denominators with that target. Only executed clients have
  observed outcomes; unavailable, unselected and missing observations must not
  silently become negative labels. Preserve selection-bias limitations.
- Separate observable noisy probability, prior/history estimate and the outcome.
  Preserve the exact prediction made before selection for every scored outcome.
- Apply the corrected criterion consistently to C1/C4/C5 and version the
  definition. A corrected reliability study is a new protocol, not a rewrite of
  E3 or a directly interchangeable continuation of its results.
- Report Brier score and reliability-bin calibration with sample counts and
  explicit cohort/scenario/partition grouping, including sparse/missing evidence.
- Separate duration prediction residuals, injected observation errors, simulation
  jitter and physical worker execution. Define relative-error denominators.
- Report widths, pre-round residual-history counts, cold-start/prior use,
  clipping/capping frequency, signed bias, residual quantiles, empirical interval
  coverage and interval widths. A fuzzy membership interval does not become a
  nominal probabilistic confidence interval merely because coverage is measured.
- Diagnose timing uncertainty and reliability uncertainty separately. Use past
  observations only; fit/tune any new calibration choice on validation, then lock
  it before confirmation. Do not tune on either frozen E3 test scores or the
  robustness batch's held-out scores.

Keep offline decision replay separate from end-to-end FL evidence. Publish both
generalization and robustness results with their own identities, scopes and
limitations; do not pool runs from the different protocols as interchangeable
replicates or treat seed repeats within one partition as independent partitions.
