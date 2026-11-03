"""Isolated synthetic smoke of the actual IntelliJ entry point + manual worker.

Creates its own pilot/frozen JAR/database. Never starts or modifies production E3.
"""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
import psutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fuzzy_uncertainty_workflow import atomic
from research_watchdog import source_identity
from verify_fuzzy import free_port, get
from verify_fuzzy_recovery import stop_tree, wait_health

ROOT = Path(__file__).resolve().parents[1]


def main(timeout_recovery=False):
    folder = ROOT / "artifacts/frozen-e3-ide-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    config = json.loads((ROOT / "configurations/fuzzy-uncertainty.json").read_text())
    config.pop("mode", None)
    config.update(dataset="synthetic", rounds=3, trainingSeeds=[42], scenarios=["U0"], evidenceDatabases=[],
        minimumFreeDiskGB=.05, confirmationAlphas=[.5], confirmationPartitions=[3001], confirmationSeeds=[42])
    atomic(folder / "protocol.json", config)
    atomic(folder / "source-identity.json", source_identity())
    current_jar = ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar"
    shutil.copyfile(current_jar, folder / "coordinator.jar")
    from resume_frozen_e3 import file_hash
    atomic(folder / "build-identity.json", {"jarSHA256": file_hash(folder / "coordinator.jar")})
    java_port, worker_port = free_port(), free_port()
    worker_base, base = f"http://127.0.0.1:{worker_port}", f"http://127.0.0.1:{java_port}"
    armed = threading.Event()
    delayed = threading.Event()
    gate = threading.Lock()
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def forward(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            try:
                with urlopen(Request(worker_base+self.path, data=body, method=self.command, headers={"Content-Type": "application/json"}), timeout=90) as response:
                    code, payload = response.status, response.read()
            except HTTPError as error:
                code, payload = error.code, error.read()
            except OSError as error:
                code, payload = 503, json.dumps({"detail": str(error)}).encode()
            hold = False
            if self.path == "/train" and code == 200 and armed.is_set():
                with gate:
                    if not delayed.is_set():
                        delayed.set();hold = True
            if hold:
                # The receipt is already durable. Force the API transport budget
                # to expire without changing any scientific request or outcome.
                time.sleep(8)
            try:
                self.send_response(code);self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)));self.end_headers();self.wfile.write(payload)
            except (BrokenPipeError, ConnectionError):
                pass
        do_GET = forward
        do_POST = forward
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy) if timeout_recovery else None
    if proxy:
        threading.Thread(target=proxy.serve_forever, daemon=True).start()
    gateway = f"http://127.0.0.1:{proxy.server_port}" if proxy else worker_base
    env = dict(os.environ, MINIFLS_WORKSPACE=str(ROOT), MINIFLS_DATABASE=str(folder / "experiments.db"),
        MINIFLS_SERVER_PORT=str(java_port), MINIFLS_WORKER_URL=gateway, MINIFLS_LAUNCH_ENABLED="false",
        MINIFLS_METHOD="none", MINIFLS_FUZZY_BATCH=str(folder), MINIFLS_FUZZY_MODE="pilot", PYTHONUTF8="1",
        MINIFLS_TORCH_THREADS="1", MINIFLS_WORKER_MAX_ATTEMPTS="8", MINIFLS_WORKER_RETRY_DELAY_MS="2000",
        MINIFLS_WORKER_RETRY_MAX_DELAY_MS="30000", MINIFLS_WORKER_REQUEST_TIMEOUT_SECONDS="1800",
        MINIFLS_WORKER_RECOVERY_BUDGET_SECONDS="900", MINIFLS_WORKER_RETRY_JITTER="0")
    if timeout_recovery:
        env.update(MINIFLS_WORKER_REQUEST_TIMEOUT_SECONDS="5", MINIFLS_WORKER_RECOVERY_BUDGET_SECONDS="5")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = server = launcher = None
    probe_children = []
    with (folder / "worker.log").open("w", encoding="utf-8") as wlog, (folder / "pilot.log").open("w", encoding="utf-8") as plog:
        try:
            # Exact manual-worker invocation, with a private port only for isolation.
            worker = subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(worker_port)],
                cwd=ROOT, env=env, stdout=wlog, stderr=wlog, **flags)
            wait_health(worker_base, worker)
            server = subprocess.Popen(["java", "-Xmx512m", "-XX:ActiveProcessorCount=2", "-jar", str(folder / "coordinator.jar")],
                cwd=ROOT, env=env, stdout=plog, stderr=plog, **flags)
            wait_health(base, server)
            pilot = subprocess.run([sys.executable, "-u", "scripts/fuzzy_uncertainty_workflow.py"], cwd=ROOT, env=env,
                stdout=plog, stderr=plog, timeout=240, **flags)
            assert pilot.returncode == 0, f"Pilot fixture failed: {folder}"
            assert json.loads((folder / "completion.json").read_text())["mode"] == "pilot"
            stop_tree(server);server = None
            frozen_files = {name: (folder / name).read_bytes() for name in
                ("protocol.json", "policy-lock.json", "source-identity.json", "runtime-identity.json", "build-identity.json")}
            def counts():
                with sqlite3.connect(folder / "experiments.db") as db:
                    return db.execute("SELECT count(*) FROM rounds").fetchone()[0]
            pilot_rounds = counts()
            def command(budget, worker_url=gateway):
                return ["java", "-Xmx128m", "-Dloader.main=com.huanphan.ferderatedsystem.FrozenE3IdeLauncher", "-cp", str(current_jar),
                    "org.springframework.boot.loader.launch.PropertiesLauncher", f"--workspace={ROOT}", f"--batch={folder}",
                    f"--server-port={java_port}", f"--worker-url={worker_url}", f"--run-budget={budget}",
                    f"--lock-directory={folder / 'locks'}", f"--java={shutil.which('java')}"]
            # Simulate a hard IntelliJ Stop while waiting for a worker. No training
            # can start on this private absent worker URL; the real worker is untouched.
            absent = f"http://127.0.0.1:{free_port()}"
            with (folder / "ownership.log").open("w", encoding="utf-8") as log:
                launcher = subprocess.Popen(command(0, absent), cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
                deadline = time.monotonic()+90
                while True:
                    assert launcher.poll() is None
                    try:
                        get(base, "/experiments");break
                    except OSError:
                        assert time.monotonic()<deadline
                        time.sleep(.1)
                probe_children = psutil.Process(launcher.pid).children(recursive=True)
                launcher.kill();launcher.wait(timeout=15);launcher = None
                deadline = time.monotonic()+15
                while any(p.is_running() for p in probe_children):
                    assert time.monotonic()<deadline, "Hard-stopped IDE launcher left an API/controller child alive"
                    time.sleep(.1)
            assert worker.poll() is None and get(worker_base, "/health")["status"] == "ok"
            if timeout_recovery:
                armed.set()
            def launch(name, budget):
                nonlocal launcher
                with (folder / (name + ".log")).open("w", encoding="utf-8") as log:
                    launcher = subprocess.Popen(command(budget), cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
                    code = launcher.wait(timeout=240)
                    assert code == 0, f"IDE launcher {name} exited {code}: {folder}"
                    launcher = None
                assert worker.poll() is None and get(worker_base, "/health")["status"] == "ok", "Launcher stopped the manual worker"
                for filename, content in frozen_files.items():
                    assert (folder / filename).read_bytes() == content, f"Frozen metadata was changed: {filename}"
                log_text = (folder / (name + ".log")).read_text(encoding="utf-8")
                assert "no pilot/report replay" in log_text
                assert "E2 pilot:" not in log_text
            launch("budget", 1)
            if timeout_recovery:
                assert delayed.is_set(), "No successful response was held for timeout injection"
                text = (folder / "budget.log").read_text(encoding="utf-8")
                assert "[E3-RECOVERY] Verified checkpoint=" in text
            assert json.loads((folder / "status.json").read_text())["workflowStatus"] == "BUDGET_REACHED"
            assert counts() == pilot_rounds + config["rounds"]
            launch("resume", 0)
            lock = json.loads((folder / "policy-lock.json").read_text())
            expected = len(lock["policies"])*config["rounds"]
            assert counts() == pilot_rounds + expected
            assert json.loads((folder / "completion.json").read_text())["mode"] == "full"
            assert json.loads((folder / "status.json").read_text())["workflowStatus"] == "COMPLETED"
            with sqlite3.connect(folder / "experiments.db") as db:
                assert not db.execute("SELECT experiment_id,round_id FROM rounds GROUP BY experiment_id,round_id HAVING count(*)>1").fetchall()
            print(f"Frozen E3 IntelliJ/manual-worker smoke PASS: {folder}", flush=True)
            atomic(folder / "summary.json", dict(status="PASS", checks=["actual Java IDE main", "manual worker remains alive", "unchanged frozen identities",
                "budget resume", "no pilot retraining or replay", "no duplicate round commits", "final reports", "hard IDE stop cleans API/controller children"],
                transportBudgetExhaustionRecovery=timeout_recovery, committedRounds=counts()))
        finally:
            stop_tree(launcher);stop_tree(server);stop_tree(worker)
            for child in probe_children:
                try:
                    if child.is_running():child.kill()
                except psutil.NoSuchProcess:
                    pass
            if proxy:
                proxy.shutdown();proxy.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-recovery", action="store_true")
    main(parser.parse_args().timeout_recovery)
