# Manual Uvicorn + IntelliJ for the existing frozen E3

This launch path resumes the current C1/C4/C5 generalization study under U0.
It does not select policies, rerun pilot training or change reliability/calibration
definitions. The old coordinator JAR, worker implementation, experiment configs,
policy lock, model checkpoints and receipts remain authoritative.

## Start

1. Stop the previous two PowerShell watchdog sessions with Ctrl+C. The new Java
   launcher refuses an existing coordinator lock or occupied server port; do not
   run both launch methods simultaneously.
2. Open PowerShell at the repository root and start the worker yourself:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000
   ```

3. In IntelliJ, open/import the Gradle project in `ferderatedsystem`. Select the
   shared **Resume Frozen E3** run configuration and click **Run**.
   It uses `com.huanphan.ferderatedsystem.FrozenE3IdeLauncher`, working directory
   at the repository root, with JDK **17**. For this existing batch, the recorded
   Java runtime is **17.0.11**. Keep that runtime installed/selected; another Java
   runtime will fail the saved identity check.

If IntelliJ has not discovered the shared configuration, reload the Gradle
project. Alternatively create an Application configuration for
`FrozenE3IdeLauncher` in module `ferderatedsystem.main`, select the recorded JDK
and use the repository root as working directory. Use this new entry point for
the frozen batch rather than launching `FerderatedsystemApplication` as newly
compiled classes: that would have a different scientific build hash.

No watchdog terminal, environment-variable setup or Java source editing is
needed. The launcher starts the **existing copied `coordinator.jar`** as an
API-only child process, and runs a dedicated E3 controller. Both write directly
to the IntelliJ console. It never starts or terminates your manually owned worker.

## What changes operationally

- Existing validation completion, policy lock and executing-build audit are
  verified instead of recalculating validation decisions.
- The 66 original frozen source files and JAR hash remain checked. No original
  source-identity record is rewritten to accept a new build.
- The original scientific coordinator/worker runtime identity must still match.
  Transport retries/timeouts are loaded from that saved identity.
- The original experiment/trace builder, checkpoint validation, admission,
  idempotency, retry and round-resume code is reused.
- Each partition is verified once per launch, rather than once per policy/seed.
- Intermediate E0/E1/E2/E4 reports are not regenerated during resume. Final reports
  run once after all E3 runs commit, with a progress heartbeat during export.
- A separate `launchers/ide-*.json` records this operational controller's hash,
  launcher class hash and the unchanged frozen scientific identities. This
  records the launch change without pretending the new launcher was part of the
  original source snapshot.

The default remains the locked **135 runs x 70 rounds**. Previously committed
runs/rounds are reused; the run interrupted at round 62 resumes from round 63.
The launcher does not adopt orphan model files from uncommitted rounds.

## Logs and status

Look in the IntelliJ console for `[IDE]`, `[E3-PREFLIGHT]`, `[E3]` and `[REPORT]`.
The frozen coordinator also prints its normal training, aggregation and round
commit logs. Worker logs remain in your Uvicorn terminal. `status.json` in the
active batch continues to track progress.

This is a manually managed launch. If Uvicorn exits, restart the same worker
command. Transient HTTP retries remain active, but there is no worker process
watchdog. If a retry budget is exhausted or Java stops, rerun the IntelliJ
configuration to resume. A changed runtime, corrupt checkpoint or ambiguous
receipt still fails closed.

The controller recognizes only the exact frozen checkpoint-RPC transport-budget
failure (`reason=recovery budget exhausted`) as eligible for bounded recovery.
It waits until the old worker operation is idle, verifies runtime, contiguous
SQLite commits, snapshot provenance, checkpoint receipt and actual tensor hash,
then resumes through the original Java API with a fresh uncommitted-round attempt.
This consumes the existing experiment retry budget; it does not increase Java's
HTTP timeout or accept an integrity/scientific validation error. A retry of the
same run keeps one run admission and its maximum reserved round budget.

While this IntelliJ E3 controller is active, it requests Windows to inhibit
automatic idle sleep using `ES_CONTINUOUS | ES_SYSTEM_REQUIRED`, and releases
that request when the controller exits. It changes no power plan/registry and
does not keep the display on. Manual Sleep, lid/power-button actions and loss of
power can still interrupt work. See Microsoft's
[SetThreadExecutionState documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate).

Stopping the IntelliJ launcher stops its API-server/controller children. An
owner-process monitor also stops its own frozen API server if IntelliJ forcibly
kills the launcher. It never targets the independently started Uvicorn process.

## Optional budgets

By default no run/round admission cap is set. In IntelliJ **Program arguments**,
`--run-budget=15` limits an invocation to fifteen unfinished experiments. A
`--round-budget=700` reserves at most 700 remaining rounds before admission.
These arguments do not edit the immutable scientific protocol. Budget stops
preserve checkpoints and skip expensive intermediate report exports; rerun to
continue. Disk checks remain active.

## Verification

Java/Python unit tests cover frozen identity rejection, policy/audit validation
and per-partition caching. `scripts/verify_frozen_e3_ide.py` runs the actual Java
entry point with a separate manual worker, synthetic data, private ports and a
private database. It checks budget/resume, completed-run reuse, unchanged frozen
metadata, no duplicate commits and that the worker survives Java completion.
It does not start the production E3 batch.
