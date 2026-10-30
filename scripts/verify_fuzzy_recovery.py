"""Kill a real worker inside training, then kill Java inside an uncommitted round.

Isolated synthetic data/ports/database. Checks preserved committed evidence and
deterministic final tensors against an uninterrupted reference. No research run.
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

import psutil
from minifls.data import prepare
from verify_fuzzy import free_port, get, post

ROOT = Path(__file__).resolve().parents[1]


def stop_tree(process):
    if process is None:
        return
    try:
        descendants = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []
    for child in reversed(descendants):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=30)


def wait_health(base, process, timeout=90):
    deadline = time.monotonic()+timeout
    while True:
        assert process.poll() is None, "Service exited during readiness"
        try:
            return get(base, "/health")
        except (OSError, ConnectionError):
            if time.monotonic()>deadline:
                raise TimeoutError("readiness")
            time.sleep(.1)


def main():
    folder = ROOT / "artifacts/fuzzy-recovery-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    prepare(folder / "partition", dataset="synthetic", clients=100)
    worker_port, java_port = free_port(), free_port()
    worker_base, java_base = f"http://127.0.0.1:{worker_port}", f"http://127.0.0.1:{java_port}"
    first_train = threading.Event()
    bodies = []

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            if self.path == "/train":
                bodies.append(body)
                first_train.set()
            try:
                with urlopen(Request(worker_base+self.path, data=body, headers={"Content-Type": "application/json"}, method=self.command), timeout=90) as response:
                    status, payload = response.status, response.read()
            except HTTPError as error:
                status, payload = error.code, error.read()
            except OSError as error:
                status, payload = 503, json.dumps({"detail": str(error)}).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers();self.wfile.write(payload)
            except (BrokenPipeError, ConnectionError):
                pass
        do_GET = forward
        do_POST = forward

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    env = dict(os.environ, MINIFLS_WORKSPACE=str(ROOT), MINIFLS_DATABASE=str(folder / "test.db"),
               MINIFLS_WORKER_URL=f"http://127.0.0.1:{proxy.server_port}", MINIFLS_SERVER_PORT=str(java_port),
               MINIFLS_LAUNCH_ENABLED="false", MINIFLS_TORCH_THREADS="1", MINIFLS_WORKER_MAX_ATTEMPTS="30",
               MINIFLS_WORKER_RETRY_DELAY_MS="500", MINIFLS_WORKER_RETRY_MAX_DELAY_MS="1000", PYTHONUTF8="1")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = server = None
    with (folder / "worker.log").open("w", encoding="utf-8") as wlog, (folder / "java.log").open("w", encoding="utf-8") as jlog:
        def start_worker():
            return subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(worker_port), "--workers", "1"], cwd=ROOT, env=env, stdout=wlog, stderr=wlog, **flags)
        def start_java():
            return subprocess.Popen(["java", "-Xmx384m", "-jar", str(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")], cwd=ROOT, env=env, stdout=jlog, stderr=jlog, **flags)
        try:
            worker = start_worker();wait_health(worker_base, worker)
            server = start_java();wait_health(java_base, server)
            runtime = get(java_base, "/research/runtime")
            config = json.loads((ROOT / "configurations/smoke.json").read_text())
            config.update(experimentId="recovery-"+folder.name, manifestPath=(folder / "partition").relative_to(ROOT).as_posix(),
                rounds=2, selectedPerRound=1, localEpochs=100, batchSize=1, simulationEnabled=False, selection="fuzzy_topsis",
                timing={"mode": "deterministic", "secondsPerSample": .0005}, evaluationSplit="proxy", finalEvaluationSplit="proxy",
                fuzzySelection={"weights": {"estimatedTime": .4, "reliability": .35, "learningUtility": .25}, "uncertaintyMode": "error_calibrated"},
                provenance={"runtimeIdentity": runtime})
            identifier = config["experimentId"]
            post(java_base, "/experiments", config)
            assert first_train.wait(45), "No train dispatch"
            deadline = time.monotonic()+10
            while not get(worker_base, "/health")["busy"]:
                assert time.monotonic()<deadline
                time.sleep(.002)
            # Local epochs=100,batch=1 deliberately leaves time to kill before commit.
            stop_tree(worker)
            assert not list((ROOT / "artifacts/models" / identifier).glob("r0001_client*.pt")), "Kill was too late"
            worker = start_worker();wait_health(worker_base, worker)
            deadline = time.monotonic()+120
            while True:
                state = get(java_base, "/experiments/"+identifier)
                if (state.get("snapshot") or {}).get("round", 0) >= 1:
                    break
                assert state["status"] == "RUNNING", state.get("error")
                assert time.monotonic()<deadline
                time.sleep(.02)
            assert state["snapshot"]["round"] == 1, "Missed Java interruption window"
            old_round = get(java_base, "/experiments/"+identifier+"/rounds")[0]
            stop_tree(server)
            server = start_java();wait_health(java_base, server)
            recovered = get(java_base, "/experiments/"+identifier)
            assert recovered["status"] == "INTERRUPTED" and recovered["snapshot"]["round"] == 1
            post(java_base, "/experiments/"+identifier+"/resume")
            deadline = time.monotonic()+120
            while True:
                state = get(java_base, "/experiments/"+identifier)
                if state["status"] != "RUNNING":
                    break
                assert time.monotonic()<deadline
                time.sleep(.1)
            assert state["status"] == "COMPLETED", state.get("error")
            evidence = get(java_base, "/experiments/"+identifier+"/rounds")
            assert [r["roundId"] for r in evidence] == [1, 2]
            assert evidence[0] == old_round
            assert state["snapshot"]["modelVersion"] == 2
            assert len(bodies) >= 3 and bodies[0] == bodies[1], "Transport retry changed request identity"
            reference = dict(config, experimentId="reference-"+folder.name)
            post(java_base, "/experiments", reference)
            deadline = time.monotonic()+120
            while True:
                other = get(java_base, "/experiments/"+reference["experimentId"])
                if other["status"] != "RUNNING":
                    break
                assert time.monotonic()<deadline
                time.sleep(.1)
            assert other["status"] == "COMPLETED", other.get("error")
            ref_result = get(java_base, "/experiments/"+reference["experimentId"]+"/result")
            assert ref_result["modelStateHash"] == evidence[-1]["modelStateHash"]
            with sqlite3.connect(folder / "test.db") as db:
                assert db.execute("SELECT count(*) FROM rounds WHERE experiment_id=?", (identifier,)).fetchone()[0] == 2
            report = dict(status="PASS", workerKilledDuringTraining=True, javaKilledAfterCommittedRound=1,
                resumedRound=2, sameRetriedRequest=True, duplicateCommits=0, uninterruptedTensorHash=ref_result["modelStateHash"])
            (folder / "summary.json").write_text(json.dumps(report, indent=2))
            print(f"Live worker/Java recovery PASS: {folder}", flush=True)
        finally:
            stop_tree(server);stop_tree(worker)
            proxy.shutdown();proxy.server_close()


if __name__ == "__main__":
    main()
