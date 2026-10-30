# Fuzzy uncertainty pipeline implementation validation — 31 October 2026

This is implementation evidence, using synthetic data. No complete Covertype
E2 or E3 matrix was run, and no algorithm superiority claim is supported.
The working tree is modified; each launch captures content identities rather
than identifying this work solely by its parent Git commit.

## Checks

- Java: 85 unit/integration tests pass, including conventional Crisp against an
  independent scalar reference, the distinct zero-width fuzzy formula,
  deterministic observation noise, stable bias subsets, bounded residual
  quantiles, worker runtime mismatch on retry, atomic snapshots and legacy modes.
- Python: 32 tests pass (existing worker/data/idempotency/receipt tests, existing
  fairness analytics and nine workflow tests). One existing Starlette/httpx
  deprecation warning remains. No tests were disabled.
- Both PowerShell entrypoints pass the PowerShell parser.
- Real workflow smoke passes budget resume, automatic worker watchdog restart,
  automatic Java crash/round recovery, immutable pilot-to-full policy lock,
  completed-run reuse, report-only generation, NumPy Crisp score verification,
  identical paired scenario traces and final-round-only test evaluation.
- A separate real recovery test kills Python inside local training, then Java
  after round 1 commits. Round 1 remains byte-for-byte identical in SQLite;
  resume completes round 2 with no duplicate commit and the same final tensor
  hash as an uninterrupted reference.
- The existing lost-successful-response test passes: the same operation ID and
  serialized request return the original checkpoint response/actual duration.
- Existing F1–F5 and L0–L5 synthetic matrix, numerical/credit replay and live
  process resume checks pass. Legacy E0/E1 research and Pareto gate/resume/reuse
  smoke tests pass with their own new isolated output folders.

## Local evidence

These ignored artifacts remain on disk; they are not research result archives.

| Check | Evidence directory |
| --- | --- |
| Workflow including automatic process faults | `artifacts/fuzzy-uncertainty-smoke/2fbf1b9817` |
| Workflow final report completion status | `artifacts/fuzzy-uncertainty-smoke/fbd12ca975` |
| Completed checkpoint/receipt identity verification and strict retry classification | `artifacts/fuzzy-uncertainty-smoke/87cb4176b1` |
| Final source, progress deadline and completed-artifact checks | `artifacts/fuzzy-uncertainty-smoke/443a522456` |
| Worker and Java killed during an experiment | `artifacts/fuzzy-recovery-smoke/61c404adc7` |
| Lost successful training response | `artifacts/worker-retry-smoke/06ad211036` |
| F1–F5 | `artifacts/fuzzy-smoke/2023d6cf7b` |
| L0–L5 | `artifacts/lambda-smoke/7e45ae07c2` |
| Legacy E0/E1 | `artifacts/research-smoke/47009650bb` |
| Legacy Pareto | `artifacts/pareto-smoke/9649f45a4e` |

Earlier development smoke attempts exposed and led to fixes for Windows lock
reads, transient atomic-replacement denial, stale budget status on restart,
retry log prefix compatibility, and the legacy smoke's missing API-only startup
flag. Their incomplete artifacts were preserved. Provenance failures were not
bypassed or rewritten. Existing published F/L/E/Pareto evidence was not modified.

## Operational limit on this machine

At validation time D: had about 5.6 GiB free. The production default requires
8 GiB before admission and estimates additional storage for budgeted held-out
confirmation. Thus the production launch currently stops safely for insufficient
disk. No research outputs or resumable checkpoints were removed to make it start.
Full confirmation retains many immutable checkpoints and needs substantially
more capacity than the pilot; use an admission budget and retain the same batch
identity across nights.

Watchdogs and HTTP retries cannot recover from lost disk capacity, sleeping or
powered-off hardware, or an incompatible build/runtime. An ambiguous checkpoint
without a receipt remains an explicit integrity blocker.
