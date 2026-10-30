"""Windows supervisors with workspace-wide OS locks and an explicit exit contract.

0: completed or deliberate budget stop. 20: fatal/integrity/configuration blocker.
75: transient controller failure. A Java VM crash may restart within the sliding
budget, but a persisted BLOCKED status always stops. No checkpoint cleanup occurs.
"""
from collections import deque
from contextlib import contextmanager
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid

from fuzzy_uncertainty_workflow import ROOT, atomic, digest, immutable


@contextmanager
def run_lock(path, wait=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    if path.stat().st_size == 0:
        stream.write(b"0"); stream.flush()
    deadline = time.monotonic() + wait
    try:
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Another research process holds {path}")
                time.sleep(.2)
        yield
    finally:
        stream.close()


def source_identity():
    files = list((ROOT / "ferderatedsystem/src/main").rglob("*")) + list((ROOT / "ml-python/minifls").rglob("*.py"))
    files += [ROOT / "scripts" / name for name in ("research_watchdog.py", "fuzzy_uncertainty_workflow.py", "fuzzy_uncertainty_reports.py", "run_fl_research_java.ps1", "run_fl_research_worker.ps1")]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file() and "__pycache__" not in p.parts}


def prepare():
    config_path = ROOT / os.environ.get("MINIFLS_FUZZY_CONFIG", "configurations/fuzzy-uncertainty.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    mode = os.environ.get("MINIFLS_FUZZY_MODE", config.pop("mode", "pilot"))
    config.pop("mode", None)
    if mode not in ("pilot", "full", "report-only"):
        raise ValueError("Invalid workflow mode")
    output = (ROOT / os.environ.get("MINIFLS_FUZZY_OUTPUT", "artifacts/research/fuzzy-uncertainty")).resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Output root must stay in workspace")
    with run_lock(output / "bootstrap.lock", 120):
        pointer = output / "active-batch.json"
        if pointer.exists():
            batch = Path(json.loads(pointer.read_text(encoding="utf-8"))["folder"])
            if not batch.resolve().is_relative_to(output):
                raise ValueError("Batch pointer escapes output root")
        else:
            batch = output / ("fuzzy-uncertainty-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
            batch.mkdir(parents=True)
            atomic(pointer, {"folder": str(batch)})
        immutable(batch / "protocol.json", config)
        immutable(batch / "source-identity.json", source_identity())
    return batch, config, mode


def port_free(port):
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} already has a listener; refusing duplicate service")


class RestartBudget:
    def __init__(self, limit, window):
        self.limit, self.window = limit, window
        self.events = deque()

    def admit(self, now):
        while self.events and self.events[0] <= now-self.window:
            self.events.popleft()
        if len(self.events) >= self.limit:
            return False
        self.events.append(now)
        return True


def completed(batch, mode):
    path = batch / "completion.json"
    if not path.exists():
        return False
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get("status") == "COMPLETED" and (value.get("mode") == "full" or value.get("mode") == mode)


def supervise(role, batch, config, mode):
    if role == "worker" and mode == "report-only":
        return 0
    if completed(batch, mode) and mode != "report-only":
        print(f"Workflow already completed: {batch}", flush=True)
        return 0
    logger = logging.getLogger(role)
    logger.setLevel(logging.INFO)
    logpath = batch / "logs" / (role + ".log")
    logpath.parent.mkdir(exist_ok=True)
    handler = RotatingFileHandler(logpath, maxBytes=8*1024**2, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    env = dict(os.environ, MINIFLS_WORKSPACE=str(ROOT), MINIFLS_FUZZY_BATCH=str(batch), MINIFLS_FUZZY_MODE=mode,
        MINIFLS_DATABASE=str(batch / "experiments.db"), MINIFLS_METHOD="fuzzy_uncertainty_workflow", MINIFLS_LAUNCH_ENABLED="true",
        MINIFLS_TORCH_THREADS=str(config["torchThreads"]), OMP_NUM_THREADS=str(config["torchThreads"]), MKL_NUM_THREADS=str(config["torchThreads"]),
        MINIFLS_WORKER_REQUEST_TIMEOUT_SECONDS=str(config["requestTimeoutSeconds"]), MINIFLS_WORKER_RECOVERY_BUDGET_SECONDS=str(config["recoverySeconds"]), PYTHONUTF8="1")
    env.setdefault("MINIFLS_WORKER_MAX_ATTEMPTS", "8")
    env.setdefault("MINIFLS_WORKER_RETRY_DELAY_MS", "2000")
    env.setdefault("MINIFLS_WORKER_RETRY_MAX_DELAY_MS", "30000")
    env.setdefault("MINIFLS_SERVER_PORT", "8080")
    env.setdefault("MINIFLS_WORKER_URL", "http://127.0.0.1:8000")
    if role == "java":
        jar = batch / "coordinator.jar"
        if not jar.exists():
            if mode == "report-only":
                raise RuntimeError("No immutable batch build available")
            command = [str(ROOT / "ferderatedsystem/gradlew.bat"), "-p", str(ROOT / "ferderatedsystem"), "bootJar", "--no-daemon"]
            subprocess.run(command, cwd=ROOT, check=True)
            source = ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar"
            temporary = jar.with_suffix(".tmp")
            shutil.copyfile(source, temporary)
            temporary.replace(jar)
        jarhash = hashlib.sha256(jar.read_bytes()).hexdigest()
        immutable(batch / "build-identity.json", dict(jarSHA256=jarhash))
        command = ["java", "-Xms128m", "-Xmx512m", "-XX:ActiveProcessorCount=2", "-jar", str(jar)]
        port = int(env["MINIFLS_SERVER_PORT"])
    else:
        from urllib.parse import urlparse
        parsed = urlparse(env["MINIFLS_WORKER_URL"])
        if parsed.hostname != "127.0.0.1":
            raise ValueError("Watchdog requires a local worker")
        port = parsed.port or 8000
        command = [sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"]
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    budget = RestartBudget(config["restartLimit"], config["restartWindowSeconds"])
    # Restart budget survives wrapper restarts too.
    history_path = batch / (role + "-restart-history.json")
    if history_path.exists():
        budget.events.extend(json.loads(history_path.read_text(encoding="utf-8")))
    supervisor_started = time.time()
    while True:
        immutable(batch / "source-identity.json", source_identity())
        port_free(port)
        logger.info("process.start role=%s batch=%s", role, batch)
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", **flags)
        def pump():
            for line in process.stdout:
                logger.info(line.rstrip())
                if (role == "java" and (line.startswith("[E") or line.startswith("[AUDIT") or " ERROR " in line or " WARN " in line or line.startswith("Traceback"))) or (role == "worker" and ("ERROR" in line or "WARNING" in line)):
                    print(line, end="", flush=True)
        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        descendants = {}
        try:
            while process.poll() is None:
                import psutil
                try:
                    for child in psutil.Process(process.pid).children(recursive=True):
                        descendants[child.pid] = child.create_time()
                except psutil.NoSuchProcess:
                    pass
                if role == "worker":
                    status_path = batch / "status.json"
                    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
                    if completed(batch, mode) or (status.get("updatedAt", 0) >= supervisor_started and status.get("workflowStatus") in ("BLOCKED", "BUDGET_REACHED", "REPORT_ONLY_COMPLETED")):
                        process.terminate()
                        process.wait(timeout=30)
                        return 0 if status.get("workflowStatus") != "BLOCKED" else 20
                time.sleep(.2)
            code = process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            # A crashed JVM must not leave a second batch controller running.
            import psutil
            for pid, birth in reversed(list(descendants.items())):
                try:
                    child=psutil.Process(pid)
                    if child.create_time()==birth:
                        child.kill()
                except psutil.NoSuchProcess:
                    pass
            thread.join(timeout=5)
            process.stdout.close()
        logger.info("process.exit role=%s code=%s", role, code)
        if role == "java" and code == 0:
            return 0
        status_path = batch / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        if code == 20 or status.get("workflowStatus") == "BLOCKED":
            raise RuntimeError("Workflow stopped on a fatal/integrity blocker; inspect status.json")
        if not budget.admit(time.time()):
            atomic(batch / (role + "-blocker.json"), dict(status="BLOCKED", reason="Sliding process restart budget exhausted", exitCode=code))
            raise RuntimeError("Sliding process restart budget exhausted")
        atomic(history_path, list(budget.events))
        logger.warning("process.restart exitCode=%s delay=%s crashesInWindow=%s", code, config["restartDelaySeconds"], len(budget.events))
        time.sleep(config["restartDelaySeconds"])


def main():
    role = sys.argv[1]
    if role not in ("java", "worker"):
        raise ValueError("role must be java or worker")
    with run_lock(ROOT / "artifacts/research/locks" / (role + ".lock")):
        batch, config, mode = prepare()
        print(f"[{role}] batch={batch} mode={mode}", flush=True)
        if role == "worker":
            # Validate all ML imports before entering the process restart loop.
            subprocess.run([sys.executable, "-c", "import torch, fastapi, uvicorn, simpy, sklearn, minifls"], check=True)
        return supervise(role, batch, config, mode)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as error:
        print(f"BLOCKED: {error}", file=sys.stderr, flush=True)
        sys.exit(20)
