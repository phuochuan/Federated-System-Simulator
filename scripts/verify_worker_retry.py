"""Fault-injection smoke: lose a successful /train reply, then retry safely.

Synthetic, 2 rounds only. Isolated services/database; existing worker is untouched.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

from minifls.data import prepare
from verify_fuzzy import free_port, get, post
from verify_research import stop

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "artifacts/worker-retry-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    prepare(folder / "partition", dataset="synthetic", clients=100)
    worker_port = free_port()
    worker_base = f"http://127.0.0.1:{worker_port}"
    replies = []
    bodies = []
    dropped = False
    gate = threading.Lock()

    class Proxy(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def forward(self):
            nonlocal dropped
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            req = Request(worker_base+self.path, data=body, method=self.command, headers={"Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=30) as response:
                    status, result = response.status, response.read()
            except HTTPError as error:
                status, result = error.code, error.read()
            except OSError as error:
                status, result = 503, json.dumps({"detail": str(error)}).encode()
            drop = False
            if self.path == "/train" and status == 200:
                with gate:
                    if not dropped:
                        dropped = True
                        bodies.append(body)
                        replies.append(json.loads(result))
                        drop = True
                    elif body == bodies[0]:
                        bodies.append(body)
                        replies.append(json.loads(result))
            if drop:
                # The upstream has already committed its checkpoint and receipt.
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(result)
            self.close_connection = True

        do_GET = forward
        do_POST = forward

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    server_port = free_port()
    while server_port in (worker_port, proxy.server_port):
        server_port = free_port()
    base = f"http://127.0.0.1:{server_port}"
    env = {**os.environ, "MINIFLS_WORKSPACE": str(ROOT), "MINIFLS_WORKER_URL": f"http://127.0.0.1:{proxy.server_port}",
           "MINIFLS_SERVER_PORT": str(server_port), "MINIFLS_DATABASE": str(folder / "test.db"),
           "MINIFLS_TORCH_THREADS": "1", "MINIFLS_LAUNCH_ENABLED": "false", "MINIFLS_METHOD": "none",
           "MINIFLS_WORKER_MAX_ATTEMPTS": "4", "MINIFLS_WORKER_RETRY_DELAY_MS": "100",
           "MINIFLS_WORKER_RETRY_MAX_DELAY_MS": "500", "MINIFLS_LOG_LEVEL": "INFO"}
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = server = None
    with (folder / "worker.log").open("w", encoding="utf-8") as worker_log, (folder / "java.log").open("w", encoding="utf-8") as java_log:
        try:
            worker = subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(worker_port), "--workers", "1"], cwd=ROOT, env=env, stdout=worker_log, stderr=worker_log, **flags)
            deadline = time.monotonic()+120
            while True:
                if worker.poll() is not None:
                    raise RuntimeError(f"Worker exited; inspect {folder}")
                try:
                    get(worker_base, "/health")
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Worker startup")
                    time.sleep(.25)
            server = subprocess.Popen(["java", "-Xmx384m", "-jar", str(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")], cwd=ROOT, env=env, stdout=java_log, stderr=java_log, **flags)
            deadline = time.monotonic()+120
            while True:
                if worker.poll() is not None or server.poll() is not None:
                    raise RuntimeError(f"Service exited; inspect {folder}")
                try:
                    get(base, "/health")
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Startup")
                    time.sleep(.25)
            config = json.loads((ROOT / "configurations/smoke.json").read_text())
            config.update(experimentId="retry-"+folder.name, manifestPath=(folder / "partition").relative_to(ROOT).as_posix(), rounds=2)
            post(base, "/experiments", config)
            deadline = time.monotonic()+120
            while True:
                state = get(base, "/experiments/"+config["experimentId"])
                if state["status"] != "RUNNING":
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("Experiment")
                time.sleep(.25)
            assert state["status"] == "COMPLETED", state.get("error")
            rounds = get(base, "/experiments/"+config["experimentId"]+"/rounds")
            assert [r["roundId"] for r in rounds] == [1, 2]
            assert dropped and len(bodies) == 2 and bodies[0] == bodies[1]
            assert replies[0] == replies[1]  # Same tensor hash AND original actualTrainingMs.
            target = ROOT / replies[0]["updatePath"]
            assert target.exists() and target.with_suffix(".response.json").exists()
            assert len(list(target.parent.glob("*.pt"))) == 13  # initial + 10 clients + 2 global checkpoints
            assert "worker.retry method=POST route=/train" in (folder / "java.log").read_text(encoding="utf-8")
            report = {"status": "PASS", "syntheticRounds": 2, "lostSuccessfulReplies": 1,
                      "sameRequestAndOperationId": True, "sameOriginalResponse": True, "duplicateCheckpoints": 0,
                      "checkpoint": replies[0]["updatePath"], "modelStateHash": replies[0]["modelStateHash"]}
            (folder / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Worker retry fault-injection smoke PASS: {folder}", flush=True)
        finally:
            stop(server)
            stop(worker)
            proxy.shutdown()
            proxy.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
