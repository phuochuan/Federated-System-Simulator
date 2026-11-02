# IntelliJ/manual-worker frozen E3 launch validation — 3 November 2026

The requested launch uses a manually started Uvicorn worker and the IntelliJ
`Resume Frozen E3` configuration. Its Java entry point is
`FrozenE3IdeLauncher`; actual scientific coordination runs in the batch's
original copied JAR, not a newly compiled replacement scientific runtime.

## Verified

- Java: **88 tests pass**, including the original suite and launcher argument,
  working-directory and frozen source/JAR rejection checks.
- Python: **39 tests pass**, including lock/audit validation and one verification
  per partition per launch. The existing Starlette/httpx deprecation warning
  remains; no tests were disabled.
- The shared IntelliJ XML parses and targets `ferderatedsystem.main`, JDK 17,
  `FrozenE3IdeLauncher` and the repository working directory.
- Real synthetic smoke runs the actual Java launcher with a separately owned
  Uvicorn process, private ports and its own frozen JAR/database. It verifies
  admission budget, resume, completed-run reuse, final reporting, no duplicated
  round commits and unchanged policy/protocol/source/build/runtime identity files.
- A hard launcher termination also removes its frozen API/controller children;
  the independent worker survives both hard termination and successful completion.
- Original production frozen source-file hashes and the copied coordinator JAR
  still match. No original selector, reliability, training, checkpoint, protocol
  or policy-lock file was modified for this launch change.

## Evidence

Final smoke directory: `artifacts/frozen-e3-ide-smoke/fc305490c6`.
`summary.json` records PASS with **25 committed synthetic rounds**: a tiny
validation fixture and two three-round held-out confirmation runs. These are
implementation checks, not research results or evidence of superiority.
`ownership.log` records the hard-stop cleanup; `budget.log` and `resume.log`
show real progress through the Java entry point. The earlier smoke in
`artifacts/frozen-e3-ide-smoke/ccf6e59e68` also passed normal budget/resume checks.

The controller retains original config/trace construction, scientific provenance
verification, worker retries and checkpoint/receipt validation. It reads the
existing policy lock without reselecting policies. Operational additions receive
their own `launchers/ide-*.json` identity record; the old source identity is not
rewritten to conceal the change.

Production E3 was not launched by this validation. The user starts the worker
and IntelliJ configuration. Existing watchdog sessions must be stopped first;
locks and occupied ports fail closed if a coordinator is still running.
