# Full controlled ablation: IntelliJ/manual-worker validation

User requested the entire225-run study without the separate40-run Covertype
pilot, using manual Uvicorn and IntelliJ. Added explicit protocol
controlled-fuzzy-width-full-v1, full-policy-lock.json and the shared
Controlled Fuzzy Ablation Full IntelliJ configuration. Existing staged
pilot/confirmation protocols retain their original gates and results.

- Java test/bootJar: **93 tests, zero failures/errors**.
- Python suite: **54 passed**, one existing Starlette/httpx deprecation warning.
- Real IDE entry-point evidence:
  `artifacts/controlled-ablation-ide-smoke/d44057eeb1/summary.json`: **PASS**.
  The actual Java main was loaded from the built JAR, with a separately owned
  Uvicorn worker on a private port. The full synthetic fixture completed19
  rounds: two2-round audits and five3-round FULL runs. No PILOT stage or
  pilot-validation lock was created. All parameters were predeclared.
- Hard-killed IDE launcher cleaned owned coordinator/controller children while
  leaving the independent worker healthy. Normal budget stops, unlimited resume,
  completed reuse and report-only also preserved that worker. Final checkpoint
  hashes, round continuity, final-only test and offline evidence verification pass.
- No production Covertype study was started. Synthetic fixtures are test evidence.

Executing-design preflight:
`artifacts/controlled-ablation-preflight/20261104/full/preflight.json`.
Research matrix225x70=15,750 rounds; separate audit workload2x2, giving227
runs/15,754 rounds total. No repository-visible conflicts for6001/6002/6003.
Both admission budgets default to0 (unlimited) in the dedicated IDE full config.
Conservative full estimate56.3GiB versus about40.4GiB available: the production
capacity guard remains enabled and will block training until capacity is added
or an explicit smaller admission budget is chosen. It never substitutes pilot.

Scientific formulas and prior published evidence remain unchanged. Reports label
this as a full predeclared ablation without separate Covertype pilot validation.
The manual worker has no process watchdog under this launch choice; it must be
restarted manually if it exits. Coordinator transport retries/readiness/resume
remain bounded, and the Java child retains its immutable JAR/runtime identity.
