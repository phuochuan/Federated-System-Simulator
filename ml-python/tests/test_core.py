import json
import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from minifls import api
from minifls.data import Dataset, partition, prepare
from minifls.model import model, weighted_average, load_checkpoint
from minifls.simulation import simulate_round


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ROOT", tmp_path)
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
    assert sum(p.numel() for p in model().parameters()) == 15751


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


def test_api_round_and_no_cross_client_state(client):
    context = dict(experimentId="test", manifestPath="dataset", seed=42)
    initial = client.post("/models/initialize",json=context).json()
    request = dict(**context, roundId=1, clientId=0, baseModelVersion=0, globalModelPath=initial["checkpointPath"])
    first = client.post("/train",json=request)
    assert first.status_code == 200, first.text
    # Train client khác không được làm thay đổi kết quả khi lặp lại job từ cùng checkpoint gốc.
    other = client.post("/train",json={**request,"clientId":1}).json()
    again = client.post("/train",json={**request,"operationId":"repeat"}).json()
    state = load_checkpoint(api.path(first.json()["updatePath"]))["state"]
    repeated = load_checkpoint(api.path(again["updatePath"]))["state"]
    assert all(torch.equal(state[k],repeated[k]) for k in state)
    aggregate = {**context,"roundId":1,"baseModelVersion":0,
                 "updates":[first.json()["updatePath"],other["updatePath"]],"weights":[.5,.5]}
    result = client.post("/models/aggregate",json=aggregate)
    assert result.status_code == 200, result.text
    assert result.json()["modelVersion"] == 1
    evaluation = client.post("/models/evaluate",json=dict(checkpointPath=result.json()["checkpointPath"],manifestPath="dataset"))
    assert evaluation.status_code == 200
    assert len(evaluation.json()["perClassRecall"]) == 7
    assert client.post("/models/aggregate",json={**aggregate,"roundId":2}).status_code == 400
    assert client.post("/models/aggregate",json={**aggregate,"updates":[first.json()["updatePath"]]*2}).status_code == 400
    assert client.post("/train",json={**request,"baseModelVersion":1}).status_code == 400


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
