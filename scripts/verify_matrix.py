"""Real matrix smoke: eight rows, shared traces/initial weights, factorial report."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from urllib.error import URLError
from urllib.request import urlopen

from minifls.data import prepare
from minifls.model import load_checkpoint

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get(base, route):
    with urlopen(base + route, timeout=5) as response:
        return json.load(response)


def verify():
    folder = ROOT / "artifacts" / "matrix-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    iid, non_iid = folder / "iid", folder / "non-iid"
    prepare(iid, dataset="synthetic", clients=100, samples=7000)
    prepare(non_iid, dataset="synthetic", clients=100, samples=7000, strategy="dirichlet_label_skew")
    config = json.loads((ROOT / "configurations/controlled-matrix.json").read_text(encoding="utf-8"))
    config.update(iidManifestPath=iid.relative_to(ROOT).as_posix(), nonIidManifestPath=non_iid.relative_to(ROOT).as_posix(), seeds=[42, 43])
    config["baseConfig"].update(rounds=1)
    matrix_file = folder / "matrix.json"
    matrix_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    worker_port, server_port = free_port(), free_port()
    while worker_port == server_port:
        server_port = free_port()
    base, worker_base = f"http://127.0.0.1:{server_port}", f"http://127.0.0.1:{worker_port}"
    env = {**os.environ, "MINIFLS_WORKSPACE":str(ROOT), "MINIFLS_WORKER_URL":worker_base,
           "MINIFLS_SERVER_PORT":str(server_port), "MINIFLS_DATABASE":str(folder / "test.db"),
           "MINIFLS_METHOD":"matrix", "MINIFLS_MATRIX_CONFIG":str(matrix_file), "MINIFLS_MATRIX_ROUNDS":"1"}
    flags = {"creationflags":subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = server = None
    with (folder / "services.log").open("w", encoding="utf-8") as log:
        try:
            worker = subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(worker_port), "--workers", "1"],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if worker.poll() is not None:
                    raise RuntimeError("Worker exited; inspect smoke logs")
                try:
                    get(worker_base, "/health")
                    break
                except (URLError, TimeoutError):
                    time.sleep(.25)
            else:
                raise RuntimeError("Worker startup timed out")
            server = subprocess.Popen(["java", "-Xmx384m", "-jar", str(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")],
                                      cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic() + 180
            reports = []
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError("Java exited; inspect smoke logs")
                try:
                    experiments = get(base, "/experiments")
                    if len(experiments) == 16 and all(e["status"] == "COMPLETED" for e in experiments):
                        batch = experiments[0]["id"][len("matrix-"):].rsplit("-", 2)[0]
                        output = ROOT / "artifacts/comparisons" / batch
                        reports = [output / f for f in ("A-model-size.txt", "B-aggregation.txt", "C-client-selection.txt")]
                        if all(p.exists() for p in reports):
                            break
                except (URLError, TimeoutError):
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError("Matrix did not finish; inspect smoke logs")
            for report in reports:
                text = report.read_text(encoding="utf-8")
                assert "Status: COMPLETED" in text and "PAIRED QUALITY DIFFERENCES" in text
                assert "seed=42" in text and "seed=43" in text
            states = {}
            round_evidence = {}
            for experiment in experiments:
                state = get(base, f"/experiments/{experiment['id']}")
                result = get(base, f"/experiments/{experiment['id']}/result")
                assert result["roundId"] == 1
                architecture = state["config"]["architecture"]
                assert result["evaluation"]["architecture"] == architecture
                checkpoint = load_checkpoint(ROOT / state["snapshot"]["checkpointPath"])
                assert checkpoint["architecture"] == architecture
                row = experiment["id"].rsplit("-", 2)[1]
                seed = state["config"]["seed"]
                states[(row,seed)] = state
                assert architecture == ("mlp_54_128_64_7" if row == "A1" else "mlp_54_256_128_7")
                rounds = get(base, f"/experiments/{experiment['id']}/rounds")
                assert len(rounds) == 1
                round_evidence[(row,seed)] = rounds
                assert rounds[0]["serverAggregationOverheadMs"] >= rounds[0]["aggregationMs"]
                assert rounds[0]["communicationCost"] == "NOT_MODELED"
            for seed in (42,43):
                for pair in (("B1","B2"),("C1","C2"),("C1","C3"),("C1","C4")):
                    a,b = [states[(row,seed)]["snapshot"] for row in pair]
                    assert a["initialModelStateHash"] == b["initialModelStateHash"]
                    assert a["scenarioTraceHash"] == b["scenarioTraceHash"]
                    assert round_evidence[(pair[0],seed)][0]["scenarioTrace"] == round_evidence[(pair[1],seed)][0]["scenarioTrace"]
                for row in ("C1","C2","C3","C4"):
                    assert states[(row,seed)]["config"]["resourceProfile"] == "heterogeneous"
                    assert round_evidence[(row,seed)][0]["fairness"]["ramFeasiblePopulation"] == 60
            assert "INTERACTION = (C4-C3) - (C2-C1)" in reports[2].read_text(encoding="utf-8")
            summary = dict(status="PASS", experiments=16, seeds=[42,43], pairedInitialWeights="verified", sharedTraces="verified",
                           reports=[str(p) for p in reports], evidence=str(folder))
            (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary), flush=True)
        finally:
            for process in (server, worker):
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)


if __name__ == "__main__":
    verify()
