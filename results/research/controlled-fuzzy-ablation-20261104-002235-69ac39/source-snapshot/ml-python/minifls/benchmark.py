"""Kiểm tra học tập trung; không bảo đảm cùng ngân sách tính toán với FL."""
import argparse
import json
import logging
import os
import time

from . import api
from .data import Dataset
from .model import ARCHITECTURE, ARCHITECTURES, model, save_checkpoint
import torch
from torch import nn

log = logging.getLogger(__name__)


def benchmark(manifest, epochs, seed, learning_rate, batch_size, name, architecture=ARCHITECTURE):
    log.info("benchmark.started name=%s architecture=%s manifest=%s epochs=%s batchSize=%s learningRate=%s seed=%s",
             name, architecture, manifest, epochs, batch_size, learning_rate, seed)
    data = Dataset(api.path(manifest))
    torch.manual_seed(seed)
    network = model(architecture)
    optimizer = torch.optim.SGD(network.parameters(),lr=learning_rate)
    # Dùng cùng training pool của FL; held-out test chỉ dùng ở bước đánh giá cuối.
    batches = api.loader(data, data.splits["train"], batch_size, True, seed)
    started = time.perf_counter()
    for epoch in range(epochs):
        epoch_loss, epoch_count = 0.0, 0
        network.train()
        for x,y in batches:
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(network(x),y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(y)
            epoch_count += len(y)
        log.info("benchmark.epoch name=%s epoch=%s/%s loss=%.6f", name, epoch + 1, epochs, epoch_loss / epoch_count)
    target = api.path(f"artifacts/benchmarks/{name}.pt")
    save_checkpoint(target,network.state_dict(),architecture=architecture,experimentId=name,modelVersion=epochs)
    evaluation = api.evaluate(api.Evaluate(checkpointPath=api.relative(target),manifestPath=manifest))
    result = dict(architecture=architecture,dataset=data.manifest["dataset"],seed=seed,epochs=epochs,learningRate=learning_rate,
                  batchSize=batch_size,actualSeconds=time.perf_counter()-started,evaluation=evaluation)
    target.with_suffix(".json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    log.info("benchmark.completed name=%s accuracy=%.6f macroF1=%.6f loss=%.6f elapsedSeconds=%.2f report=%s",
             name, evaluation["accuracy"], evaluation["macroF1"], evaluation["loss"], result["actualSeconds"], target.with_suffix(".json"))
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument("--epochs",type=int,default=5)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--learning-rate",type=float,default=.01)
    p.add_argument("--batch-size",type=int,default=32)
    p.add_argument("--name",default="centralized-42")
    p.add_argument("--architecture",choices=list(ARCHITECTURES),default=os.environ.get("MINIFLS_MODEL_ARCHITECTURE", ARCHITECTURE))
    benchmark(**vars(p.parse_args()))
