import hashlib
import json
import logging
import os
from pathlib import Path
import uuid

import torch
from torch import nn

ARCHITECTURE = "mlp_54_256_128_7"
ARCHITECTURES = {"mlp_54_128_64_7": (128, 64), ARCHITECTURE: (256, 128)}
log = logging.getLogger(__name__)


def model(architecture=ARCHITECTURE):
    if architecture not in ARCHITECTURES:
        raise ValueError(f"Unknown architecture: {architecture}")
    first, second = ARCHITECTURES[architecture]
    # Trả logits trực tiếp vì CrossEntropyLoss đã xử lý bước chuẩn hóa cần thiết.
    return nn.Sequential(nn.Linear(54, first), nn.ReLU(), nn.Linear(first, second), nn.ReLU(), nn.Linear(second, 7))


def schema_hash(state):
    # Hash mô tả tên, shape và dtype; không phải hash giá trị trọng số.
    schema = [(k, list(v.shape), str(v.dtype)) for k, v in state.items()]
    return hashlib.sha256(json.dumps(schema).encode()).hexdigest()


def validate_state(state, architecture=ARCHITECTURE):
    # Chặn tensor sai cấu trúc hoặc chứa NaN/Inf trước khi lưu và aggregation.
    reference = model(architecture).state_dict()
    if list(state) != list(reference):
        raise ValueError("Model keys mismatch")
    for k, v in state.items():
        if v.shape != reference[k].shape or v.dtype != reference[k].dtype or not torch.isfinite(v).all():
            raise ValueError(f"Invalid tensor {k}")


def save_checkpoint(path, state, architecture=ARCHITECTURE, **metadata):
    validate_state(state, architecture)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("Immutable checkpoint already exists")
    # Ghi file tạm rồi đổi tên nguyên tử để tránh checkpoint bị ghi dở khi gián đoạn.
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        torch.save(dict(state=state, architecture=architecture, modelSchemaHash=schema_hash(state), **metadata), temporary)
        os.replace(temporary, path)
        log.debug("checkpoint.saved architecture=%s path=%s modelVersion=%s", architecture, path, metadata.get("modelVersion", metadata.get("baseModelVersion")))
    finally:
        temporary.unlink(missing_ok=True)


def load_checkpoint(path):
    # Chỉ nạp các kiểu được weights_only cho phép, không khôi phục đối tượng tùy ý.
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint["architecture"] not in ARCHITECTURES:
        raise ValueError("Architecture mismatch")
    validate_state(checkpoint["state"], checkpoint["architecture"])
    if checkpoint["modelSchemaHash"] != schema_hash(checkpoint["state"]):
        raise ValueError("Schema mismatch")
    log.debug("checkpoint.loaded architecture=%s path=%s modelVersion=%s", checkpoint["architecture"], path,
              checkpoint.get("modelVersion", checkpoint.get("baseModelVersion")))
    return checkpoint


def weighted_average(states, weights, architecture=ARCHITECTURE):
    if not states or len(states) != len(weights):
        raise ValueError("Expected nonempty matching states and weights")
    w = torch.tensor(weights, dtype=torch.float64)
    if not torch.isfinite(w).all() or (w < 0).any() or abs(w.sum().item() - 1) > 1e-8:
        raise ValueError("Weights must be finite, nonnegative and sum to one")
    for state in states:
        validate_state(state, architecture)
    # Cộng bằng FP64 để giảm sai số tích lũy rồi trả trọng số về FP32 của mô hình.
    result = {key: sum(state[key].double() * weight for state, weight in zip(states, weights)).float()
              for key in states[0]}
    validate_state(result, architecture)
    return result
