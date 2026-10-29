"""Chuẩn bị dữ liệu offline theo seed; tách biệt dữ liệu test khỏi huấn luyện."""
import argparse
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
from sklearn.datasets import fetch_covtype, make_classification
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)


def partition(y, clients, strategy, alpha, seed, minimum=1):
    # Cùng seed và cấu hình sẽ tạo cùng danh sách chỉ số cho từng client.
    rng = np.random.default_rng(seed)
    if len(y) < clients * minimum:
        raise ValueError("Insufficient samples for minimum client size")
    valid = {"iid_equal", "iid_quantity_skew", "dirichlet_label_skew", "dirichlet_mixed_skew"}
    if strategy not in valid or alpha <= 0:
        raise ValueError("Invalid partition strategy or alpha")
    # Cố định sức chứa từng client để kiểm soát lệch số mẫu riêng với lệch nhãn.
    quantity = strategy in {"iid_quantity_skew", "dirichlet_mixed_skew"}
    probs = rng.dirichlet(np.ones(clients) * 2) if quantity else np.ones(clients) / clients
    capacities = np.full(clients, minimum) + rng.multinomial(len(y) - clients * minimum, probs)
    if strategy == "iid_equal":
        capacities = np.array([len(a) for a in np.array_split(np.arange(len(y)), clients)])
    buckets = [[] for _ in range(clients)]
    remaining = capacities.copy()
    classes = np.unique(y)
    preferences = rng.dirichlet(np.full(len(classes), alpha), clients)
    # Gán từng mẫu đã xáo trộn vào chỗ còn trống; IID không ưu tiên nhãn cụ thể.
    for idx in rng.permutation(len(y)):
        weights = remaining.astype(float)
        if strategy.startswith("dirichlet"):
            weights *= preferences[:, int(y[idx])]
        if weights.sum() == 0:
            # Alpha quá nhỏ có thể làm xác suất bằng 0 do giới hạn số thực.
            weights = remaining.astype(float)
        weights /= weights.sum()
        client = int(rng.choice(clients, p=weights))
        buckets[client].append(int(idx))
        remaining[client] -= 1
    return [np.asarray(b, dtype=np.int64) for b in buckets]


def prepare(output, dataset="covertype", clients=100, seed=42, strategy="iid_equal", alpha=0.5, samples=7000, partition_seed=None):
    log.info("data.prepare_started dataset=%s output=%s clients=%s strategy=%s alpha=%s seed=%s",
             dataset, output, clients, strategy, alpha, seed)
    # Không ghi đè manifest cũ để các thí nghiệm đã chạy vẫn có thể tái lập.
    output = Path(output)
    if output.exists():
        raise ValueError("Manifest directory already exists; choose a new output to preserve reproducibility")
    if dataset == "covertype":
        raw = fetch_covtype(data_home=str(output.parent / "cache"))
        x, y = raw.data.astype(np.float32), raw.target.astype(np.int64) - 1
        assert x.shape == (581012, 54)
        test_size, proxy_size = 116202, 29051
    elif dataset == "synthetic":
        x, y = make_classification(n_samples=samples, n_features=54, n_informative=20,
                                   n_redundant=0, n_classes=7, random_state=seed)
        x = x.astype(np.float32)
        test_size, proxy_size = round(samples * .2), round(samples * .05)
    else:
        raise ValueError("Dataset must be covertype or synthetic")
    indices = np.arange(len(y))
    train_proxy, test = train_test_split(indices, test_size=test_size, stratify=y, random_state=seed)
    train, proxy = train_test_split(train_proxy, test_size=proxy_size, stratify=y[train_proxy], random_state=seed + 1)
    # Covertype có 10 đặc trưng số đầu tiên; các cột còn lại là chỉ báo nhị phân.
    continuous = 10 if dataset == "covertype" else 54
    # Chỉ fit trên train; proxy/test dùng lại thống kê này để tránh rò rỉ dữ liệu.
    scaler = StandardScaler().fit(x[train, :continuous])
    x[:, :continuous] = scaler.transform(x[:, :continuous])
    effective_partition_seed = seed + 2 if partition_seed is None else partition_seed
    parts = partition(y[train], clients, strategy, alpha, effective_partition_seed)
    log.info("data.partitioned train=%s proxy=%s test=%s minClientSamples=%s maxClientSamples=%s scaledColumns=%s",
             len(train), len(proxy), len(test), min(map(len, parts)), max(map(len, parts)), continuous)
    output.mkdir(parents=True)
    np.save(output / "features.npy", x)
    np.save(output / "labels.npy", y)
    np.savez(output / "splits.npz", train=train, proxy=proxy, test=test)
    np.savez(output / "partitions.npz", **{str(i): train[p] for i, p in enumerate(parts)})
    files = ["features.npy", "labels.npy", "splits.npz", "partitions.npz"]
    hashes = {f: hashlib.sha256((output / f).read_bytes()).hexdigest() for f in files}
    manifest = dict(dataset=dataset, seed=seed, partitionSeed=effective_partition_seed, strategy=strategy, alpha=alpha, totalClients=clients,
                    counts=dict(train=len(train), proxy=len(proxy), test=len(test)), hashes=hashes,
                    scaler=dict(columns=continuous, mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist()),
                    labelMapping="1..7 -> 0..6" if dataset == "covertype" else "0..6",
                    clients=[dict(clientId=i, numSamples=len(p), labelHistogram=np.bincount(y[train[p]], minlength=7).tolist())
                             for i, p in enumerate(parts)])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("data.prepare_completed manifest=%s", output / "manifest.json")
    return manifest


class Dataset:
    """Nạp dữ liệu dùng chung và kiểm tra tính toàn vẹn của split/partition."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))
        for name, digest in self.manifest["hashes"].items():
            log.debug("data.verify_checksum file=%s", self.directory / name)
            if hashlib.sha256((self.directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Dataset checksum mismatch: {name}")
        # Memory map cho phép truy cập một dataset chung thay vì sao chép cho 100 client.
        self.x = np.load(self.directory / "features.npy", mmap_mode="r")
        self.y = np.load(self.directory / "labels.npy", mmap_mode="r")
        with np.load(self.directory / "splits.npz") as z:
            self.splits = {k: z[k] for k in z.files}
        with np.load(self.directory / "partitions.npz") as z:
            self.partitions = {int(k): z[k] for k in z.files}
        indices = np.concatenate([self.splits[k] for k in ["train", "proxy", "test"]])
        if len(indices) != len(self.y) or not np.array_equal(np.sort(indices), np.arange(len(self.y))):
            raise ValueError("Split overlap, missing rows or invalid indices")
        assigned = np.concatenate(list(self.partitions.values()))
        if not np.array_equal(np.sort(assigned), np.sort(self.splits["train"])):
            raise ValueError("Partitions do not cover training rows exactly once")
        if len(self.partitions) != self.manifest["totalClients"] or any(len(p) == 0 for p in self.partitions.values()):
            raise ValueError("Invalid client population or empty partition")
        log.debug("data.verified dataset=%s rows=%s clients=%s", self.manifest["dataset"], len(self.y), len(self.partitions))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--dataset", choices=["covertype", "synthetic"], default="covertype")
    p.add_argument("--clients", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--partition-seed", type=int, default=None, help="Partition RNG only; --seed still fixes train/proxy/test pools")
    p.add_argument("--strategy", default="iid_equal")
    p.add_argument("--alpha", type=float, default=.5)
    p.add_argument("--samples", type=int, default=7000)
    print(json.dumps(prepare(**vars(p.parse_args()))["counts"]))
