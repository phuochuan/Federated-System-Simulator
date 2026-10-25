# Local API

Both services bind to localhost. Java defaults to 8080, Python to 8000. Python's interactive OpenAPI is at `http://127.0.0.1:8000/docs`.

## Java coordinator

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Java plus worker health |
| POST | `/experiments` | Validated JSON config; 202 after admission |
| GET | `/experiments` | Stored experiment status list |
| GET | `/experiments/{id}` | Config, snapshot, status, failure detail |
| GET | `/experiments/{id}/rounds` | Full round, client, simulation, policy and model metrics |
| GET | `/experiments/{id}/result` | Single final round object, including evaluation; round 20 for a 20-round run |
| GET | `/experiments/{id}/metrics.csv` | Compact CSV export |
| POST | `/experiments/{id}/resume` | Resume FAILED/INTERRUPTED from the latest committed snapshot |

Only one experiment is admitted at once; a second returns 409. IDs are unique; use a new ID for a new experiment. Unknown experiments return 404. Invalid configurations return 400. Failed runs retain their config, previous committed model and error detail. Resume does not change the configuration.

`GET /experiments/{id}/result` reads the configured final round from SQLite and
returns the same round object as `/rounds`, without the other rounds. It requires
`COMPLETED`; running, failed or interrupted experiments return 409 so a partial
round history cannot be mistaken for the final result. A missing experiment returns
404; a completed record without its final round returns 409. This endpoint does
not rerun training or evaluation and works with previously completed experiments.

See single-run files such as `configurations/fedavg.json` for complete request bodies. `controlled-matrix.json` and `fuzzy-matrix.json` are batch protocols, not bodies for `POST /experiments`. `manifestPath` is a directory relative to the shared workspace, not the JSON file. To start a new dataset/seed comparison generate a matching manifest and use another experiment ID. Numerical fields are validated; fuzzy settings have documented defaults, but criterion weights must be explicit. Unknown fields are rejected.

Experiment configs optionally accept `architecture` (`mlp_54_128_64_7` or
`mlp_54_256_128_7`). Java passes it explicitly at initialization when present;
omitting it preserves the Python worker default. Existing checkpoint metadata
continues to determine architecture on resume. The matrix launcher uses this field
to compare small and large MLPs without restarting Python.

Optional `scenarioTracePath` references a generated matrix trace within the shared
workspace. Java validates all events and persists its SHA-256 hash; resume rejects
a changed trace. Each round includes the full population trace, conditional fairness,
logical payload byte counts, and proxy/weight/aggregation overhead measurements.

`selection` supports `random`, `feasible_random`, `resource_aware`, `fuzzy_topsis`, `fuzzy_topsis_fair` and `adaptive_fuzzy_topsis_fair`.
Feasible Random uniformly samples without replacement from available clients passing
the same RAM and pre-round estimated-deadline filter as Resource-aware, without ranking.

The three fuzzy methods require `fuzzySelection` with nonnegative finite weights summing to one. Existing baseline configs may omit it. They share the same RAM/deadline feasibility predicate and never fill missing slots with infeasible clients. `aggregation` remains `fedavg` or `fedlbw`; FMCDM is Java client selection, not a Python aggregation method.

To construct a full single-run body from the F batch protocol in PowerShell:

```powershell
$matrix = Get-Content configurations/fuzzy-matrix.json -Raw | ConvertFrom-Json
$config = $matrix.baseConfig
$config | Add-Member -NotePropertyName fuzzySelection -NotePropertyValue $matrix.fuzzySelection
$config | Add-Member -NotePropertyName architecture -NotePropertyValue 'mlp_54_256_128_7'
$config.experimentId = 'fuzzy-api-example-42' # choose a new ID for another run
$config.selection = 'adaptive_fuzzy_topsis_fair'
# Optional implementation smoke; omit for the 70-round protocol.
$config.rounds = 3
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/experiments `
  -ContentType 'application/json' -Body ($config | ConvertTo-Json -Depth 12)
```

The prepared manifest must already exist. Start Java with `MINIFLS_METHOD=none` for this API example. Alternatively, `MINIFLS_METHOD=fuzzy_matrix` launches the complete [F1–F5 batch](controlled-matrix.md#nhóm-f--fmcdm-client-selection) using `MINIFLS_FUZZY_MATRIX_CONFIG`.

Round JSON includes `selectionMethod`, `feasibleCandidateCount`, `selectorComputationMs`, `selectedClientIds`, `fuzzyTopsisScores`, `fairnessCredits`, `finalSelectionScores` and `currentFairnessLambda`. Fuzzy rounds additionally expose `selectorInput`, raw TFNs/observations, ideals/distances, `fairnessCreditsAfterRound` and `nextFairnessLambda`. Full score maps are empty for baselines. The `fairness` object distinguishes population, RAM-feasible and valid-opportunity coverage, selection/completion Gini and feasible-opportunity staleness. `cumulativeVirtualSecondsWithSelector` adds selector and separately measured `fairnessUpdateMs` to the existing virtual clock.

`GET /experiments/{id}` includes `snapshot.selectionHistory` and, for fuzzy methods, `snapshot.fuzzySelectionState` with method/version, credits, lambda and completed-round feedback. They commit atomically with round metrics. Resume restores this state; it does not reset credits or read future events. A missing or incompatible fuzzy snapshot fails explicitly. Legacy baseline snapshots remain readable; their new opportunity diagnostics identify the first observed round via `feasibleHistoryStartRound`.

`/result` returns these fields for the configured final round; `/rounds` exposes the full trajectory. `/metrics.csv` remains a compact legacy export and does **not** include full fuzzy scores or the expanded conditional fairness metrics. Use round JSON or the matrix TXT report for these analyses. See [definitions and configuration parameters](fuzzy-mcdm-client-selection.md).

## Python worker

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Single-worker concurrency state |
| GET | `/methods` | Implemented method IDs and full catalog with planned packages |
| POST | `/methods/{method}/weights` | Method-specific scalar weights from sample counts and proxy losses |
| GET | `/datasets/manifest?manifestPath=...` | Verified prepared dataset metadata |
| POST | `/models/initialize` | Seeded version-zero MLP |
| POST | `/train` | One client partition from supplied global checkpoint |
| POST | `/models/evaluate` | Train/proxy/test evaluation |
| POST | `/models/aggregate` | Validated weighted tensor averaging |
| POST | `/simulation/round` | SimPy parallel virtual-device events |

`POST /models/initialize` optionally accepts `architecture` (`mlp_54_256_128_7` or
`mlp_54_128_64_7`). An explicit request overrides `MINIFLS_MODEL_ARCHITECTURE` in
the Python worker; the default is the larger MLP. Initialization, training,
evaluation and aggregation responses include the actual `architecture`.
Existing Java requests need no changes. Later operations and resumed experiments
use checkpoint metadata and reject mixed architectures during aggregation.

For example, `POST /methods/fedlbw/weights` accepts
`{"samples":[100,200],"losses":[1.0,2.0]}` and returns
`{"method":"fedlbw","weights":[0.6666666666666666,0.3333333333333333]}`.
FedAvg accepts `samples` with an optional empty `losses` array. Java supplies only
accepted updates and validates the response before tensor aggregation. Planned
methods return 501; unknown method IDs return 400. See [package catalog](method-packages.md).

`TRAINING_COMPLETED` means physical training finished, not virtual-round acceptance. The Java coordinator alone chooses accepted updates. Python aggregation checks experiment/round/base version, distinct clients, architecture, tensor keys/shapes/dtypes/finite values and normalized nonnegative weights. See OpenAPI for precise schemas. Workspace artifacts are local trusted experiment inputs; the API is not an internet-facing service.
