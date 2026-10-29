# Java E0 / E1 implementation validation — 27 October 2026

No full Covertype matrix was run for this implementation task. All live checks
below use synthetic data and isolated databases/ports. Existing uncommitted
changes were retained; Git metadata records a dirty working tree.

## Checks

- `gradlew.bat test bootJar --no-daemon`: **56 Java tests pass**. Coverage includes
  legacy F/L configuration/reporting, snapshot/resume, deterministic timing,
  fairness matching, immutable provenance/lock validation, completed-run reuse,
  first-divergence reporting and conditional repeated-run sample SD.
- `python -m pytest ml-python/tests scripts/test_fairness_matched.py -q`:
  **21 Python tests pass**. One existing FastAPI/Starlette TestClient deprecation
  warning remains. Tests cover unchanged local tensor state, explicit hashes,
  duration isolation/CPU scaling, partition/split seed separation, runtime metadata,
  immutable partition preparation and fairness-only matching.
- `python scripts/verify_research.py`: **PASS**, actual Spring HTTP + PyTorch +
  SimPy + SQLite. Evidence: `artifacts/research-smoke/20c2129171/`.
- Existing `python scripts/verify_fuzzy.py --lambda-ablation`: **PASS**, 12 L0–L5
  experiments ×3 rounds, seeds42/43, independent numerical/credit replay and live
  restart/resume through round12. Evidence: `artifacts/lambda-smoke/028e5b5482/`;
  report: `artifacts/comparisons/20261027-193806-e45cc78f/L-fixed-lambda-ablation.txt`.

## Java E0/E1 smoke evidence

Final research smoke runtime Java content identity:
`d5d118be6d84148f0797dbde6b5303858e878d35519d2f57202cbee92fa56696`.
The runtime identity combines the executing application/classpath file hashes;
it is not simply the outer JAR file SHA-256. Python versions, CPU device, thread
settings and package source hashes are in the E0 JSON metadata.

E0 completed12 runs: fixed .7 / adaptive .3 ×3 repetitions ×2 duration modes,
seed45, 3 rounds each. All six deterministic pairwise comparisons have exactly
equal decisions, tensors and learning metrics. Saved history/credit/controller/
timing replay passes for every run. Measured-duration comparisons expose timing
divergence while equal-input local tensor updates still match. Repeated-run
summary groups each have n=3 and sample SD (n−1); deterministic accuracy SD=0
in this smoke only. This does not establish 70-round or cross-platform determinism.

The same E0 launch was repeated against the same SQLite database. Experiment
and committed-round counts remained unchanged, verifying completed-run reuse
with matching identity and provenance.

Phase A completed14 runs: M1–M7, two partition seeds, one training/scenario seed,
3 rounds. Phase B completed6 runs: locked fixed policy plus M7, three held-out
partition seeds, one training/scenario seed, 3 rounds. Smoke-only fairness
tolerances are deliberately widened to exercise lock creation and evaluation;
neither these matches nor their outcomes are research evidence.

The smoke verifies immutable policy lock, paired initial tensors/manifest/scenario,
separate partition seeds, actual JSON/CSV/Markdown exports, per-partition sample
summaries and paired deltas, and all four PNG/SVG plot families. Phase B's
evaluation split sequence is exactly `[proxy, proxy, test]`, while every
trajectory evaluation remains proxy. Test is evaluated only at the final model.
All services started by these checks were stopped after completion.

## Remaining limits

Use [the Java protocol](../reproducibility-fairness-matched.md) to run the full
E0 and then the42/30-run Covertype phases. A successful synthetic smoke cannot
unlock a research E1 batch. No adaptive advantage, statistical equivalence or
cross-partition generalization follows from these checks.

Deterministic duration is an explicit uncalibrated simulation model. Server,
selector/fairness overhead and wall time remain measured; total virtual seconds
therefore retain physical timing variability. Tensor replay is tested on the
recorded CPU/runtime, with no promise across hardware or package versions.
