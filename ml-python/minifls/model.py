import hashlib
import json
import os
from pathlib import Path
import uuid

import torch
from torch import nn

ARCHITECTURE = "mlp_54_128_64_7"


def model():
    # Trả logits trực tiếp vì CrossEntropyLoss đã xử lý bước chuẩn hóa cần thiết.
    return nn.Sequential(nn.Linear(54, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 7))


def schema_hash(state):
    # Hash mô tả tên, shape và dtype; không phải hash giá trị trọng số.
    schema = [(k, list(v.shape), str(v.dtype)) for k, v in state.items()]
    return hashlib.sha256(json.dumps(schema).encode()).hexdigest()


def validate_state(state):
    # Chặn tensor sai cấu trúc hoặc chứa NaN/Inf trước khi lưu và aggregation.
    reference = model().state_dict()
    if list(state) != list(reference):
        raise ValueError("Model keys mismatch")
    for k, v in state.items():
        if v.shape != reference[k].shape or v.dtype != reference[k].dtype or not torch.isfinite(v).all():
            raise ValueError(f"Invalid tensor {k}")


def save_checkpoint(path, state, **metadata):
    validate_state(state)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("Immutable checkpoint already exists")
    # Ghi file tạm rồi đổi tên nguyên tử để tránh checkpoint bị ghi dở khi gián đoạn.
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        torch.save(dict(state=state, architecture=ARCHITECTURE, modelSchemaHash=schema_hash(state), **metadata), temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_checkpoint(path):
    # Chỉ nạp các kiểu được weights_only cho phép, không khôi phục đối tượng tùy ý.
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if checkpoint["architecture"] != ARCHITECTURE:
        raise ValueError("Architecture mismatch")
    validate_state(checkpoint["state"])
    if checkpoint["modelSchemaHash"] != schema_hash(checkpoint["state"]):
        raise ValueError("Schema mismatch")
    return checkpoint


def weighted_average(states, weights):
    if not states or len(states) != len(weights):
        raise ValueError("Expected nonempty matching states and weights")
    w = torch.tensor(weights, dtype=torch.float64)
    if not torch.isfinite(w).all() or (w < 0).any() or abs(w.sum().item() - 1) > 1e-8:
        raise ValueError("Weights must be finite, nonnegative and sum to one")
    for state in states:
        validate_state(state)
    # Cộng bằng FP64 để giảm sai số tích lũy rồi trả trọng số về FP32 của mô hình.
    result = {key: sum(state[key].double() * weight for state, weight in zip(states, weights)).float()
              for key in states[0]}
    validate_state(result)
    return result
