"""IntelliJ/manual-Uvicorn resume of validated E3, using the original frozen runtime.

No policy selection, pilot training or intermediate report regeneration. The
original Workflow admission, receipt, checkpoint and retry code remains in use.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
import traceback

import psutil
from fuzzy_uncertainty_workflow import ROOT, Workflow, BudgetReached, atomic, digest, immutable, transient
from research_watchdog import run_lock


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_frozen_files(folder):
    saved = json.loads((folder / "source-identity.json").read_text(encoding="utf-8"))
    for relative, expected in saved.items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or file_hash(path) != expected:
            raise RuntimeError(f"Frozen source differs: {relative}")
    build = json.loads((folder / "build-identity.json").read_text(encoding="utf-8"))
    if file_hash(folder / "coordinator.jar") != build["jarSHA256"]:
        raise RuntimeError("Frozen JAR checksum mismatch")


def owner_is_alive(pid, started_ms):
    try:
        return abs(psutil.Process(pid).create_time()-started_ms/1000) < 2
    except psutil.NoSuchProcess:
        return False


def watch_ide_owner():
    """If IntelliJ forcibly kills the launcher, stop its API server, never the worker."""
    owner = os.environ.get("MINIFLS_IDE_OWNER_PID")
    if not owner:
        return
    pid, birth = int(owner), int(os.environ["MINIFLS_IDE_OWNER_STARTED_MS"])
    server = psutil.Process(int(os.environ["MINIFLS_IDE_SERVER_PID"]))
    server_birth = server.create_time()
    def monitor():
        while owner_is_alive(pid, birth):
            time.sleep(1)
        try:
            if server.create_time() == server_birth:
                for child in reversed(server.children(recursive=True)):
                    child.terminate()
                server.terminate()
        except psutil.NoSuchProcess:
            pass
        print("[IDE] Launcher stopped; the frozen API server was stopped. Checkpoints remain intact.", flush=True)
        os._exit(130)
    threading.Thread(target=monitor, daemon=True).start()


class FrozenE3Controller(Workflow):
    def __init__(self):
        super().__init__()
        if self.mode != "full":
            raise RuntimeError("Frozen E3 resume requires full mode")
        self.partition_cache = {}

    def partition(self, alpha, partition):
        key = (alpha, partition)
        if key not in self.partition_cache:
            print(f"[E3-PREFLIGHT] Verify partition alpha={alpha} seed={partition}", flush=True)
            self.partition_cache[key] = super().partition(alpha, partition)
        return self.partition_cache[key]

    def ready(self):
        done = threading.Event()
        def heartbeat():
            while not done.wait(15):
                print("[E3-PREFLIGHT] Waiting for compatible frozen Java server and manual Uvicorn worker...", flush=True)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            super().ready()
        finally:
            done.set(); thread.join(timeout=2)

    def validate_lock(self):
        lock = json.loads((self.folder / "policy-lock.json").read_text(encoding="utf-8"))
        if lock["protocolHash"] != digest(self.config) or lock["runtime"] != self.runtime:
            raise RuntimeError("Locked protocol/runtime differs; refusing migration or retuning")
        expected = dict(alphas=self.config["confirmationAlphas"], partitions=self.config["confirmationPartitions"],
            seeds=self.config["confirmationSeeds"], scenario="U0", checkpoint="final round only")
        if lock["confirmation"] != expected or lock["policies"] not in (["C1", "C4"], ["C1", "C4", "C5"]):
            raise RuntimeError("Unexpected confirmation policy lock")
        if self.config["validationPartitionSeed"] in expected["partitions"]:
            raise RuntimeError("Validation and confirmation partitions overlap")
        if any(self.state["stages"].get(stage) != "COMPLETED" for stage in ("E2", "E4", "POLICY_LOCK")):
            raise RuntimeError("Complete validation and lock policies before using frozen E3 resume")
        audit = json.loads((self.folder / "e0-reproducibility-audit.json").read_text(encoding="utf-8"))
        if audit.get("status") != "PASS" or audit["runtime"] != self.runtime or audit["protocolHash"] != digest(self.config):
            raise RuntimeError("Missing/incompatible executing-build reproducibility audit")
        immutable(self.folder / "confirmation-protocol.json", dict(policyLockHash=digest(lock),
            expectedRuns=len(lock["policies"])*len(expected["alphas"])*len(expected["partitions"])*len(expected["seeds"]),
            protocol=self.config))
        return lock

    def report(self):
        done = threading.Event()
        def heartbeat():
            while not done.wait(15):
                print("[REPORT] Final evidence export is still running; training has completed.", flush=True)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            return super().report()
        finally:
            done.set(); thread.join(timeout=2)

    def execute(self):
        self.stage = "E3-PREFLIGHT"
        self.status(workflowStatus="RUNNING", lastError=None, currentExperimentId=None, currentRound=None,
                    nextResumeAction="verify frozen E3 identities")
        print("[E3-PREFLIGHT] Verify frozen source, runtime and saved policy lock; no pilot/report replay.", flush=True)
        verify_frozen_files(self.folder)
        self.ready()
        self.lock = self.validate_lock()
        lock_hash = file_hash(self.folder / "policy-lock.json")
        protocol_hash = file_hash(self.folder / "protocol.json")
        total = len(self.lock["policies"])*len(self.config["confirmationAlphas"])*len(self.config["confirmationPartitions"])*len(self.config["confirmationSeeds"])
        completed = sum(r["stage"] == "E3" and r["status"] == "COMPLETED" for r in self.state["runs"].values())
        print(f"[E3] Locked matrix {total} runs x {self.config['rounds']} rounds; completed={completed}. Resume only unfinished work.", flush=True)
        remaining = total-completed
        run_budget = int(os.environ.get("MINIFLS_FUZZY_RUN_BUDGET", "0"))
        round_budget = int(os.environ.get("MINIFLS_FUZZY_ROUND_BUDGET", "0"))
        if run_budget < 0 or round_budget < 0:
            raise ValueError("Budgets cannot be negative")
        if run_budget:
            remaining = min(remaining, run_budget)
        if round_budget:
            # Reserve at least one resumable partial run if its committed prefix fits the budget.
            remaining = min(remaining, max(1, round_budget//self.config["rounds"]))
        required = max(self.config["minimumFreeDiskGB"]*1024**3,
            remaining*self.config["rounds"]*(self.config["selectedPerRound"]+1)*350000 +
            len(self.config["confirmationAlphas"])*len(self.config["confirmationPartitions"])*160*1024**2)
        if shutil.disk_usage(self.folder).free < required:
            raise RuntimeError(f"Insufficient disk for E3 admission: require about {required/1024**3:.1f} GiB free")
        lineage = dict(mode="INTELLIJ_FROZEN_E3", controllerSHA256=file_hash(Path(__file__)),
            launcherClassSHA256=os.environ.get("MINIFLS_IDE_LAUNCHER_CLASS_SHA256"),
            frozenSourceIdentitySHA256=file_hash(self.folder / "source-identity.json"),
            frozenJarSHA256=file_hash(self.folder / "coordinator.jar"), policyLockSHA256=lock_hash,
            scientificRuntime=self.runtime, changes="Launch/resume scheduling only; no scientific code or policy changes")
        atomic(self.folder / "launchers" / f"ide-{time.time_ns()}.json", lineage)
        # Use the original exact config/trace builder. Validate each dataset only once per launch.
        runs = []
        for alpha in self.config["confirmationAlphas"]:
            for partition in self.config["confirmationPartitions"]:
                for seed in self.config["confirmationSeeds"]:
                    for policy in self.lock["policies"]:
                        runs.append(self.experiment("E3", policy, "U0", seed, alpha, partition))
                        if len(runs) % 15 == 0 or len(runs) == total:
                            print(f"[E3-PREFLIGHT] Config/trace identity verified {len(runs)}/{total}", flush=True)
        self.stage = "E3"
        self.status(lastError=None, workerStatus="READY", nextResumeAction="resume committed E3 checkpoints")
        for run in runs:
            self.run(run)
        if file_hash(self.folder / "policy-lock.json") != lock_hash or file_hash(self.folder / "protocol.json") != protocol_hash:
            raise RuntimeError("Frozen policy lock/protocol changed during execution")
        self.state["stages"]["E3"] = "COMPLETED"
        self.stage = "REPORT"
        self.status(nextResumeAction="final E3 reports")
        print("[REPORT] All E3 runs committed; generate final reports once.", flush=True)
        self.report()
        self.status(workflowStatus="COMPLETED", lastError=None, nextResumeAction="none")
        atomic(self.folder / "completion.json", dict(mode="full", status="COMPLETED", time=time.time()))


def main():
    workflow = FrozenE3Controller()
    try:
        watch_ide_owner()
        with run_lock(workflow.folder / "workflow.lock"):
            workflow.execute()
        return 0
    except BudgetReached:
        workflow.status(workflowStatus="BUDGET_REACHED", lastError=None,
                        nextResumeAction="rerun IntelliJ configuration; no intermediate report regeneration")
        print("[E3] Admission budget reached; committed checkpoints saved. Resume with the same IDE configuration.", flush=True)
        return 0
    except Exception as error:
        traceback.print_exc()
        recoverable = transient(str(error))
        workflow.status(workflowStatus="RETRYABLE_FAILURE" if recoverable else "BLOCKED", lastError=str(error),
                        nextResumeAction="restart manual worker/IDE using the same frozen runtime" if recoverable else "inspect blocker; retain original evidence")
        return 75 if recoverable else 20


if __name__ == "__main__":
    raise SystemExit(main())
