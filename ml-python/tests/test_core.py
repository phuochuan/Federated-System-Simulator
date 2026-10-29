import json
import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from minifls import api
from minifls.data import Dataset, partition, prepare
from minifls.model import ARCHITECTURE, ARCHITECTURES, model, weighted_average, load_checkpoint, schema_hash, state_hash
from minifls.simulation import simulate_round


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ROOT", tmp_path)
    monkeypatch.delenv("MINIFLS_MODEL_ARCHITECTURE", raising=False)
    api.datasets.clear()
    prepare(tmp_path / "dataset", dataset="synthetic", clients=10, samples=1400)
    return TestClient(api.app)


def test_partition_disjoint_reproducible_and_sizes():
    y = np.tile(np.arange(7), 200)
    for strategy in ["iid_equal", "iid_quantity_skew", "dirichlet_label_skew", "dirichlet_mixed_skew"]:
        a = partition(y, 10, strategy, .5, 42)
        b = partition(y, 10, strategy, .5, 42)
        assert all(np.array_equal(x, z) for x, z in zip(a, b))
        assert np.array_equal(np.sort(np.concatenate(a)), np.arange(len(y)))
        assert min(map(len, a)) > 0


def test_splits_and_train_only_scaler(client):
    data = Dataset(api.ROOT / "dataset")
    train, proxy, test = (set(data.splits[k]) for k in ["train", "proxy", "test"])
    assert not (train & proxy or train & test or test & proxy)
    assert set(np.concatenate(list(data.partitions.values()))) == train
    assert np.max(abs(data.x[data.splits["train"]].mean(0))) < 1e-5
    assert data.y.min() == 0 and data.y.max() == 6
    assert sum(p.numel() for p in model().parameters()) == 47879


def test_aggregation_hand_calculation_and_rejections():
    a = {k: torch.ones_like(v) for k, v in model().state_dict().items()}
    b = {k: torch.ones_like(v) * 3 for k, v in model().state_dict().items()}
    assert all(torch.equal(v, torch.full_like(v, 2.5)) for v in weighted_average([a,b], [.25,.75]).values())
    for states, weights in [([], []), ([a,b],[.5,.6]), ([a],[-1]), ([a],[float("nan")])]:
        with pytest.raises(ValueError):
            weighted_average(states, weights)
    b["0.weight"][0,0] = float("inf")
    with pytest.raises(ValueError):
        weighted_average([a,b], [.5,.5])


def test_virtual_parallel_deadline_oom_dropout():
    jobs = [dict(clientId=i, actualTrainingMs=t, cpu=1, ramMb=1024, requiredRamMb=600)
            for i,t in enumerate([2000,5000])]
    result = simulate_round(jobs,42)
    assert result["virtualRoundSeconds"] == 5  # Lấy thời gian lớn nhất khi chạy song song, không lấy tổng.
    result = simulate_round(jobs,42,deadline=3)
    assert [r["status"] for r in result["results"]] == ["COMPLETED","TIMEOUT"]
    jobs[0]["ramMb"] = 512
    result = simulate_round(jobs,42,dropout=1)
    assert [r["status"] for r in result["results"]] == ["SIMULATED_OOM","DROPPED"]
    assert result == simulate_round(jobs,42,dropout=1)


def test_fixed_duration_ignores_wall_clock_but_retains_trace_and_cpu_scaling():
    job = dict(clientId=0, actualTrainingMs=1, simulatedTrainingMs=4000, cpu=2,
               ramMb=1024, requiredRamMb=600, jitterMultiplier=1.1, dropoutEvent=False)
    a = simulate_round([job], 45)
    b = simulate_round([{**job, "actualTrainingMs": 999999}], 45)
    assert a == b
    assert a["virtualRoundSeconds"] == pytest.approx(2.2)
    assert simulate_round([job], 45, deadline=2)["results"][0]["status"] == "TIMEOUT"


def test_partition_seed_does_not_change_pools_or_scaler(tmp_path):
    a = prepare(tmp_path / "a", dataset="synthetic", samples=1400, clients=10,
                strategy="dirichlet_label_skew", partition_seed=1001)
    b = prepare(tmp_path / "b", dataset="synthetic", samples=1400, clients=10,
                strategy="dirichlet_label_skew", partition_seed=1002)
    for name in ("features.npy", "labels.npy", "splits.npz"):
        assert a["hashes"][name] == b["hashes"][name]
    assert a["hashes"]["partitions.npz"] != b["hashes"]["partitions.npz"]
    assert a["scaler"] == b["scaler"]


def test_runtime_provenance_and_partition_prepare_reuse(client):
    runtime = client.get("/runtime").json()
    assert runtime["executionDevice"] == "cpu" and runtime["sourceFilesUnchanged"]
    assert runtime["idempotentCheckpointOperations"]
    assert runtime["packages"]["torch"] and "api.py" in runtime["sourceHashes"]
    request = dict(output="new-partition", dataset="synthetic", clients=100, seed=42, partitionSeed=1001)
    first = client.post("/datasets/prepare", json=request)
    assert first.status_code == 200, first.text
    repeated = client.post("/datasets/prepare", json=request)
    assert first.json() == repeated.json()
    assert client.post("/datasets/prepare", json={**request, "partitionSeed": 1002}).status_code == 400
    assert client.post("/datasets/prepare", json={**request, "output": "../outside"}).status_code == 400


def test_checkpoint_operations_replay_exact_durable_responses(client, monkeypatch):
    context = dict(experimentId="retry", manifestPath="dataset", seed=42, operationId="round-operation")
    initial = client.post("/models/initialize", json=context)
    assert initial.status_code == 200, initial.text
    initial_stat = api.path(initial.json()["checkpointPath"]).stat().st_mtime_ns
    assert client.post("/models/initialize", json=context).json() == initial.json()
    assert api.path(initial.json()["checkpointPath"]).stat().st_mtime_ns == initial_stat
    request = dict(**context, roundId=1, clientId=0, baseModelVersion=0, globalModelPath=initial.json()["checkpointPath"])
    trained = client.post("/train", json=request)
    assert trained.status_code == 200, trained.text
    target = api.path(trained.json()["updatePath"])
    timestamp = target.stat().st_mtime_ns
    api.datasets.clear()  # Receipts do not rely on an in-memory operation cache.
    with monkeypatch.context() as patch:
        def unexpected_model(*args, **kwargs):
            raise AssertionError("A replay must not train again")
        patch.setattr(api, "model", unexpected_model)
        replay = client.post("/train", json=request)
    assert replay.status_code == 200, replay.text
    assert replay.json() == trained.json()  # Includes original actualTrainingMs and tensor hash.
    assert target.stat().st_mtime_ns == timestamp
    aggregate = dict(**context, roundId=1, baseModelVersion=0, updates=[trained.json()["updatePath"]], weights=[1.0])
    combined = client.post("/models/aggregate", json=aggregate)
    assert combined.status_code == 200, combined.text
    with monkeypatch.context() as patch:
        patch.setattr(api, "weighted_average", unexpected_model)
        assert client.post("/models/aggregate", json=aggregate).json() == combined.json()
    assert len(list(api.path("artifacts/models/retry").glob("*.pt"))) == 3
    assert client.post("/train", json={**request, "seed": 43}).status_code == 409
    assert client.post("/models/aggregate", json={**aggregate, "weights": [.5]}).status_code == 409


def test_missing_or_corrupt_receipt_fails_without_overwriting_checkpoint(client):
    from minifls.operations import receipt_path
    context = dict(experimentId="receipt", manifestPath="dataset", seed=42)
    initial = client.post("/models/initialize", json=context).json()
    target = api.path(initial["checkpointPath"])
    before = target.read_bytes()
    receipt = receipt_path(target)
    payload = json.loads(receipt.read_text())
    payload["response"]["modelStateHash"] = "corrupt"
    receipt.write_text(json.dumps(payload))
    assert client.post("/models/initialize", json=context).status_code == 400
    receipt.unlink()
    failure = client.post("/models/initialize", json=context)
    assert failure.status_code == 409 and "without a committed response" in failure.text
    assert target.read_bytes() == before


@pytest.mark.parametrize("architecture", list(ARCHITECTURES))
def test_api_round_and_no_cross_client_state(client, architecture):
    context = dict(experimentId="test", manifestPath="dataset", seed=42)
    initial = client.post("/models/initialize",json={**context,"architecture":architecture}).json()
    assert initial["architecture"] == architecture
    request = dict(**context, roundId=1, clientId=0, baseModelVersion=0, globalModelPath=initial["checkpointPath"])
    first = client.post("/train",json=request)
    assert first.status_code == 200, first.text
    assert first.json()["architecture"] == architecture
    # Train client khác không được làm thay đổi kết quả khi lặp lại job từ cùng checkpoint gốc.
    other = client.post("/train",json={**request,"clientId":1}).json()
    again = client.post("/train",json={**request,"operationId":"repeat"}).json()
    state = load_checkpoint(api.path(first.json()["updatePath"]))["state"]
    repeated = load_checkpoint(api.path(again["updatePath"]))["state"]
    assert all(torch.equal(state[k],repeated[k]) for k in state)
    assert first.json()["modelStateHash"] == again["modelStateHash"] == state_hash(state)
    aggregate = {**context,"roundId":1,"baseModelVersion":0,
                 "updates":[first.json()["updatePath"],other["updatePath"]],"weights":[.5,.5]}
    result = client.post("/models/aggregate",json=aggregate)
    assert result.status_code == 200, result.text
    assert result.json()["modelVersion"] == 1
    assert result.json()["architecture"] == architecture
    assert load_checkpoint(api.path(result.json()["checkpointPath"]))["architecture"] == architecture
    evaluation = client.post("/models/evaluate",json=dict(checkpointPath=result.json()["checkpointPath"],manifestPath="dataset"))
    assert evaluation.status_code == 200
    assert evaluation.json()["architecture"] == architecture
    assert len(evaluation.json()["perClassRecall"]) == 7
    assert evaluation.json()["modelStateHash"] == result.json()["modelStateHash"]
    assert evaluation.json()["split"] == "test"
    assert client.post("/models/aggregate",json={**aggregate,"roundId":2,"operationId":"bad-round"}).status_code == 400
    assert client.post("/models/aggregate",json={**aggregate,"updates":[first.json()["updatePath"]]*2,"operationId":"bad-duplicates"}).status_code == 400
    assert client.post("/train",json={**request,"baseModelVersion":1,"operationId":"bad-version"}).status_code == 400


def test_worker_busy_and_path_boundary(client):
    api.lock.acquire()
    try:
        assert client.post("/models/initialize",json=dict(experimentId="test",manifestPath="dataset",seed=42)).status_code == 409
    finally:
        api.lock.release()
    assert client.get("/datasets/manifest",params={"manifestPath":"../outside"}).status_code == 400
    assert client.post("/models/initialize",json=dict(experimentId="../bad",manifestPath="dataset",seed=42)).status_code == 422


def test_checksum_detects_mutated_data(client):
    path = api.ROOT / "dataset" / "labels.npy"
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError,match="checksum"):
        Dataset(api.ROOT / "dataset")


def test_architecture_default_environment_override_and_validation(client, monkeypatch):
    context = dict(experimentId="architecture", manifestPath="dataset", seed=42)
    default = client.post("/models/initialize", json=context)
    assert default.status_code == 200
    assert default.json()["architecture"] == ARCHITECTURE
    state = load_checkpoint(api.path(default.json()["checkpointPath"]))["state"]
    assert state["0.weight"].shape == (256, 54)
    assert state["2.weight"].shape == (128, 256)
    assert state["4.weight"].shape == (7, 128)
    monkeypatch.setenv("MINIFLS_MODEL_ARCHITECTURE", "mlp_54_128_64_7")
    small = client.post("/models/initialize", json={**context,"operationId":"small"})
    assert small.status_code == 200
    assert small.json()["architecture"] == "mlp_54_128_64_7"
    # Explicit request takes precedence over the worker's default.
    explicit = client.post("/models/initialize", json={**context,"operationId":"large","architecture":ARCHITECTURE})
    assert explicit.json()["architecture"] == ARCHITECTURE
    monkeypatch.setenv("MINIFLS_MODEL_ARCHITECTURE", "typo")
    assert client.post("/models/initialize", json=context).status_code == 422
    assert client.post("/models/initialize", json={**context,"architecture":"typo"}).status_code == 422


def test_mixed_architectures_cannot_aggregate(client):
    context = dict(experimentId="mixed", manifestPath="dataset", seed=42)
    updates = []
    for client_id, architecture in enumerate(ARCHITECTURES):
        initial = client.post("/models/initialize", json={**context,"architecture":architecture,"operationId":architecture}).json()
        update = client.post("/train", json={**context,"roundId":1,"clientId":client_id,"baseModelVersion":0,
                                             "globalModelPath":initial["checkpointPath"]})
        assert update.status_code == 200, update.text
        updates.append(update.json()["updatePath"])
    result = client.post("/models/aggregate", json={**context,"roundId":1,"baseModelVersion":0,
                                                   "updates":updates,"weights":[.5,.5]})
    assert result.status_code == 400
    assert "different architectures" in result.json()["detail"]


def test_legacy_checkpoint_format_is_supported_and_architecture_is_checked(tmp_path):
    state = model("mlp_54_128_64_7").state_dict()
    legacy = dict(state=state, architecture="mlp_54_128_64_7", modelSchemaHash=schema_hash(state),
                  experimentId="old-run", modelVersion=1)
    checkpoint = tmp_path / "legacy.pt"
    torch.save(legacy, checkpoint)
    assert load_checkpoint(checkpoint)["architecture"] == "mlp_54_128_64_7"
    # Matching schema hash alone must not allow a falsely labelled architecture.
    torch.save({**legacy,"architecture":ARCHITECTURE}, checkpoint)
    with pytest.raises(ValueError, match="Invalid tensor"):
        load_checkpoint(checkpoint)
    torch.save({**legacy,"architecture":"unknown"}, checkpoint)
    with pytest.raises(ValueError, match="Architecture mismatch"):
        load_checkpoint(checkpoint)


def test_initialization_fingerprint_measures_actual_tensor_values(client):
    context = dict(experimentId="fingerprint", manifestPath="dataset", seed=42)
    first = client.post("/models/initialize", json=context).json()
    second = client.post("/models/initialize", json={**context,"operationId":"repeat"}).json()
    changed = client.post("/models/initialize", json={**context,"seed":43,"operationId":"changed"}).json()
    assert first["modelStateHash"] == second["modelStateHash"] != changed["modelStateHash"]
    assert first["initializationMethod"] == "pytorch-default-linear-v1"
    assert first["modelPayloadBytes"] == 47879 * 4
    checkpoint = load_checkpoint(api.path(first["checkpointPath"]))
    checkpoint["state"]["0.weight"][0,0] += 1
    torch.save(checkpoint, api.path(first["checkpointPath"]))
    with pytest.raises(ValueError, match="state hash"):
        load_checkpoint(api.path(first["checkpointPath"]))


def test_explicit_dropout_jitter_trace_replays_across_order_and_oom():
    jobs = [dict(clientId=0, actualTrainingMs=1000, cpu=1, ramMb=512, requiredRamMb=600,
                 dropoutEvent=False, jitterMultiplier=1.1),
            dict(clientId=1, actualTrainingMs=2000, cpu=1, ramMb=1024, requiredRamMb=600,
                 dropoutEvent=True, jitterMultiplier=.9),
            dict(clientId=2, actualTrainingMs=4000, cpu=1, ramMb=1024, requiredRamMb=600,
                 dropoutEvent=False, jitterMultiplier=1.5)]
    first = simulate_round(jobs,42,deadline=3,dropout=0,jitter=.1)
    second = simulate_round(list(reversed(jobs)),99,deadline=3,dropout=1,jitter=.1)
    assert first == second
    assert [r["status"] for r in first["results"]] == ["SIMULATED_OOM","DROPPED","TIMEOUT"]
    assert first["results"][1]["virtualTrainingSeconds"] == 1.8
