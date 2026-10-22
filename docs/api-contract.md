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
| GET | `/methods` | Implemented method IDs and full catalog with planned packages |
| POST | `/methods/{method}/weights` | Method-specific scalar weights from sample counts and proxy losses |
| GET | `/datasets/manifest?manifestPath=...` | Verified prepared dataset metadata |
| POST | `/models/initialize` | Seeded version-zero MLP |
| POST | `/train` | One client partition from supplied global checkpoint |
| POST | `/models/evaluate` | Train/proxy/test evaluation |
| POST | `/models/aggregate` | Validated weighted tensor averaging |
| POST | `/simulation/round` | SimPy parallel virtual-device events |

For example, `POST /methods/fedlbw/weights` accepts
`{"samples":[100,200],"losses":[1.0,2.0]}` and returns
`{"method":"fedlbw","weights":[0.6666666666666666,0.3333333333333333]}`.
FedAvg accepts `samples` with an optional empty `losses` array. Java supplies only
accepted updates and validates the response before tensor aggregation. Planned
methods return 501; unknown method IDs return 400. See [package catalog](method-packages.md).

`TRAINING_COMPLETED` means physical training finished, not virtual-round acceptance. The Java coordinator alone chooses accepted updates. Python aggregation checks experiment/round/base version, distinct clients, architecture, tensor keys/shapes/dtypes/finite values and normalized nonnegative weights. See OpenAPI for precise schemas. Workspace artifacts are local trusted experiment inputs; the API is not an internet-facing service.
