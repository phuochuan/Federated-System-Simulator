"""Centralized diagnostic, not a compute-matched federated baseline."""
import argparse
import json
import time

from . import api
from .data import Dataset
from .model import model, save_checkpoint
import torch
from torch import nn


def benchmark(manifest, epochs, seed, learning_rate, batch_size, name):
    data = Dataset(api.path(manifest))
    torch.manual_seed(seed)
    network = model()
    optimizer = torch.optim.SGD(network.parameters(),lr=learning_rate)
    batches = api.loader(data, data.splits["train"], batch_size, True, seed)
    started = time.perf_counter()
    for epoch in range(epochs):
        network.train()
        for x,y in batches:
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(network(x),y)
            loss.backward()
            optimizer.step()
        print(f"centralized epoch {epoch+1}/{epochs}",flush=True)
    target = api.path(f"artifacts/benchmarks/{name}.pt")
    save_checkpoint(target,network.state_dict(),experimentId=name,modelVersion=epochs)
    evaluation = api.evaluate(api.Evaluate(checkpointPath=api.relative(target),manifestPath=manifest))
    result = dict(dataset=data.manifest["dataset"],seed=seed,epochs=epochs,learningRate=learning_rate,
                  batchSize=batch_size,actualSeconds=time.perf_counter()-started,evaluation=evaluation)
    target.with_suffix(".json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument("--epochs",type=int,default=5)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--learning-rate",type=float,default=.01)
    p.add_argument("--batch-size",type=int,default=32)
    p.add_argument("--name",default="centralized-42")
    benchmark(**vars(p.parse_args()))
