# Controlled fuzzy uncertainty ablation validation

Implementation baseline: main cc201905. Historical result publications are
unchanged. No Covertype pilot or225-run confirmation was started by validation.

## Automated checks

- Java: `ferderatedsystem/gradlew.bat -p ferderatedsystem test bootJar --no-daemon`
  completed successfully: **91 tests, zero failures/errors**. New tests verify
  shared point criteria/feasibility, the same production engine for A1-A4,
  zero-width triangles, deterministic ranking, no mutation of replay inputs,
  history/calibrated widths and an independent manually calculated three-client
  zero-width matrix. Existing conventional Crisp and nondegenerate fuzzy
  numerical tests remain enabled.
- Python: venv pytest over `ml-python/tests`, `scripts/test_fairness_matched.py`,
  `scripts/test_fuzzy_uncertainty.py`, `scripts/test_frozen_e3_resume.py` and
  `scripts/test_controlled_ablation.py`: **53 passed**. One existing
  Starlette/httpx deprecation warning remains. No tests were disabled.
- Both PowerShell launchers parse successfully with the PowerShell language
  parser. `git diff --check` passes. No tracked `results/` file was modified.

## Real isolated Java/PyTorch smoke

Final evidence: `artifacts/controlled-ablation-smoke/142c8a3f17/summary.json`.
**PASS, 38 committed synthetic rounds**: one reduced pilot and one reduced
confirmation, each with five3-round policies and two2-round reproducibility
audits. Synthetic results are implementation checks, not research findings.

The smoke verifies:

- Preflight without training, explicit admission-budget stop and resume.
- Kill the actual coordinator after a committed round; recover interrupted work
  from SQLite without duplicate round commits.
- All five policies, identical paired initialization/partition/scenario identities,
  immutable replay point observations, zero-width A1 and width distributions.
- Pilot proxy-only evaluation; confirmation final-only held-out test evaluation.
- Completed-run reuse without increasing committed-round counts.
- Locked pilot-to-confirmation controls, separate datasets/databases and identities.
- Read-only report regeneration and all ten PNG/SVG figure families.
- Checkpoint byte corruption rejection with restoration of the test fixture;
  incompatible source ledger rejection without relaxing provenance checks.
- Explicit audit/research cohort labels in calibration diagnostics; audit rows are
  excluded from research diagnostics figures and aggregate calibration summaries.
- Historical full-publication manifest bytes remain unchanged.

Read-only `scripts/verify_controlled_batch.py` checks every completed checkpoint/
receipt hash, config/runtime identity, contiguous SQLite rounds, final-only test
splits and pinned offline artifacts. Both final synthetic batches pass.

Additional recovery evidence:
`artifacts/fuzzy-recovery-smoke/97c59d30d9/summary.json`: **PASS**. A real worker
was killed during local training, Java was killed after round1, original request
bytes were preserved on transport retry, no duplicate commits occurred and the
final tensor matched an uninterrupted two-round reference.

Legacy workflow regression:
`artifacts/fuzzy-uncertainty-smoke/ced633e78f/summary.json`: **PASS, 40 synthetic
rounds**, including worker/Java watchdog restart, budget/resume, immutable
pilot-to-full policy lock, completed reuse, final-only test, report-only, NumPy
Crisp reference, paired traces and selector-input future-field checks.

## Failures found and corrected

The first new inventory implementation unnecessarily resolved every artifact
JSON path. Filtering metadata names first avoids that large startup overhead.
A subsequent confirmation smoke exposed that planned `confirmationDesign`
reservations were being counted as already executed assignments. The inventory
now excludes that future-design subtree, with a regression assertion; actual
recorded partition assignments remain checked. Failed/aborted smoke artifacts
were preserved. Later complete smoke reruns passed.

The first invocation of the legacy live-recovery test was interrupted by Windows
Connected Standby (23:25:35 entry,23:30:59 keyboard wake), exceeding its existing
progress deadline. It was rerun unchanged under the existing scoped idle-sleep
guard and passed; no timeout assertion or integrity check was removed. The new
controlled smoke entry point scopes the same idle guard around the whole test.

## Preflight on this machine

Machine-readable reports:
`artifacts/controlled-ablation-preflight/20261103/{pilot,confirmation}/preflight.json`.
Repository-visible inventory found no prior use of5001/5002 or6001/6002/6003.

| Design | Research runs | Research rounds | Conservative full disk estimate |
| --- | --- | --- | --- |
| Pilot | 40 | 2,800 | 17.0 GiB |
| Proposed confirmation | 225 | 15,750 | 56.3 GiB |

Each batch also has two2-round audits. D: had approximately30GiB free during
final preflight. The full confirmation estimate exceeds available space; it is
not accepted or launched automatically. Positive admission budgets permit safe
increments, but do not reduce total accumulated evidence/storage requirements.

Memory planning ranges: coordinator RSS300-900MiB including a512MiB heap;
worker RSS400-2,000MiB, with additional OS/IDE and reclaimable mmap/page-cache
cost. These are planning ranges, not guarantees or measured peak limits.
Training is sequential with one Uvicorn worker and one PyTorch CPU thread.

A bounded100-round sample from the completed Covertype batch had median physical
round time about1.408 seconds, giving approximately1.1/6.2 hours of comparable
training work for the pilot/confirmation. This excludes dataset preparation,
replay/report overhead and future load/sleep/IO changes; it is not a promised
overnight completion time. Matrix counts and conservative disk admission are
checked again by the executing launcher.

## Research readiness and limits

The implementation is ready for an explicitly launched pilot. A1-A4 differ only
in width policy through unchanged scientific scoring/extraction equations.
Reliability retains the audited accepted-given-selected-executed-v1 target.
All five policies are retained regardless of pilot proxy performance. A1-A0
remains formulation-only diagnostic. No full Covertype ablation conclusions
exist yet. Two/three independent partition assignments provide weak inferential
precision, and the underlying fixed test examples have been inspected before.
