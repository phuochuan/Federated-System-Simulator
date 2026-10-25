# MiniFLS — Resource-Aware Federated Learning Simulator

A research testbed built with **Java Spring Boot + Python/PyTorch + SimPy**, using CPU training with **100 logical clients**, **5 selected clients per round**, and **one active local training job** at a time. The primary dataset is **UCI Covertype**, with an **MLP 54 → 256 → 128 → 7** (47,879 parameters) by default. The original 54 → 128 → 64 → 7 baseline and its checkpoints remain supported.

The pipeline prepares data, selects clients in Java, trains each client from the same global checkpoint in PyTorch, simulates outcomes with SimPy, filters updates in Java, computes weights in method-specific Python packages, validates weights in Java, aggregates and evaluates in Python, and commits results to SQLite. Aggregation supports FedAvg and FedLBW. Selection supports Random, Feasible Random, Resource-aware, Fuzzy TOPSIS, Fuzzy TOPSIS with Fairness Credit, and Adaptive Fuzzy TOPSIS with Fairness Credit. Metrics, CSV/JSON exports, plots, and recovery after interruption are included.

The implementation follows the [Notion plan](https://app.notion.com/p/3fbb6ecc362380b29145ed0a5324deac). Smoke-test results do not establish that one algorithm outperforms another.

## Installation on Windows

Requirements: **JDK 17+** (validated on 17; supports 21), **Python 3.11–3.13**, and network access for the initial dependency and Covertype downloads. Run PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python -m pip install -e 'ml-python[test]'
```

`ml-python/requirements-validated.txt` records the validated Windows environment. To reproduce it, run `pip install -r ml-python/requirements-validated.txt --extra-index-url https://download.pytorch.org/whl/cpu`, followed by `pip install --no-deps -e ml-python`. On Linux, use `.venv/bin/python` instead of the Windows Python path.

## Data preparation

```powershell
# Real dataset: train/proxy/test split of 435759 / 29051 / 116202.
.\.venv\Scripts\python -m minifls.data --dataset covertype --output artifacts/partitions/covertype-iid-42

# Non-IID data with the same seed; existing manifests cannot be overwritten.
.\.venv\Scripts\python -m minifls.data --dataset covertype --strategy dirichlet_label_skew --alpha 0.5 --output artifacts/partitions/covertype-dirichlet-42

# Synthetic data is intended for quick tests only.
.\.venv\Scripts\python -m minifls.data --dataset synthetic --output artifacts/partitions/synthetic-iid-42
```

Only the first ten numerical Covertype features are scaled, using statistics fitted on training data. Labels are mapped from 1–7 to 0–6. Proxy and test rows are excluded from client partitions. Other partition modes are `iid_quantity_skew` and `dirichlet_mixed_skew`. Each manifest stores seeds, indices, hashes, scaler statistics, and class histograms.

## Starting services and running experiments

The [controlled matrix workflow](docs/controlled-matrix.md) contains the existing A/B/C comparisons and the separate **F group for Fuzzy Multi-Criteria Decision Making (FMCDM)**. `MINIFLS_METHOD=fuzzy_matrix` calls `compareFuzzyClientSelection()` and runs F1–F5, producing six paired comparisons in one TXT report. It uses `configurations/fuzzy-matrix.json`: five seeds, 70 rounds, 100 clients, K=5, Non-IID alpha=.5 and FedAvg throughout.

`MINIFLS_METHOD=matrix` uses `configurations/controlled-matrix.json` and the A/B/C calls enabled in `FerderatedsystemApplication.paperExperiment()`. Those calls are currently commented out; uncomment the desired calls before running this mode. The F entry point is already enabled and independent of that choice.

To select a paper-specific Python package from the Java application class or IDE, see
[method packages and environment configuration](docs/method-packages.md) and [.env.example](.env.example).
`MINIFLS_METHOD=none` keeps startup in API-only mode; `fedavg` or `fedlbw` submits one experiment on startup.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
.\.venv\Scripts\python -m minifls.experiment configurations/fedavg.json
```

The script builds Java and starts both services in hidden processes. It writes PIDs to `artifacts/processes.json` and logs to `artifacts/logs/`. Java listens at `http://127.0.0.1:8080`, Python at `http://127.0.0.1:8000`, and the Python OpenAPI UI is available at `/docs`.

| Configuration | Dataset | Selection / aggregation | Simulation |
| --- | --- | --- | --- |
| `configurations/fedavg.json` | Covertype IID | Random / FedAvg, 20 rounds | Disabled |
| `configurations/resource-aware-fedlbw.json` | Covertype Dirichlet | Resource-aware / FedLBW | CPU/RAM, availability, dropout, deadline |
| `configurations/smoke.json` | Synthetic | Random / FedAvg, 20 rounds | Heterogeneous |
| `configurations/fuzzy-matrix.json` | Covertype Non-IID | F1–F5 client selection / FedAvg, 70 rounds × 5 seeds | Shared heterogeneous traces |

The fuzzy matrix file is a batch protocol, not a single-experiment API body. See the [F1–F5 launch and result instructions](docs/controlled-matrix.md#nhóm-f--fmcdm-client-selection) and [mathematical specification](docs/fuzzy-mcdm-client-selection.md).

Each new run requires a unique `experimentId`. To continue a `FAILED` or `INTERRUPTED` run, use its original configuration with `--resume`:

```powershell
.\.venv\Scripts\python -m minifls.experiment configurations/fedavg.json --resume
Invoke-RestMethod http://127.0.0.1:8080/experiments
```

To start services manually, create the `artifacts` directory first and use two terminals:

```powershell
# Terminal 1, from the repository root; always use --workers 1.
.\.venv\Scripts\python -m uvicorn minifls.api:app --host 127.0.0.1 --port 8000 --workers 1

# Terminal 2
cd ferderatedsystem
.\gradlew.bat bootRun
```

To stop services started by the script, run `powershell -ExecutionPolicy Bypass -File scripts/stop.ps1`. The stop script checks process identities before terminating services and their child processes. Environment settings: `MINIFLS_WORKSPACE`, `MINIFLS_WORKER_URL`, `MINIFLS_SERVER_PORT`, `MINIFLS_DATABASE`, and `MINIFLS_TORCH_THREADS`.

## Results and validation

Java and Python now log experiment/round/client progress, per-epoch training loss,
aggregation, server evaluation metrics and failures. Set `MINIFLS_LOG_LEVEL=DEBUG`
in both processes for detailed diagnostics; see [logging guide](docs/logging.md).

The SQLite database is stored at `artifacts/minifls.db`. The CLI exports `experiment.json`, `rounds.json`, and `metrics.csv` under `artifacts/results/<experimentId>/`. Snapshots include the manifest, Git commit, checkpoint, and client histories; the experiment record also stores the configuration. Round JSON includes selection decisions, statuses, model versions, weights, proxy losses, test metrics, physical wall time, and virtual time.

```powershell
.\.venv\Scripts\python -m minifls.plot artifacts/results/covertype-fedavg-42/metrics.csv
.\.venv\Scripts\python -m minifls.benchmark artifacts/partitions/covertype-iid-42 --epochs 5
.\.venv\Scripts\python -m pytest ml-python/tests -q
Push-Location ferderatedsystem
.\gradlew.bat test bootJar --no-daemon
Pop-Location
.\.venv\Scripts\python scripts/verify_e2e.py
```

The integration test starts services on separate ports, runs 100 clients for 20 rounds, checks exclusion of OOM/dropout/timeout updates, exercises FedLBW, and verifies crash recovery. CI runs the same checks on Linux.

CPU and RAM constraints are **virtual simulation**. Measured RSS belongs to the entire worker process. CPU scaling, `requiredRamMb`, and cold-start priors require benchmark calibration before drawing conclusions about resource efficiency. Virtual time depends on measured training duration; a fixed seed does not guarantee identical wall times. Logical clients do not require 100 processes or containers.

Fuzzy TOPSIS, fairness credit and adaptive fairness selectors are available through `MINIFLS_METHOD=fuzzy_matrix`; see [formulas, parameters, F1–F5 protocol and smoke validation](docs/fuzzy-mcdm-client-selection.md). FedProx, Oort, Lyapunov optimization and WAN emulation remain research extensions.

Further details: [architecture](docs/architecture.md), [API](docs/api-contract.md), [experiment protocol and requirement coverage](docs/experiment-protocol.md), and [validation results](docs/validation/README.md).
