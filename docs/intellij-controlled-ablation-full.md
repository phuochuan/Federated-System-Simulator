# Full controlled ablation: manual Uvicorn and IntelliJ

Requested launch on4 November2026: user-owned Uvicorn worker and Java in IntelliJ,
the entire predefined225-run matrix, without the separate40-run Covertype pilot.

1. In the repository-root PowerShell terminal, start the existing worker:

   `.\.venv\Scripts\python.exe -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000`

2. Open/import the `ferderatedsystem` Gradle module in IntelliJ, select JDK17,
   reload its shared run configurations, then Run **Controlled Fuzzy Ablation Full**.
   Its main class is `com.huanphan.ferderatedsystem.ControlledAblationIdeLauncher`.
   Do not select the old Resume Frozen E3 configuration for this new study.

The shared configuration sets `--stage=full --run-budget=0 --round-budget=0`.
Zero means unlimited admissions: all225 research runs,70 rounds each, sequentially.
The five policies A0-A4 cover alpha.1/.5/1, partitions6001/6002/6003 and seeds42-46.
Two2-round reproducibility audits are separate implementation checks, not a pilot.
Total workload is **227 runs /15,754 rounds**, of which **225/15,750 are research**.
No40-run pilot is admitted and no pilot-validation lock is fabricated.

`configurations/controlled-fuzzy-ablation-full.json` uses explicit protocol version
`controlled-fuzzy-width-full-v1`. It retains the established five policies,
scoring/width equations, weights and training settings. All parameters/design axes
are fixed in `full-policy-lock.json` before research training. Reports explicitly
identify a full predeclared study without a separate Covertype pilot; they do not
claim pilot-validated confirmation. The prior pilot/confirmation workflow remains
available with its original gates. Existing result publications are unchanged.

## Preflight and storage

Use IntelliJ Program arguments `--stage=full --mode=preflight` to generate the
resource/matrix report without training or needing the worker. Restore the shared
arguments above to execute. The measured v2 full storage estimate is39.3GiB,
including the8GiB free-space reserve and nine dataset assignments. It uses300KB
per checkpoint/receipt and220KB per SQLite round, versus measured maxima197519B
and159164B;256MiB covers reports/JAR/logs plus a separate audit allowance.
The former56.3GiB estimate overallocated checkpoint size. About40.4GiB free
passes the revised estimate. Add/free capacity if the executing preflight fails.
The guard stops explicitly; it never silently substitutes pilot or weakens
checkpoint/provenance guarantees. Smaller budgets permit incremental execution
but do not remove total storage needs. No data/checkpoint cleanup is automatic.

## Operation and recovery

The small IntelliJ parent JVM runs the existing coordinator watchdog through a
repository Python helper. The actual scientific coordinator uses an immutable
copied JAR,512MiB heap and the JDK selected in IntelliJ. Progress and errors appear
in the IntelliJ console; rotating coordinator logs remain in the batch logs folder.
The supervisor limits repeated JVM crashes and recovers compatible interrupted
work using the established APIs. Hard IDE Stop cleans owned server/controller
children through an owner monitor; it does not terminate the independent worker.

The worker is manual: this configuration does not launch/restart/terminate it.
If it exits, restart it with the same command and runtime. Existing bounded HTTP
retries/readiness waits may tolerate the interruption; an exhausted/fatal failure
stops with an explicit error. Re-run the same IntelliJ configuration to resume
verified checkpoints/completed runs. Never delete state or change scientific
parameters to resolve a provenance error. Scoped idle-sleep protection cannot
recover from manual sleep, power loss or exhausted disk capacity.

Batch pointer: `artifacts/research/controlled-fuzzy-ablation/full/active-batch.json`.
Each unique batch contains status/preflight/protocol/runtime/source/build identities,
SQLite, replay evidence, full-policy-lock.json, report CSV/JSON/Markdown and figures.
Check completion.json status COMPLETED and integrity-report.json passed=true;
there should be225 completed research runs plus two audits. The read-only verifier
is `scripts/verify_controlled_batch.py <batch-folder>`.

Optional Program arguments: `--mode=report-only` regenerates reports without
training; `--run-budget=N --round-budget=M` limits admissions; `--output-root=...`
selects a new workspace-local batch family. Defaults resume the same full batch.
No Java source editing is needed. Worker and coordinator ports default8000/8080;
duplicate coordinator/worker listeners are rejected rather than killed.
