# Held-out Pareto implementation validation — 28 October 2026

No60-run Covertype matrix was launched. The completed Phase A and its NO_MATCH
lock were read without modifying their reports, database or checkpoints.

## Checks completed

- `gradlew.bat test bootJar --no-daemon`: **73 Java tests pass**. New tests cover
  all seven objective directions, strict vs equal dominance (including signed
  zero), missing objectives,2D vs multi-objective completeness, locked policies,
  source integrity/inheritance, E0 blockers, paired P4 comparisons, partition
  inconsistency, report generation, incomplete cells and explicit CLI dispatch.
  Existing F/L, Phase A, retry, snapshot/resume and provenance tests still pass.
- `python -m pytest ml-python/tests scripts/test_fairness_matched.py -q`:
  **23 Python tests pass**; the existing TestClient deprecation warning remains.
- `python scripts/verify_pareto.py`: **PASS**. Evidence:
  `artifacts/pareto-smoke/d59b131c10/`.

The smoke first validated the REAL Phase A evidence with the new preflight mode.
It reported `ready:false`, `determinismClaimed:false`, reason **E0_MISSING**,
and created zero experiments. See
`real-protocol-preflight/pareto-preflight.json` under the smoke evidence folder.
The historical audit is successful for its old build; it does not certify this
new Java/Python runtime.

The remaining smoke stages are synthetic and three rounds only:

1.12 E0 runs, three repeats per fixed/adaptive policy and duration mode.
2. Seven validation policies on one synthetic partition/seed; strict smoke
   tolerances yield NO_MATCH.
3. Missing-audit preflight proves the held-out gate cannot be bypassed.
4. A deliberate HTTP400 stops the first P run after committed round1.
5. API-only restart on the same JAR/worker resumes that SQLite snapshot through
   round3, including scheduler credit/history/provenance checks.
6. The Pareto launcher reuses that completed run and finishes eight held-out
   synthetic runs (four policies ×two partitions ×one seed).
7. A second Pareto launch leaves the committed-round count unchanged.

The smoke verifies P1–P4, final test vs proxy trajectory labels, six paired fixed
comparisons, immutable config/evidence, all requested report filenames and five
PNG/SVG figure families. The actual Accuracy–Gini plot was visually inspected.
Partition frontier status can differ even in this tiny example; no scientific
conclusion is drawn from smoke means or measured timing differences.

## User-controlled research execution

Run the NEW E0 on the chosen frozen runtime before the60-run experiment. A fresh,
unexecuted profile was prepared at
`artifacts/research/pareto-20261028-204148/`. It contains only configs and
single-argument launch profiles, not experiment data or a new audit certificate.

See [the protocol, commands, metrics and evidence limits](../pareto-tradeoff.md).
The successful synthetic smoke cannot unlock a production research protocol.
