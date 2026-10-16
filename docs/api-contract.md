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
| GET | `/experiments/{id}/metrics.csv` | Compact CSV export |
| POST | `/experiments/{id}/resume` | Resume FAILED/INTERRUPTED from the latest committed snapshot |

Only one experiment is admitted at once; a second returns 409. IDs are unique; use a new ID for a new experiment. Unknown experiments return 404. Invalid configurations return 400. Failed runs retain their config, previous committed model and error detail. Resume does not change the configuration.

See `configurations/*.json` for complete request bodies. `manifestPath` is a directory relative to the shared workspace, not the JSON file. To start a new dataset/seed comparison generate a matching manifest and use another experiment ID. All numerical configuration fields are explicit; unknown fields are rejected.

## Python worker

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Single-worker concurrency state |
| GET | `/datasets/manifest?manifestPath=...` | Verified prepared dataset metadata |
| POST | `/models/initialize` | Seeded version-zero MLP |
| POST | `/train` | One client partition from supplied global checkpoint |
| POST | `/models/evaluate` | Train/proxy/test evaluation |
| POST | `/models/aggregate` | Validated weighted tensor averaging |
| POST | `/simulation/round` | SimPy parallel virtual-device events |

`TRAINING_COMPLETED` means physical training finished, not virtual-round acceptance. The Java coordinator alone chooses accepted updates. Python aggregation checks experiment/round/base version, distinct clients, architecture, tensor keys/shapes/dtypes/finite values and normalized nonnegative weights. See OpenAPI for precise schemas. Workspace artifacts are local trusted experiment inputs; the API is not an internet-facing service.
