"""API HTTP cục bộ cho ML; phải chạy đúng một uvicorn worker."""
from contextlib import contextmanager
import os
from pathlib import Path
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
import psutil
from pydantic import BaseModel, ConfigDict, Field
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .data import Dataset
from .model import load_checkpoint, model, save_checkpoint, weighted_average
from .simulation import simulate_round
from .methods import METHODS, catalog, get_method

torch.set_num_threads(int(os.environ.get("MINIFLS_TORCH_THREADS", "1")))
torch.use_deterministic_algorithms(True)
ROOT = Path(os.environ.get("MINIFLS_WORKSPACE", Path(__file__).resolve().parents[2])).resolve()
app = FastAPI(title="MiniFLS ML Worker", version="0.1.0")
lock = threading.Lock()
datasets = {}


class Strict(BaseModel):
    # Từ chối trường thừa và NaN/Inf để phát hiện sớm cấu hình sai từ Java.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Experiment(Strict):
    experimentId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    manifestPath: str
    seed: int = Field(ge=0, le=2147483647)
    operationId: str = Field(default="initial", pattern=r"^[A-Za-z0-9_-]{1,80}$")


class Training(Strict):
    epochs: int = Field(default=1, ge=1, le=100)
    batchSize: int = Field(default=32, ge=1, le=65536)
    learningRate: float = Field(default=.01, gt=0, le=10)


class Train(Experiment):
    roundId: int = Field(ge=1)
    clientId: int = Field(ge=0)
    baseModelVersion: int = Field(ge=0)
    globalModelPath: str
    training: Training = Field(default_factory=Training)


class Evaluate(Strict):
    checkpointPath: str
    manifestPath: str
    split: str = Field(default="test", pattern="^(test|proxy|train)$")


class Aggregate(Experiment):
    roundId: int = Field(ge=1)
    baseModelVersion: int = Field(ge=0)
    updates: list[str] = Field(min_length=1)
    weights: list[float] = Field(min_length=1)


class MethodWeights(Strict):
    samples: list[int] = Field(min_length=1)
    losses: list[float] = Field(default_factory=list)


class Job(Strict):
    clientId: int = Field(ge=0)
    actualTrainingMs: float = Field(ge=0)
    cpu: float = Field(gt=0)
    ramMb: float = Field(gt=0)
    requiredRamMb: float = Field(gt=0)


class Simulation(Strict):
    jobs: list[Job]
    seed: int
    deadline: float | None = Field(default=None, gt=0)
    enabled: bool = True
    dropout: float = Field(default=0, ge=0, le=1)
    jitter: float = Field(default=0, ge=0, lt=1)


def path(value):
    # Resolve cả đường dẫn tương đối và symlink trước khi kiểm tra phạm vi workspace.
    resolved = (ROOT / value).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("Artifact path must stay within workspace")
    return resolved


def dataset(value):
    resolved = path(value)
    if resolved not in datasets:
        datasets.clear()  # Chỉ giữ dataset đang dùng trong worker chạy lâu dài.
        datasets[resolved] = Dataset(resolved)
    return datasets[resolved]


def artifact(experiment, name):
    return path(f"artifacts/models/{experiment}/{name}.pt")


def relative(value):
    return value.relative_to(ROOT).as_posix()


@contextmanager
def exclusive():
    # Khóa chung cho các thao tác ML; trả 409 ngay nếu worker đang bận.
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "Worker busy; only one active ML operation allowed")
    try:
        yield
    finally:
        lock.release()


@app.exception_handler(ValueError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FileNotFoundError)
async def missing_file(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Dataset or model artifact not found"})


@app.get("/health")
def health():
    return dict(status="ok", maxActiveTraining=1, busy=lock.locked(), torchThreads=torch.get_num_threads())


@app.get("/methods")
def methods():
    return {"methods": list(METHODS), "catalog": catalog()}


@app.post("/methods/{method}/weights")
def method_weights(method: str, req: MethodWeights):
    try:
        implementation = get_method(method)
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    return {"method": method, "weights": implementation.weights(req.samples, req.losses)}


@app.get("/datasets/manifest")
def manifest(manifestPath: str):
    with exclusive():
        return dataset(manifestPath).manifest


@app.post("/models/initialize")
def initialize(req: Experiment):
    with exclusive():
        dataset(req.manifestPath)
        torch.manual_seed(req.seed)
        state = model().state_dict()
        target = artifact(req.experimentId, f"global_0000_{req.operationId}")
        save_checkpoint(target, state, experimentId=req.experimentId, modelVersion=0)
        return dict(checkpointPath=relative(target), modelVersion=0)


def loader(data, indices, batch_size, shuffle=False, seed=0):
    # Chỉ đưa partition đang xử lý vào tensor, không nhân bản toàn dataset cho mỗi client.
    tensors = TensorDataset(torch.from_numpy(np.array(data.x[indices])), torch.from_numpy(np.array(data.y[indices])))
    return DataLoader(tensors, batch_size=batch_size, shuffle=shuffle, num_workers=0,
                      generator=torch.Generator().manual_seed(seed))


@app.post("/train")
def train(req: Train):
    with exclusive():
        started = time.perf_counter()
        data = dataset(req.manifestPath)
        if req.clientId not in data.partitions:
            raise ValueError("Unknown client")
        checkpoint = load_checkpoint(path(req.globalModelPath))
        if checkpoint["experimentId"] != req.experimentId or checkpoint["modelVersion"] != req.baseModelVersion:
            raise ValueError("Base checkpoint experiment/version mismatch")
        torch.manual_seed(req.seed)
        network = model()
        # Mỗi client bắt đầu từ checkpoint được Java cố định cho round hiện tại.
        network.load_state_dict(checkpoint["state"])
        network.train()
        # Tạo optimizer mới để state huấn luyện không truyền từ client trước sang client sau.
        optimizer = torch.optim.SGD(network.parameters(), lr=req.training.learningRate)
        batches = loader(data, data.partitions[req.clientId], req.training.batchSize, True, req.seed)
        total_loss, count = 0.0, 0
        for _ in range(req.training.epochs):
            for x, y in batches:
                optimizer.zero_grad(set_to_none=True)
                loss = nn.functional.cross_entropy(network(x), y)
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite training loss")
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(y)
                count += len(y)
        target = artifact(req.experimentId, f"r{req.roundId:04}_client{req.clientId:03}_{req.operationId}")
        metadata = dict(experimentId=req.experimentId, roundId=req.roundId, clientId=req.clientId,
                        baseModelVersion=req.baseModelVersion, numSamples=len(data.partitions[req.clientId]))
        save_checkpoint(target, network.state_dict(), **metadata)
        # RSS thuộc toàn process worker, không đại diện RAM của một thiết bị ảo.
        memory = psutil.Process().memory_info()
        return dict(**metadata, modelSchemaHash=checkpoint["modelSchemaHash"], updatePath=relative(target),
                    trainingLoss=total_loss / count, actualTrainingMs=(time.perf_counter() - started) * 1000,
                    workerRssMb=memory.rss / 2**20,
                    workerPeakRssMb=getattr(memory, "peak_wset", memory.rss) / 2**20,
                    status="TRAINING_COMPLETED")


@app.post("/models/evaluate")
def evaluate(req: Evaluate):
    with exclusive():
        started = time.perf_counter()
        data = dataset(req.manifestPath)
        checkpoint = load_checkpoint(path(req.checkpointPath))
        network = model()
        network.load_state_dict(checkpoint["state"])
        network.eval()
        predicted, actual, loss = [], [], 0.0
        # Đánh giá không cập nhật trọng số; proxy và test có mục đích riêng do Java chọn.
        with torch.no_grad():
            for x, y in loader(data, data.splits[req.split], 1024):
                logits = network(x)
                loss += nn.functional.cross_entropy(logits, y, reduction="sum").item()
                predicted.extend(logits.argmax(1).tolist())
                actual.extend(y.tolist())
        precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, labels=list(range(7)), zero_division=0)
        return dict(loss=loss / len(actual), accuracy=accuracy_score(actual, predicted), macroF1=float(f1.mean()),
                    perClassPrecision=precision.tolist(), perClassRecall=recall.tolist(), worstClassRecall=float(recall.min()),
                    confusionMatrix=confusion_matrix(actual, predicted, labels=list(range(7))).tolist(),
                    evaluationMs=(time.perf_counter() - started) * 1000)


@app.post("/models/aggregate")
def aggregate(req: Aggregate):
    with exclusive():
        # Kiểm tra lại artifact dù Java đã lọc metadata của các update được chấp nhận.
        checkpoints = [load_checkpoint(path(p)) for p in req.updates]
        ids = [c["clientId"] for c in checkpoints]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate client update")
        for c in checkpoints:
            if (c["experimentId"], c["roundId"], c["baseModelVersion"]) != (req.experimentId, req.roundId, req.baseModelVersion):
                raise ValueError("Stale or foreign update")
        state = weighted_average([c["state"] for c in checkpoints], req.weights)
        target = artifact(req.experimentId, f"global_{req.baseModelVersion + 1:04}_{req.operationId}")
        save_checkpoint(target, state, experimentId=req.experimentId, modelVersion=req.baseModelVersion + 1)
        return dict(checkpointPath=relative(target), modelVersion=req.baseModelVersion + 1)


@app.post("/simulation/round")
def simulation(req: Simulation):
    return simulate_round(**req.model_dump())
