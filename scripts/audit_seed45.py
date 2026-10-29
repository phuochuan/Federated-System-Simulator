"""Freeze a runtime, audit historical F5/L5, and repeat the identical seed-45 policy.

Run after gradlew test bootJar: .venv/Scripts/python scripts/audit_seed45.py
Evidence is isolated from the historical database. F/L labels are aliases here;
all repeats submit one canonical config, changing only experimentId.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen

from verify_fuzzy import replay_fuzzy

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalized(config):
    return {k: v for k, v in config.items() if k not in ("experimentId", "scenarioTracePath") and v is not None}


def load_run(folder):
    return {"name": folder.name, "state": read(folder / "experiment.json"),
            "rounds": read(folder / "rounds.json")}


def audit(run):
    state, rounds = run["state"], run["rounds"]
    config = state["config"]
    assert state["status"] == "COMPLETED" and len(rounds) == config["rounds"]
    replay_fuzzy(rounds, state)
    estimates = {}
    history = {}
    samples = {p["clientId"]: p for p in state["snapshot"]["clients"]}
    checked = 0
    for row in rounds:
        assert row["selectorInput"]["history"]["startRound"] == 1
        assert row["selectorInput"]["history"]["clients"] == history, (run["name"], row["roundId"], "decision history")
        eligible = row["selectorInput"]["eligibleClients"]
        expected_feasible = []
        for client in eligible:
            cid = client["clientId"]
            expected = estimates.get(cid)
            assert client["estimatedSeconds"] == expected, (run["name"], row["roundId"], cid)
            prediction = expected if expected is not None else client["numSamples"] * config["localEpochs"] * config["priorSecondsPerSample"] / client["cpu"]
            if client["ramMb"] >= config["requiredRamMb"] and prediction <= config["deadlineSeconds"]:
                expected_feasible.append(cid)
            obs = row["criteriaObservations"].get(str(cid))
            if obs is not None:
                assert math.isclose(obs["estimatedTime"], prediction, abs_tol=1e-10)
                checked += 1
        assert set(expected_feasible) == set(row["estimatedFeasibleIds"])
        for decision in row["selectionDecisions"]:
            cid = decision["clientId"]
            client = samples[cid]
            expected = estimates.get(cid)
            prediction = expected if expected is not None else client["numSamples"] * config["localEpochs"] * config["priorSecondsPerSample"] / client["cpu"]
            assert math.isclose(decision["predictedSeconds"], prediction, abs_tol=1e-10)
            assert decision["estimateSource"] == ("prior" if expected is None else "history")
        for participant in row["participants"]:
            cid = participant["clientId"]
            estimates[cid] = participant.get("durationInputMs", participant["training"]["actualTrainingMs"]) / 1000 / samples[cid]["cpu"]
        feasible = row["estimatedFeasibleIds"]
        share = min(config["selectedPerRound"], len(feasible)) / len(feasible) if feasible else 0
        for cid in feasible:
            account = history.setdefault(str(cid), {"opportunities": 0, "selections": 0,
                                                     "completions": 0, "feasibleStaleness": 0, "entitlement": 0.0})
            selected = cid in row["selectedIds"]
            account["opportunities"] += 1
            account["selections"] += int(selected)
            account["completions"] += int(cid in row["acceptedIds"])
            account["feasibleStaleness"] = 0 if selected else account["feasibleStaleness"] + 1
            account["entitlement"] += share
    assert state["snapshot"]["selectionHistory"]["clients"] == history
    return {"rounds": len(rounds), "timingCriteriaChecked": checked,
            "scoreCreditControllerReplay": "PASS", "timingHistoryAndFeasibility": "PASS",
            "serializedDecisionHistory": "PASS"}


def comparison(a, b, output):
    fields = ["selectedIds", "acceptedIds", "estimatedFeasibleIds", "criteriaObservations",
              "fuzzyTopsisScores", "fairnessCredits", "currentFairnessLambda"]
    rows = []
    for x, y in zip(a["rounds"], b["rounds"]):
        common = set(x["criteriaObservations"]) & set(y["criteriaObservations"])
        deltas = [abs(x["criteriaObservations"][c]["estimatedTime"] - y["criteriaObservations"][c]["estimatedTime"]) for c in common]
        rows.append({"round": x["roundId"], **{k + "Equal": x[k] == y[k] for k in fields},
                     "selectedSetEqual": set(x["selectedIds"]) == set(y["selectedIds"]),
                     "acceptedSetEqual": set(x["acceptedIds"]) == set(y["acceptedIds"]),
                     "slotsChanged": len(set(x["selectedIds"]) - set(y["selectedIds"])),
                     "maxEstimatedTimeDeltaSeconds": max(deltas, default=0)})
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    keys = [k for k in rows[0] if k.endswith("Equal")]
    return {"left": a["name"], "right": b["name"],
            "differences": {k: {"roundCount": sum(not r[k] for r in rows),
                                 "firstRound": next((r["round"] for r in rows if not r[k]), None)} for k in keys},
            "changedSlots": sum(r["slotsChanged"] for r in rows),
            "selectedSlots": sum(len(r["selectedIds"]) for r in a["rounds"]),
            "maxEstimatedTimeDeltaSeconds": max(r["maxEstimatedTimeDeltaSeconds"] for r in rows)}


def metrics(run):
    rounds = run["rounds"]
    last = rounds[-1]
    times = [p["training"]["actualTrainingMs"] for r in rounds for p in r["participants"]]
    return {"accuracy": last["evaluation"]["accuracy"], "macroF1": last["evaluation"]["macroF1"],
            "loss": last["evaluation"]["loss"], "coverage": last["fairness"]["coverage"],
            "feasibleSelectionGini": last["fairness"]["feasibleOpportunityAdjustedGini"],
            "finalLambda": last["nextFairnessLambda"],
            "virtualSeconds": last["cumulativeVirtualSeconds"],
            "wallSeconds": sum(r["wallClockSeconds"] for r in rounds),
            "meanTrainingMs": statistics.mean(times),
            "accepted": sum(len(r["acceptedIds"]) for r in rounds)}


def request(base, route, payload=None):
    req = Request(base + route, data=None if payload is None else json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_ready(base, route, process):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Service exited; inspect services.log")
        try:
            request(base, route)
            return
        except (OSError, TimeoutError):
            time.sleep(.5)
    raise TimeoutError(base)


def repeat(folder, config, jar, frozen_python):
    worker_port, server_port = port(), port()
    while worker_port == server_port:
        server_port = port()
    worker_base, base = f"http://127.0.0.1:{worker_port}", f"http://127.0.0.1:{server_port}"
    env = {**os.environ, "MINIFLS_WORKSPACE": str(ROOT), "MINIFLS_WORKER_URL": worker_base,
           "MINIFLS_SERVER_PORT": str(server_port), "MINIFLS_DATABASE": str(folder / "run.db"),
           "MINIFLS_METHOD": "none", "MINIFLS_TORCH_THREADS": "1", "PYTHONHASHSEED": "45",
           "PYTHONPATH": str(frozen_python)}
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    processes = []
    folder.mkdir(parents=True)
    save(folder / "submitted-config.json", config)
    with (folder / "services.log").open("w", encoding="utf-8") as log:
        try:
            worker = subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(worker_port), "--workers", "1"], cwd=folder, env=env, stdout=log, stderr=log, **flags)
            processes.append(worker)
            wait_ready(worker_base, "/health", worker)
            server = subprocess.Popen(["java", "-Xmx384m", "-jar", str(jar)], cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            processes.append(server)
            wait_ready(base, "/experiments", server)
            request(base, "/experiments", config)
            deadline = time.monotonic() + 3600
            previous = None
            while time.monotonic() < deadline:
                if any((parent / "STOP").exists() for parent in folder.parents if parent != ROOT and parent.is_relative_to(ROOT)):
                    raise InterruptedError("Experiment stop requested")
                state = request(base, "/experiments/" + config["experimentId"])
                progress = (state.get("snapshot") or {}).get("round", 0)
                if progress != previous and (progress % 10 == 0 or progress == 1):
                    print(f"{config['experimentId']}: {progress}/{config['rounds']}", flush=True)
                    previous = progress
                if state["status"] != "RUNNING":
                    save(folder / "experiment.json", state)
                    save(folder / "rounds.json", request(base, "/experiments/" + config["experimentId"] + "/rounds"))
                    assert state["status"] == "COMPLETED", state.get("error")
                    save(folder / "result.json", request(base, "/experiments/" + config["experimentId"] + "/result"))
                    return load_run(folder)
                time.sleep(2)
            raise TimeoutError("Run exceeded one hour")
        finally:
            for process in reversed(processes):
                if os.name == "nt" and process.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    process.wait()
                    continue
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, default=4)
    args = parser.parse_args()
    assert args.repeats >= 2
    folder = (args.output or ROOT / "artifacts" / "seed45-audit" / datetime.now().strftime("%Y%m%d-%H%M%S")).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    print(f"Evidence: {folder}", flush=True)
    historical = [load_run(next((ROOT / "artifacts/comparisons").glob(f"*/runs/*-{label}-s45"))) for label in ("F5", "L5")]
    assert normalized(historical[0]["state"]["config"]) == normalized(historical[1]["state"]["config"])
    baseline = historical[1]["state"]
    for key in ("manifest", "initialModelStateHash", "scenarioTraceHash"):
        assert historical[0]["state"]["snapshot"][key] == baseline["snapshot"][key], key
    report = {"historical": {"audits": [audit(r) for r in historical],
                             "metrics": {r["name"]: metrics(r) for r in historical},
                             "comparison": comparison(*historical, folder / "historical-round-differences.csv")}}
    save(folder / "historical-audit.json", report)
    freeze = folder / "freeze"
    freeze.mkdir()
    jar = freeze / "runtime.jar"
    shutil.copy2(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar", jar)
    shutil.copytree(ROOT / "ml-python/minifls", freeze / "python/minifls", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for directory in ("configurations", "ferderatedsystem/src"):
        shutil.copytree(ROOT / directory, freeze / directory)
    shutil.copy2(Path(__file__), freeze / "audit_seed45.py")
    trace_source = ROOT / baseline["config"]["scenarioTracePath"]
    shutil.copy2(trace_source, freeze / "trace.json")
    config = dict(baseline["config"])
    config["scenarioTracePath"] = (freeze / "trace.json").relative_to(ROOT).as_posix()
    config["experimentId"] = "seed45-frozen-template"
    save(freeze / "canonical-config.json", config)
    def command(*cmd):
        return subprocess.check_output(cmd, cwd=ROOT, text=True, encoding="utf-8", errors="replace", stderr=subprocess.STDOUT)
    (freeze / "git.diff").write_text(command("git", "diff", "--binary", "HEAD"), encoding="utf-8")
    (freeze / "pip-freeze.txt").write_text(command(sys.executable, "-m", "pip", "freeze"), encoding="utf-8")
    frozen_files = {p.relative_to(ROOT).as_posix(): sha(p) for p in freeze.rglob("*") if p.is_file()}
    data_files = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / config["manifestPath"]).rglob("*") if p.is_file()}
    provenance = {"gitCommit": command("git", "rev-parse", "HEAD").strip(),
                  "gitStatus": command("git", "status", "--short"), "platform": platform.platform(),
                  "python": sys.version, "java": command("java", "-version"),
                  "runtimeHashes": frozen_files, "partitionHashes": data_files,
                  "runOrder": ["F5", "L5", "L5", "F5"],
                  "conditions": "Serial; fresh Java/Python per run; torch threads=1; same canonical config and trace; seed=45; measured training times remain live."}
    save(freeze / "manifest.json", provenance)
    print("Historical replay PASS; runtime frozen; starting repeats", flush=True)
    runs = []
    for index in range(args.repeats):
        label = provenance["runOrder"][index % 4]
        name = f"seed45-{folder.name}-{index+1:02d}-{label}"
        config_run = {**config, "experimentId": name}
        run = repeat(folder / "runs" / name, config_run, jar, freeze / "python")
        assert normalized(run["state"]["config"]) == normalized(config)
        for key in ("manifest", "initialModelStateHash", "scenarioTraceHash"):
            assert run["state"]["snapshot"][key] == baseline["snapshot"][key], key
        run_audit = audit(run)
        runs.append(run)
        save(folder / "progress.json", {"completed": len(runs), "metrics": {r["name"]: metrics(r) for r in runs}, "lastAudit": run_audit})
        print(f"Completed {len(runs)}/{args.repeats}: {metrics(run)}", flush=True)
    for path, digest in {**frozen_files, **data_files}.items():
        assert sha(ROOT / path) == digest, f"Frozen input changed: {path}"
    values = {r["name"]: metrics(r) for r in runs}
    summary = {}
    for key in next(iter(values.values())):
        v = [m[key] for m in values.values()]
        mean, sd = statistics.mean(v), statistics.stdev(v)
        summary[key] = {"n": len(v), "mean": mean, "sampleSd": sd, "min": min(v), "max": max(v), "range": max(v)-min(v), "cv": sd/mean if mean else None}
    pairs = [comparison(a, b, folder / f"repeat-{i+1}-vs-{j+1}.csv") for (i, a), (j, b) in itertools.combinations(enumerate(runs), 2)]
    report.update(repeats={"metrics": values, "summary": summary, "pairs": pairs,
                           "audits": [audit(r) for r in runs], "frozenHashesUnchanged": True})
    save(folder / "report.json", report)
    lines = ["# Seed 45: frozen-runtime F5/L5 audit", "", f"Evidence: `{folder.relative_to(ROOT).as_posix()}`", "",
             "F5 and L5 use the same adaptive policy and normalized configuration. Historical builds were not frozen; their gitDirty snapshots cannot identify exact source/binary contents. Historical results are reported separately from fresh repeats.", "",
             "All score/credit/controller replays and timing-history/feasibility checks passed. Initial tensor hash, full manifest and exogenous trace hash match across all runs. Repeat runtime and partition hashes remained unchanged.", "",
             "## Historical comparison", "", "| Metric | F5 | L5 |", "| --- | ---: | ---: |"]
    for k in metrics(historical[0]):
        lines.append(f"| {k} | {metrics(historical[0])[k]:.8f} | {metrics(historical[1])[k]:.8f} |")
    lines.extend(["", "Decision differences (ordered lists and sets are distinguished):", "", "```json", json.dumps(report["historical"]["comparison"], indent=2), "```", "",
                  "## Fresh repeats", "", "Serial runs, fresh services per repeat; F5/L5 labels are aliases for the same config. No other experiments were launched by this audit. Background OS load remains uncontrolled.", "",
                  "| Metric | Mean | Sample SD | Min | Max | CV |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for k, v in summary.items():
        lines.append(f"| {k} | {v['mean']:.8f} | {v['sampleSd']:.8f} | {v['min']:.8f} | {v['max']:.8f} | {v['cv']:.4f} |")
    lines.extend(["", f"{args.repeats} repeats of one seed estimate conditional run-to-run variability; they do not estimate across-seed uncertainty or establish an F5/L5 treatment effect. Physical training duration feeds the next-round estimatedTime criterion and virtual completion time, so deterministic ML seeds do not guarantee deterministic decisions. Consult per-round CSVs for the first order/set divergence and timing deltas.", ""])
    (folder / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"DONE: {folder / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
