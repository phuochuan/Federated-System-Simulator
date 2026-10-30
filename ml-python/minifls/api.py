"""API HTTP cục bộ cho ML; phải chạy đúng một uvicorn worker."""
from contextlib import contextmanager
import os
import sys
import platform
import hashlib
import importlib.metadata
import logging
from pathlib import Path
import threading
import time
from typing import Literal

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
from .model import ARCHITECTURE, load_checkpoint, model, save_checkpoint, weighted_average, state_hash, payload_bytes
from .simulation import simulate_round
from .operations import cached_response, commit_response, request_hash
from .methods import METHODS, catalog, get_method
from .logging_config import logged_operation, log_context, set_log_context

log = logging.getLogger(__name__)

torch.set_num_threads(int(os.environ.get("MINIFLS_TORCH_THREADS", "1")))
torch.use_deterministic_algorithms(True)
ROOT = Path(os.environ.get("MINIFLS_WORKSPACE", Path(__file__).resolve().parents[2])).resolve()
RUNTIME_SOURCE_HASHES = {p.relative_to(Path(__file__).parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(Path(__file__).parent.rglob("*.py"))}
app = FastAPI(title="MiniFLS ML Worker", version="0.1.0")
lock = threading.Lock()
datasets = {}
log.info("worker.configured workspace=%s torchThreads=%s defaultArchitecture=%s", ROOT, torch.get_num_threads(),
         os.environ.get("MINIFLS_MODEL_ARCHITECTURE", ARCHITECTURE))


@app.middleware("http")
async def request_logging(request, call_next):
    with log_context(experiment=request.headers.get("X-MiniFLS-Experiment", "-"),
                     round_id=request.headers.get("X-MiniFLS-Round", "-"),
                     client_id=request.headers.get("X-MiniFLS-Client", "-"),
                     attempt=request.headers.get("X-MiniFLS-Attempt", "-")):
        started = time.perf_counter()
        log.debug("http.started method=%s path=%s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            log.exception("http.failed method=%s path=%s", request.method, request.url.path)
            raise
        log.log(logging.WARNING if response.status_code >= 400 else logging.DEBUG,
                "http.completed method=%s path=%s status=%s elapsedMs=%.2f", request.method,
                request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
        return response


class Strict(BaseModel):
    # Từ chối trường thừa và NaN/Inf để phát hiện sớm cấu hình sai từ Java.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Experiment(Strict):
    experimentId: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    manifestPath: str
    seed: int = Field(ge=0, le=2147483647)
    operationId: str = Field(default="initial", pattern=r"^[A-Za-z0-9_-]{1,80}$")


class Initialize(Experiment):
    # Chỉ chọn kiến trúc lúc tạo model; train/resume luôn theo checkpoint đã lưu.
    architecture: Literal["mlp_54_128_64_7", "mlp_54_256_128_7"] = Field(
        default_factory=lambda: os.environ.get("MINIFLS_MODEL_ARCHITECTURE", ARCHITECTURE), validate_default=True)


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
    simulatedTrainingMs: float | None = Field(default=None, ge=0)
    cpu: float = Field(gt=0)
    ramMb: float = Field(gt=0)
    requiredRamMb: float = Field(gt=0)
    dropoutEvent: bool | None = None
    jitterMultiplier: float | None = Field(default=None, gt=0, lt=2)


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
        started = time.perf_counter()
        log.info("dataset.loading manifest=%s", value)
        datasets.clear()  # Chỉ giữ dataset đang dùng trong worker chạy lâu dài.
        datasets[resolved] = Dataset(resolved)
        log.info("dataset.loaded dataset=%s clients=%s counts=%s elapsedMs=%.2f", datasets[resolved].manifest["dataset"],
                 datasets[resolved].manifest["totalClients"], datasets[resolved].manifest["counts"], (time.perf_counter() - started) * 1000)
    return datasets[resolved]


def artifact(experiment, name):
    return path(f"artifacts/models/{experiment}/{name}.pt")


def relative(value):
    return value.relative_to(ROOT).as_posix()


@contextmanager
def exclusive():
    # Khóa chung cho các thao tác ML; trả 409 ngay nếu worker đang bận.
    if not lock.acquire(blocking=False):
        log.warning("worker.busy requestRejected=true")
        raise HTTPException(409, "Worker busy; only one active ML operation allowed")
    try:
        yield
    finally:
        lock.release()


@app.exception_handler(ValueError)
async def invalid_request(request, exc):
    log.warning("request.invalid method=%s path=%s error=%s", request.method, request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FileNotFoundError)
async def missing_file(request, exc):
    log.warning("artifact.missing method=%s path=%s file=%s", request.method, request.url.path, exc.filename)
    return JSONResponse(status_code=404, content={"detail": "Dataset or model artifact not found"})


@app.get("/health")
def health():
    return dict(status="ok", apiVersion="fuzzy-research-v1", maxActiveTraining=1, busy=lock.locked(), torchThreads=torch.get_num_threads())


@app.get("/runtime")
def runtime():
    package_root = Path(__file__).parent
    sources = {p.relative_to(package_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(package_root.rglob("*.py"))}
    return dict(apiVersion="fuzzy-research-v1", python=sys.version, platform=platform.platform(), executionDevice="cpu",
                idempotentCheckpointOperations=True,
                torchThreads=torch.get_num_threads(), torchInteropThreads=torch.get_num_interop_threads(),
                deterministicAlgorithms=torch.are_deterministic_algorithms_enabled(),
                packages={name: importlib.metadata.version(name) for name in
                          ("torch", "numpy", "scikit-learn", "simpy", "fastapi", "uvicorn")},
                sourceHashes=RUNTIME_SOURCE_HASHES, sourceFilesUnchanged=sources == RUNTIME_SOURCE_HASHES)


class PrepareDataset(Strict):
    output: str
    dataset: Literal["covertype", "synthetic"] = "covertype"
    clients: int = Field(default=100, ge=1)
    seed: int = Field(default=42, ge=0)
    partitionSeed: int = Field(ge=0)
    alpha: float = Field(default=.5, gt=0)


@app.post("/datasets/prepare")
def prepare_dataset(req: PrepareDataset):
    from .data import prepare
    with exclusive():
        directory = path(req.output)
        if not directory.exists():
            prepare(directory, dataset=req.dataset, clients=req.clients, seed=req.seed,
                    partition_seed=req.partitionSeed, strategy="dirichlet_label_skew", alpha=req.alpha)
        data = Dataset(directory)  # Validate current hashes even when a directory already exists.
        expected = dict(dataset=req.dataset, totalClients=req.clients, seed=req.seed,
                        partitionSeed=req.partitionSeed, strategy="dirichlet_label_skew", alpha=req.alpha)
        if any(data.manifest.get(k) != value for k, value in expected.items()):
            raise ValueError("Existing partition manifest does not match requested partition protocol")
        return data.manifest


class ResearchPlotRequest(Strict):
    resultsPath: str


@app.post("/reports/research/plots")
def research_plots(req: ResearchPlotRequest):
    from .research_plot import plot_report
    with exclusive():
        return {"files": plot_report(path(req.resultsPath))}


@app.get("/methods")
def methods():
    return {"methods": list(METHODS), "catalog": catalog()}


@app.post("/methods/{method}/weights")
@logged_operation("weights")
def method_weights(method: str, req: MethodWeights):
    try:
        implementation = get_method(method)
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    weights = implementation.weights(req.samples, req.losses)
    log.info("weights.calculated method=%s accepted=%s samples=%s proxyLosses=%s weights=%s", method, len(req.samples), req.samples, req.losses, weights)
    return {"method": method, "weights": weights}


@app.get("/datasets/manifest")
def manifest(manifestPath: str, verify: bool = False):
    with exclusive():
        if verify:
            resolved = path(manifestPath)
            checked = Dataset(resolved)
            datasets.clear()
            datasets[resolved] = checked
        return dataset(manifestPath).manifest


@app.post("/models/initialize")
@logged_operation("initialize")
def initialize(req: Initialize):
    with exclusive():
        target = artifact(req.experimentId, f"global_0000_{req.operationId}")
        cached = cached_response(req, target)
        if cached is not None:
            log.info("operation.replayed operation=initialize experiment=%s operationId=%s", req.experimentId, req.operationId)
            return cached
        dataset(req.manifestPath)
        torch.manual_seed(req.seed)
        state = model(req.architecture).state_dict()
        save_checkpoint(target, state, architecture=req.architecture, experimentId=req.experimentId, modelVersion=0,
                        operationRequestHash=request_hash(req))
        log.info("model.initialized architecture=%s parameters=%s seed=%s checkpoint=%s", req.architecture,
                 sum(t.numel() for t in state.values()), req.seed, relative(target))
        response = dict(checkpointPath=relative(target), modelVersion=0, architecture=req.architecture,
                    modelStateHash=state_hash(state), modelPayloadBytes=payload_bytes(state),
                    initializationMethod="pytorch-default-linear-v1", initializationSeed=req.seed)
        return commit_response(req, target, response)


def loader(data, indices, batch_size, shuffle=False, seed=0):
    # Chỉ đưa partition đang xử lý vào tensor, không nhân bản toàn dataset cho mỗi client.
    tensors = TensorDataset(torch.from_numpy(np.array(data.x[indices])), torch.from_numpy(np.array(data.y[indices])))
    return DataLoader(tensors, batch_size=batch_size, shuffle=shuffle, num_workers=0,
                      generator=torch.Generator().manual_seed(seed))


@app.post("/train")
@logged_operation("train")
def train(req: Train):
    with exclusive():
        target = artifact(req.experimentId, f"r{req.roundId:04}_client{req.clientId:03}_{req.operationId}")
        cached = cached_response(req, target)
        if cached is not None:
            log.info("operation.replayed operation=train experiment=%s round=%s client=%s operationId=%s", req.experimentId, req.roundId, req.clientId, req.operationId)
            return cached
        started = time.perf_counter()
        data = dataset(req.manifestPath)
        if req.clientId not in data.partitions:
            raise ValueError("Unknown client")
        checkpoint = load_checkpoint(path(req.globalModelPath))
        if checkpoint["experimentId"] != req.experimentId or checkpoint["modelVersion"] != req.baseModelVersion:
            raise ValueError("Base checkpoint experiment/version mismatch")
        torch.manual_seed(req.seed)
        network = model(checkpoint["architecture"])
        # Mỗi client bắt đầu từ checkpoint được Java cố định cho round hiện tại.
        network.load_state_dict(checkpoint["state"])
        network.train()
        # Tạo optimizer mới để state huấn luyện không truyền từ client trước sang client sau.
        optimizer = torch.optim.SGD(network.parameters(), lr=req.training.learningRate)
        log.info("train.config architecture=%s baseModelVersion=%s samples=%s epochs=%s batchSize=%s learningRate=%s seed=%s",
                 checkpoint["architecture"], req.baseModelVersion, len(data.partitions[req.clientId]), req.training.epochs,
                 req.training.batchSize, req.training.learningRate, req.seed)
        batches = loader(data, data.partitions[req.clientId], req.training.batchSize, True, req.seed)
        total_loss, count = 0.0, 0
        for epoch in range(req.training.epochs):
            epoch_started = time.perf_counter()
            epoch_loss, epoch_count = 0.0, 0
            for batch_id, (x, y) in enumerate(batches):
                optimizer.zero_grad(set_to_none=True)
                loss = nn.functional.cross_entropy(network(x), y)
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite training loss")
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(y)
                count += len(y)
                epoch_loss += loss.item() * len(y)
                epoch_count += len(y)
                if batch_id % 50 == 0:
                    log.debug("train.batch epoch=%s/%s batch=%s/%s loss=%.6f", epoch + 1, req.training.epochs,
                              batch_id + 1, len(batches), loss.item())
            log.info("train.epoch epoch=%s/%s loss=%.6f samples=%s elapsedMs=%.2f", epoch + 1, req.training.epochs,
                     epoch_loss / epoch_count, epoch_count, (time.perf_counter() - epoch_started) * 1000)
        metadata = dict(experimentId=req.experimentId, roundId=req.roundId, clientId=req.clientId,
                        baseModelVersion=req.baseModelVersion, numSamples=len(data.partitions[req.clientId]))
        save_checkpoint(target, network.state_dict(), architecture=checkpoint["architecture"], operationRequestHash=request_hash(req), **metadata)
        # RSS thuộc toàn process worker, không đại diện RAM của một thiết bị ảo.
        memory = psutil.Process().memory_info()
        training_ms = (time.perf_counter() - started) * 1000
        log.info("train.saved loss=%.6f trainingMs=%.2f workerRssMb=%.2f update=%s", total_loss / count,
                 training_ms, memory.rss / 2**20, relative(target))
        response = dict(**metadata, architecture=checkpoint["architecture"], modelPayloadBytes=payload_bytes(network.state_dict()), modelSchemaHash=checkpoint["modelSchemaHash"], updatePath=relative(target),
                    trainingLoss=total_loss / count, actualTrainingMs=training_ms, modelStateHash=state_hash(network.state_dict()),
                    workerRssMb=memory.rss / 2**20,
                    workerPeakRssMb=getattr(memory, "peak_wset", memory.rss) / 2**20,
                    status="TRAINING_COMPLETED")
        return commit_response(req, target, response)


@app.post("/models/evaluate")
@logged_operation("evaluate")
def evaluate(req: Evaluate):
    with exclusive():
        started = time.perf_counter()
        data = dataset(req.manifestPath)
        checkpoint = load_checkpoint(path(req.checkpointPath))
        set_log_context(experiment=checkpoint["experimentId"])
        if "roundId" in checkpoint:
            set_log_context(round_id=checkpoint["roundId"])
        if "clientId" in checkpoint:
            set_log_context(client_id=checkpoint["clientId"])
        log.info("evaluate.config owner=server split=%s samples=%s architecture=%s modelVersion=%s checkpoint=%s",
                 req.split, len(data.splits[req.split]), checkpoint["architecture"],
                 checkpoint.get("modelVersion", checkpoint.get("baseModelVersion")), req.checkpointPath)
        network = model(checkpoint["architecture"])
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
        accuracy = accuracy_score(actual, predicted)
        confusion = confusion_matrix(actual, predicted, labels=list(range(7))).tolist()
        evaluation_ms = (time.perf_counter() - started) * 1000
        log.info("evaluate.metrics split=%s loss=%.6f accuracy=%.6f macroF1=%.6f worstClassRecall=%.6f",
                 req.split, loss / len(actual), accuracy, f1.mean(), recall.min())
        log.debug("evaluate.classes precision=%s recall=%s confusionMatrix=%s", precision.tolist(), recall.tolist(),
                  confusion)
        return dict(architecture=checkpoint["architecture"], modelStateHash=state_hash(checkpoint["state"]), split=req.split,
                    loss=loss / len(actual), accuracy=accuracy, macroF1=float(f1.mean()),
                    perClassPrecision=precision.tolist(), perClassRecall=recall.tolist(), worstClassRecall=float(recall.min()),
                    confusionMatrix=confusion, evaluationMs=evaluation_ms)


@app.post("/models/aggregate")
@logged_operation("aggregate")
def aggregate(req: Aggregate):
    with exclusive():
        target = artifact(req.experimentId, f"global_{req.baseModelVersion + 1:04}_{req.operationId}")
        cached = cached_response(req, target)
        if cached is not None:
            log.info("operation.replayed operation=aggregate experiment=%s round=%s operationId=%s", req.experimentId, req.roundId, req.operationId)
            return cached
        # Kiểm tra lại artifact dù Java đã lọc metadata của các update được chấp nhận.
        checkpoints = [load_checkpoint(path(p)) for p in req.updates]
        ids = [c["clientId"] for c in checkpoints]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate client update")
        for c in checkpoints:
            if (c["experimentId"], c["roundId"], c["baseModelVersion"]) != (req.experimentId, req.roundId, req.baseModelVersion):
                raise ValueError("Stale or foreign update")
        architecture = checkpoints[0]["architecture"]
        if any(c["architecture"] != architecture for c in checkpoints):
            raise ValueError("Cannot aggregate updates from different architectures")
        log.info("aggregate.inputs clients=%s weights=%s architecture=%s baseModelVersion=%s", ids, req.weights, architecture, req.baseModelVersion)
        state = weighted_average([c["state"] for c in checkpoints], req.weights, architecture)
        save_checkpoint(target, state, architecture=architecture, experimentId=req.experimentId, modelVersion=req.baseModelVersion + 1,
                        operationRequestHash=request_hash(req))
        log.info("aggregate.saved modelVersion=%s checkpoint=%s", req.baseModelVersion + 1, relative(target))
        response = dict(checkpointPath=relative(target), modelVersion=req.baseModelVersion + 1, architecture=architecture, modelStateHash=state_hash(state))
        return commit_response(req, target, response)


@app.post("/simulation/round")
@logged_operation("simulation")
def simulation(req: Simulation):
    return simulate_round(**req.model_dump())
