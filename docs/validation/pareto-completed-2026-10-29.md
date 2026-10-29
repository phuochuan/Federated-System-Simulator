# Completed Covertype Pareto evaluation — 29 October 2026

The real held-out evaluation completed **60/60 Pareto runs**, with **70 rounds
per run and 4,200 rounds total**. The associated E0 audit completed **12/12 runs**.

The matrix uses partition seeds 2001/2002/2003 and training seeds 42–46.
P1/P2/P3 have fixed fairness lambdas .650/.675/.725; P4 is adaptive with initial
lambda .300. Policies were locked after the completed NO_MATCH Phase A, before
the held-out evaluation. Final learning scores use the final test checkpoint;
proxy trajectories provide stability and target-time metrics.

## Recovery and integrity

An export-time Java heap failure occurred after the 55th run had committed its
70 rounds. Recovery reconstructed the original runtime in an isolated folder;
the recovered Java build hash and the worker runtime matched the original
provenance exactly. A Java 21.0.2 process with `-Xmx4g` reused the 55 completed
runs and trained the remaining five. Original run identities and protocol gates
were preserved.

Verified after completion:

- All 60 SQLite experiment records are `COMPLETED`, each with 70 saved rounds.
- Every run has experiment, result and round exports.
- The aggregate report is complete and contains the same 60 experiment IDs.
- The final results CSV contains 60 records.
- Five PNG plots and corresponding SVG files were generated.
- The completion marker's SHA-256 matches the aggregate JSON report:
  `0882635759f1be91852e152bbba8bc5476e9cc839fd90a0708b0f046624e8b18`.
- The owned Java/Python processes were stopped after verification.

Original runtime build hash:
`fda9679f2f0147106416d9779e40bb3da24e0e00deab3fe94c663dab296ab6df`.

## Current source validation

The later memory fix streams atomic JSON exports and canonical hashes, and
retains disk indexes instead of all research round trees across the matrix.
It preserves canonical identities, detects modified exports and produces the
same report metrics as in-memory evidence.

- Full Java test suite: **80 passed**, zero failures/errors/skips.
- Python tests: **23 passed**; one existing Starlette TestClient deprecation warning.
- Result archives: ZIP integrity checks plus file and part SHA-256 inventory.

This source build differs from the archived run runtime. Fresh runs require
fresh output metadata and E0 evidence; the archived E0 must not certify a new build.

## Published evidence

- [Readable report](../../results/research/pareto-20261028-204148/pareto-tradeoff-summary.md)
- [CSV results](../../results/research/pareto-20261028-204148/pareto-tradeoff-results.csv)
- [JSON results](../../results/research/pareto-20261028-204148/pareto-tradeoff-results.json)
- [Recovery verification](../../results/research/pareto-20261028-204148/recovery/verification.json)
- [Archive index and restoration instructions](../../results/README.md)

Interpret partition-specific frontiers and paired differences as trade-offs;
the protocol does not select an overall winner or establish algorithm superiority.
