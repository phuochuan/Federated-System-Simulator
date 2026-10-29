# Worker retry and a fresh research batch

`PythonMLClient` now retries transient transport failures, including connection
errors and request timeouts, HTTP502/503/504, and the exact worker-busy HTTP409
response. Other conflicts, validation errors, HTTP500 and malformed JSON fail
immediately. Interruptions cancel retry and retain the thread interrupt flag.
The persisted experiment error now identifies method, route, URL, attempt count
and failure reason instead of only `Worker unavailable`.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `MINIFLS_WORKER_MAX_ATTEMPTS` | 4 | Total sends of the operation, including the first |
| `MINIFLS_WORKER_RETRY_DELAY_MS` | 2000 | Initial retry wait |
| `MINIFLS_WORKER_RETRY_MAX_DELAY_MS` | 30000 | Exponential backoff cap; maximum accepted cap60s |
| `MINIFLS_WORKER_REQUEST_TIMEOUT_SECONDS` | 1800 | Timeout per HTTP attempt, unchanged by default |

Default waits are2s,4s,8s. GET capability probes have their own bounded retry
budget. A checkpoint POST's retry checks that the worker supports safe replay.
Set max attempts to1 to disable automatic retry/capability probing. These
transport settings are captured in research runtime provenance.

## Safe replay of a lost response

Initialize, train and aggregate keep their existing immutable checkpoint paths
and operation IDs. The worker stores a `.response.json` receipt beside each new
checkpoint, containing a canonical request hash, response hash and the complete
original response. Retry sends the identical serialized request and operation ID.
The worker validates the checkpoint/receipt and returns the original result,
including its tensor hash and measured `actualTrainingMs`, without training or
aggregating again. A busy in-flight job retains the single-worker lock; duplicate
requests get the retryable busy response until it finishes.

Receipts survive worker restarts. Reusing an operation ID with changed parameters
is a terminal409. If a process dies after checkpoint commit but before receipt
commit, retry also fails closed with409: it never overwrites that checkpoint or
invents the lost measured duration. Resume the round through the existing API
after the failure; resume generates a fresh operation ID for its uncommitted work.
Completed SQLite rounds are not committed a second time.

Retry cannot keep the computer awake or restore a worker that stays down longer
than the retry budget. Wall time and measured server overhead include retries and
backoff; deterministic simulated training duration remains a separate metric.

## Starting again with this changed build

The new Java/Python contents and transport provenance differ from the previous
17 completed validation runs. Keep those results; do not disable provenance checks
or overwrite their batch metadata to reuse them under this new build.

Build/test (no training matrix):

```powershell
Push-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Pop-Location
.\.venv\Scripts\python.exe -m pytest ml-python/tests scripts/test_fairness_matched.py -q
```

Generate a separate database, config copies and stage-specific output settings:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_research_retry.py
```

This only prepares files and prints environment settings; it launches nothing.
Copy the generated `run.env` values into the **IDE Run Configuration** (setting
PowerShell variables alone does not update an already running IDE).
Alternatively, copy the single line from `program-arguments.txt` into the IDE's
**Program arguments** field. It contains ONE `--spring.config.additional-location`
argument loading `application-retry.properties`, avoiding multi-argument quoting
issues with delegated Gradle launchers. Replace the old Program arguments entirely;
do not wrap the line in quotes. Clear stale `MINIFLS_*` path/database overrides
from the IDE environment if using this file: environment variables take precedence
over configuration-file values. Use either this config file or the matching
`run.env` values, not conflicting settings from an earlier batch.
`MINIFLS_AUDIT_OUTPUT` and `MINIFLS_MATCHED_OUTPUT` take priority over the generic
research output override. The copied Phase A/B config points to this new E0
report, so E0 and E1 do not collide on immutable batch metadata.

Restart the Python worker to load the updated API, then start Java using the same
build for all new stages. The three direct E0→Phase A→Phase B calls currently in
the application's runner were preserved. The old database, outputs, checkpoints
and partitions are untouched; validated partition files can still be reused.

`MINIFLS_LAUNCH_ENABLED=false` disables startup experiments even when calls are
written directly in `ApplicationRunner`; this is used only for API-only operation
and smoke checks. Default true preserves the current launch behavior.

## Fault-injection smoke

```powershell
.\.venv\Scripts\python.exe scripts/verify_worker_retry.py
```

This uses isolated ports/database and a synthetic2-round experiment. A proxy
deliberately discards a successful `/train` response after its checkpoint and
receipt have been committed. It verifies that Java retries the same request,
gets the exact original response, completes both rounds and creates no duplicate
checkpoint. It does not use or restart an existing worker on port8000.
