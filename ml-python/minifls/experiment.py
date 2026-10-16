"""Submit/poll experiments and export their evidence from the Java coordinator."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


def request(base, route, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(base + route, data=body, headers={"Content-Type":"application/json"})
    with urlopen(req, timeout=1800) as response:
        return response.read().decode()


def run(config, base="http://127.0.0.1:8080", output="artifacts/results", resume=False):
    experiment = config["experimentId"]
    request(base, f"/experiments/{experiment}/resume" if resume else "/experiments", {} if resume else config)
    last = None
    while True:
        state = json.loads(request(base, f"/experiments/{experiment}"))
        progress = (state["snapshot"] or {}).get("round", 0)
        if progress != last:
            print(f"{experiment}: round {progress}/{config['rounds']}", flush=True)
            last = progress
        if state["status"] != "RUNNING":
            break
        time.sleep(.5)
    directory = Path(output) / experiment
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "experiment.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
    rounds = json.loads(request(base, f"/experiments/{experiment}/rounds"))
    (directory / "rounds.json").write_text(json.dumps(rounds,indent=2),encoding="utf-8")
    (directory / "metrics.csv").write_text(request(base,f"/experiments/{experiment}/metrics.csv"),encoding="utf-8")
    print(f"{experiment}: {state['status']}; evidence: {directory}",flush=True)
    if state["status"] != "COMPLETED":
        raise RuntimeError(state.get("error") or state["status"])
    return state, rounds


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="artifacts/results")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run(json.loads(Path(args.config).read_text(encoding="utf-8")), args.base, args.output, args.resume)
