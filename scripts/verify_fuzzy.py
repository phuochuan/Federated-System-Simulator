"""Real PyTorch/Java/SQLite F1--F5 smoke, plus independent score/credit replay.

Run from the workspace: .venv/Scripts/python.exe scripts/verify_fuzzy.py
Synthetic smoke evidence must not be pooled with the 70-round Covertype protocol.
"""
import json
import argparse
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from urllib.error import URLError
from urllib.request import Request, urlopen

from minifls.data import prepare

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get(base, route):
    with urlopen(base + route, timeout=10) as response:
        return json.load(response)


def post(base, route, body=None):
    request = Request(base+route, data=json.dumps(body or {}).encode(), headers={"Content-Type":"application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def close(a, b):
    assert math.isfinite(a) and math.isclose(a, b, abs_tol=1e-10), (a, b)


def replay_fuzzy(rounds, state):
    """Independent scalar implementation verifies saved mathematical evidence.

    Does not call Java's engine and does not read any evaluation/test metric.
    """
    previous = {}
    previous_lambda = state["config"]["fuzzySelection"]["fairness"]["lambda"]
    method = state["config"]["selection"]
    credit = method != "fuzzy_topsis"
    if not credit:
        previous_lambda = 0
    smoothed = None
    opportunities, selections = {}, {}
    for index, row in enumerate(rounds, 1):
        close(row["currentFairnessLambda"], previous_lambda)
        assert row["selectorInput"]["state"]["lastCommittedRound"] == index - 1
        assert row["fairnessCredits"] == previous
        matrix = row["fuzzyDecisionMatrix"]
        criteria, values = matrix["criteria"], matrix["rows"]
        weighted = {key: [] for key in values}
        for j, criterion in enumerate(criteria):
            # Explicit field access avoids depending on JSON property ordering.
            column = [[value[j][k] for k in ("lower", "middle", "upper")] for value in values.values()]
            if not column:
                continue
            maximum = max(t[2] for t in column)
            minimum = min(max(1e-9, t[0]) for t in column)
            for key, value in values.items():
                triple = [value[j][k] for k in ("lower", "middle", "upper")]
                if maximum <= 1e-9:
                    normalized = [1., 1., 1.]
                elif criterion["type"] == "BENEFIT":
                    normalized = [v / maximum for v in triple]
                else:
                    normalized = [minimum / max(1e-9, v) for v in reversed(triple)]
                weighted[key].append([v * criterion["weight"] for v in normalized])
        if weighted:
            positive = [[max(v[j][k] for v in weighted.values()) for k in range(3)] for j in range(len(criteria))]
            negative = [[min(v[j][k] for v in weighted.values()) for k in range(3)] for j in range(len(criteria))]
            distance = lambda a, b: math.sqrt(sum((x-y)**2 for x, y in zip(a, b))/3)
            for key, values_i in weighted.items():
                dp = sum(distance(v, p) for v, p in zip(values_i, positive))
                dn = sum(distance(v, n) for v, n in zip(values_i, negative))
                cc = .5 if dp + dn <= 1e-9 else dn / (dp + dn)
                close(row["fuzzyTopsisScores"][key], cc)
        expected = dict(previous)
        if credit:
            feasible = row["estimatedFeasibleIds"]
            share = min(state["config"]["selectedPerRound"], len(feasible))/len(feasible) if feasible else 0
            for client in feasible:
                expected[str(client)] = max(0, expected.get(str(client), 0)+share-int(client in row["selectedIds"]))
        for key, value in expected.items():
            close(row["fairnessCreditsAfterRound"][key], value)
        feasible = row["estimatedFeasibleIds"]
        maximum_credit = max((previous.get(str(client), 0) for client in feasible), default=0)
        for key, cc in row["fuzzyTopsisScores"].items():
            normalized = previous.get(key, 0)/maximum_credit if credit and maximum_credit else 0
            close(row["finalSelectionScores"][key], cc + row["currentFairnessLambda"]*normalized)
        for client in feasible:
            opportunities[client] = opportunities.get(client, 0)+1
            selections[client] = selections.get(client, 0)+int(client in row["selectedIds"])
        if method == "adaptive_fuzzy_topsis_fair" and opportunities:
            rates = sorted(selections[client]/opportunities[client] for client in opportunities)
            gini = sum((2*(i+1)-len(rates)-1)*rate for i, rate in enumerate(rates))/(len(rates)*sum(rates)) if sum(rates) else 0
            settings = state["config"]["fuzzySelection"]["fairness"]
            smoothed = gini if smoothed is None else settings["smoothing"]*smoothed+(1-settings["smoothing"])*gini
            delta = max(-settings["maxUpdate"], min(settings["maxUpdate"], settings["adaptationRate"]*(smoothed-settings["targetFeasibleGini"])))
            close(row["nextFairnessLambda"], max(settings["lambdaMin"], min(settings["lambdaMax"], previous_lambda+delta)))
        ranked = sorted(row["finalSelectionScores"], key=lambda key: (-row["finalSelectionScores"][key], int(key)))
        assert row["selectedIds"] == [int(key) for key in ranked[:state["config"]["selectedPerRound"]]]
        previous = row["fairnessCreditsAfterRound"]
        previous_lambda = row["nextFairnessLambda"]
    assert state["snapshot"]["fuzzySelectionState"]["deficits"] == previous
    close(state["snapshot"]["fuzzySelectionState"]["currentLambda"], previous_lambda)


def verify(lambda_ablation=False):
    rows = [f"L{i}" for i in range(6)] if lambda_ablation else [f"F{i}" for i in range(1,6)]
    adaptive_row = "L5" if lambda_ablation else "F5"
    expected_experiments = len(rows)*2
    folder = ROOT / ("artifacts/lambda-smoke" if lambda_ablation else "artifacts/fuzzy-smoke") / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    for name, strategy in (("iid", "iid_equal"), ("non-iid", "dirichlet_label_skew")):
        prepare(folder/name, dataset="synthetic", clients=100, samples=7000, strategy=strategy)
    config = json.loads((ROOT/("configurations/lambda-ablation.json" if lambda_ablation else "configurations/fuzzy-matrix.json")).read_text(encoding="utf-8"))
    config.update(iidManifestPath=(folder/"iid").relative_to(ROOT).as_posix(),
                  nonIidManifestPath=(folder/"non-iid").relative_to(ROOT).as_posix(), seeds=[42, 43])
    config["baseConfig"]["rounds"] = 3
    matrix_file = folder/"matrix.json"
    matrix_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    worker_port, server_port = free_port(), free_port()
    while server_port == worker_port:
        server_port = free_port()
    base, worker_base = f"http://127.0.0.1:{server_port}", f"http://127.0.0.1:{worker_port}"
    env = {**os.environ, "MINIFLS_WORKSPACE":str(ROOT), "MINIFLS_WORKER_URL":worker_base,
           "MINIFLS_SERVER_PORT":str(server_port), "MINIFLS_DATABASE":str(folder/"test.db"),
           "MINIFLS_METHOD":"fuzzy_matrix", "MINIFLS_FUZZY_MATRIX_CONFIG":str(matrix_file), "MINIFLS_MATRIX_ROUNDS":"3"}
    if lambda_ablation:
        env.update(MINIFLS_METHOD="lambda_ablation",MINIFLS_LAMBDA_MATRIX_CONFIG=str(matrix_file))
    flags = {"creationflags":subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = server = None
    with (folder/"services.log").open("w", encoding="utf-8") as log:
        try:
            worker = subprocess.Popen([sys.executable,"-m","uvicorn","minifls.api:app","--host","127.0.0.1","--port",str(worker_port)],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic()+90
            while time.monotonic()<deadline:
                if worker.poll() is not None:
                    raise RuntimeError(f"Worker exited: {folder}/services.log")
                try:
                    get(worker_base,"/health")
                    break
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(.25)
            else:
                raise RuntimeError("Worker startup timeout")
            server = subprocess.Popen(["java","-Xmx384m","-jar",str(ROOT/"ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic()+240
            while time.monotonic()<deadline:
                if server.poll() is not None:
                    raise RuntimeError(f"Java exited: {folder}/services.log")
                try:
                    experiments = get(base,"/experiments")
                    if any(e["status"] == "FAILED" for e in experiments):
                        raise RuntimeError(f"Failed experiment: {experiments}; inspect {folder}/services.log")
                    if len(experiments)==expected_experiments and all(e["status"]=="COMPLETED" for e in experiments):
                        batch = experiments[0]["id"][len("matrix-"):].rsplit("-",2)[0]
                        report = ROOT/"artifacts/comparisons"/batch/("L-fixed-lambda-ablation.txt" if lambda_ablation else "F-fuzzy-client-selection.txt")
                        if report.exists():
                            break
                except (URLError, TimeoutError, ConnectionError):
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError(f"Matrix timeout: {folder}/services.log")
            states, evidence = {}, {}
            for experiment in experiments:
                state = get(base,f"/experiments/{experiment['id']}")
                rounds = get(base,f"/experiments/{experiment['id']}/rounds")
                row, seed = experiment["id"].rsplit("-",2)[1], state["config"]["seed"]
                assert len(rounds)==3 and get(base,f"/experiments/{experiment['id']}/result")["roundId"]==3
                states[(row,seed)], evidence[(row,seed)] = state, rounds
                for metrics in rounds:
                    assert len(set(metrics["selectedIds"])) == len(metrics["selectedIds"])
                    assert set(metrics["selectedIds"]) <= set(metrics["estimatedFeasibleIds"])
                    assert metrics["feasibleCandidateCount"] == len(metrics["estimatedFeasibleIds"])
                    assert metrics["fairness"]["ramFeasiblePopulation"] == 60
                    assert metrics["selectorComputationMs"] >= 0
                    assert metrics["cumulativeVirtualSecondsWithSelector"] >= metrics["cumulativeVirtualSeconds"]
                    assert all(math.isfinite(v) and 0<=v<=1 for v in metrics["fuzzyTopsisScores"].values())
                if lambda_ablation or row in ("F3","F4","F5"):
                    replay_fuzzy(rounds,state)
                    for metrics in rounds:
                        cc = metrics["fuzzyTopsisScores"]
                        pure = [int(key) for key in sorted(cc,key=lambda key:(-cc[key],int(key)))[:len(metrics["selectedIds"])]]
                        changed = len(set(metrics["selectedIds"])-set(pure))
                        assert metrics["topsisTopKClientIds"] == pure
                        assert metrics["slotsChangedVsTopsis"] == changed
                        if metrics["selectedIds"]:
                            close(metrics["slotsChangedVsTopsisRatio"],changed/len(metrics["selectedIds"]))
                    if lambda_ablation and row!="L5":
                        expected_lambda = config["lambdaAblation"]["fixedLambdas"][int(row[1:])]
                        assert all(r["currentFairnessLambda"]==expected_lambda and r["nextFairnessLambda"]==expected_lambda for r in rounds)
                        if row=="L0":assert all(r["slotsChangedVsTopsis"]==0 for r in rounds)
                else:
                    assert state["snapshot"]["fuzzySelectionState"] is None
            for seed in (42,43):
                reference = states[(rows[0],seed)]["snapshot"]
                for row in rows[1:]:
                    snapshot = states[(row,seed)]["snapshot"]
                    assert snapshot["initialModelStateHash"] == reference["initialModelStateHash"]
                    assert snapshot["scenarioTraceHash"] == reference["scenarioTraceHash"]
                    for i in range(3):
                        assert evidence[(row,seed)][i]["scenarioTrace"] == evidence[(rows[0],seed)][i]["scenarioTrace"]
            text = report.read_text(encoding="utf-8")
            assert "Status: COMPLETED" in text and "SMOKE TEST ONLY" in text
            pairs = ("L0 VS L5","L1 VS L5","L2 VS L5","L3 VS L5","L4 VS L5","L0 VS L4") if lambda_ablation else ("F1 VS F2","F1 VS F3","F3 VS F4","F4 VS F5","F1 VS F5","F2 VS F5")
            for pair in pairs:
                assert pair in text
            if lambda_ablation:
                for name in ("accuracyTailSd","macroF1TailSd","slotsChangedVsTopsisRatio","finalAccuracyChangePp"):
                    assert name in text
            # Crash an additional live run after an actual committed round; restart
            # both processes and resume from the SQLite checkpoint on disk.
            resume_config = dict(states[(adaptive_row,42)]["config"])
            resume_config.update(experimentId="fuzzy-resume-smoke", rounds=12, scenarioTracePath=None)
            post(base,"/experiments",resume_config)
            deadline = time.monotonic()+45
            while time.monotonic()<deadline:
                before = get(base,"/experiments/fuzzy-resume-smoke")
                if before["snapshot"] and before["snapshot"]["round"]>=1:
                    break
                time.sleep(.01)
            else:
                raise RuntimeError("Resume smoke never committed a round")
            server.terminate(); server.wait(timeout=20)
            worker.terminate(); worker.wait(timeout=20)
            env["MINIFLS_METHOD"] = "none"
            env["MINIFLS_LAUNCH_ENABLED"] = "false"
            worker = subprocess.Popen([sys.executable,"-m","uvicorn","minifls.api:app","--host","127.0.0.1","--port",str(worker_port)],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic()+60
            while time.monotonic()<deadline:
                try:
                    get(worker_base,"/health"); break
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(.25)
            else:
                raise RuntimeError("Worker restart timeout")
            server = subprocess.Popen(["java","-Xmx384m","-jar",str(ROOT/"ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic()+60
            while time.monotonic()<deadline:
                try:
                    recovered = get(base,"/experiments/fuzzy-resume-smoke"); break
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(.25)
            else:
                raise RuntimeError("Java restart timeout")
            assert recovered["status"] in ("INTERRUPTED", "FAILED"), recovered["status"]
            committed = recovered["snapshot"]["round"]
            assert 1 <= committed < 12
            old_rounds = get(base,"/experiments/fuzzy-resume-smoke/rounds")
            post(base,"/experiments/fuzzy-resume-smoke/resume")
            deadline = time.monotonic()+60
            while time.monotonic()<deadline:
                resumed = get(base,"/experiments/fuzzy-resume-smoke")
                if resumed["status"] != "RUNNING": break
                time.sleep(.1)
            assert resumed["status"] == "COMPLETED", resumed
            new_rounds = get(base,"/experiments/fuzzy-resume-smoke/rounds")
            assert len(new_rounds) == 12 and new_rounds[:committed] == old_rounds
            assert new_rounds[committed]["fairnessCredits"] == recovered["snapshot"]["fuzzySelectionState"]["deficits"]
            replay_fuzzy(new_rounds,resumed)
            summary = dict(status="PASS", protocol="LAMBDA_SYNTHETIC_SMOKE_ONLY" if lambda_ablation else "SYNTHETIC_SMOKE_ONLY", experiments=expected_experiments, roundsPerExperiment=3,
                           seeds=[42,43], pairedInitialWeights="verified", sharedTraces="verified",
                           independentNumericalAndCreditReplay="verified", liveProcessRestartResume={"status":"verified", "restartAfterRound":committed,"finalRound":12},
                           report=str(report), evidence=str(folder))
            (folder/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
            print(json.dumps(summary),flush=True)
        finally:
            for process in (server,worker):
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lambda-ablation",action="store_true",help="Verify L0-L5 lambda policies, stability report and slots-changed metrics")
    verify(parser.parse_args().lambda_ablation)
