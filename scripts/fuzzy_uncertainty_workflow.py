"""Durable sequential research controller. Exit: 0 done/budget, 20 blocked, 75 transport.

Java owns all model updates and SQLite writes. This controller uses its existing
admission/resume API; analytics stream committed SQLite evidence read-only.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {"C1": ("crisp_topsis", "crisp"), "C2": ("fuzzy_topsis", "crisp"),
            "C3": ("fuzzy_topsis", "fixed"), "C4": ("fuzzy_topsis", "history_based"),
            "C5": ("fuzzy_topsis", "error_calibrated")}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows readers/AV may briefly hold the destination without delete sharing.
    # Keep the original intact and bound retries of atomic replacement only.
    for attempt in range(41):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 40:
                raise
            time.sleep(.05)


def immutable(path, value):
    if path.exists():
        if digest(json.loads(path.read_text(encoding="utf-8"))) != digest(value):
            raise RuntimeError(f"Immutable identity mismatch: {path}")
    else:
        atomic(path, value)


def transient(message):
    # Do not classify arbitrary 409/validation/provenance/JSON errors as transient.
    status = re.search(r"HTTP (\d{3}):", message)
    if status:
        code = int(status.group(1))
        if code in (502, 503, 504):
            return True
        if code == 409:
            try:
                body = json.loads(message[status.end():].strip())
                return body.get("detail") == "Worker busy; only one active ML operation allowed"
            except (ValueError, AttributeError):
                return False
        return False
    return any(token in message for token in ("Connection refused", "Connection reset", "timed out",
        "WinError 10061", "WinError 10054", "HTTP 502:", "HTTP 503:", "HTTP 504:",
        "Worker busy; only one active ML operation allowed", "java.net.ConnectException",
        "java.net.http.HttpTimeoutException", "java.io.IOException", "Remote end closed connection", "reason=interrupted"))


def api(base, route, payload=None):
    request = Request(base + route, data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=1900 if route.startswith("/datasets/") else 60) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"HTTP {error.code}: {error.read().decode()}") from error


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    return actual == expected


class BudgetReached(Exception):
    pass


class Workflow:
    def __init__(self):
        self.folder = Path(os.environ["MINIFLS_FUZZY_BATCH"]).resolve()
        self.config = json.loads((self.folder / "protocol.json").read_text(encoding="utf-8"))
        self.mode = os.environ.get("MINIFLS_FUZZY_MODE", "pilot")
        if self.mode not in ("pilot", "full", "report-only"):
            raise ValueError("mode must be pilot, full or report-only")
        self.base = "http://127.0.0.1:" + os.environ.get("MINIFLS_SERVER_PORT", "8080")
        self.worker = os.environ.get("MINIFLS_WORKER_URL", "http://127.0.0.1:8000")
        self.started = time.time()
        self.admitted = self.admitted_rounds = 0
        self.stage = "PREFLIGHT"
        self.path = self.folder / "batch-manifest.json"
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"runs": {}, "stages": {}}
        self.state.setdefault("startedAt", self.started)
        runtime_path = self.folder / "runtime-identity.json"
        self.runtime = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.exists() else None
        self.lock = None

    def status(self, **fields):
        runs = list(self.state["runs"].values())
        counts = {s: sum(r["status"] == s for r in runs) for s in
                  ("PENDING", "RUNNING", "COMPLETED", "RETRYABLE_FAILURE", "BLOCKED", "FAILED")}
        previous = self.state.get("progress", {})
        previous.update(fields)
        self.state["progress"] = previous
        status = dict(stage=self.stage, mode=self.mode, completedRuns=counts["COMPLETED"], totalRuns=len(runs),
                      counts=counts, elapsedSeconds=time.time()-self.state["startedAt"], runtimeIdentity=self.runtime,
                      updatedAt=time.time(), **previous)
        atomic(self.path, self.state)
        atomic(self.folder / "status.json", status)

    def ready(self):
        deadline = time.monotonic() + self.config["readinessSeconds"]
        while True:
            try:
                health = api(self.worker, "/health")
                runtime = api(self.base, "/research/runtime")
                if health.get("apiVersion") != "fuzzy-research-v1" or not runtime["worker"].get("idempotentCheckpointOperations"):
                    raise RuntimeError("Incompatible worker API/capabilities")
                if not runtime["worker"]["sourceFilesUnchanged"]:
                    raise RuntimeError("Worker source changed after startup")
                self.runtime = runtime
                immutable(self.folder / "runtime-identity.json", runtime)
                return
            except (URLError, TimeoutError, ConnectionError) as error:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Worker readiness timed out") from error
                self.status(workerStatus="WAITING", lastError=str(error), nextResumeAction="wait for readiness")
                time.sleep(2)

    def partition(self, alpha, partition):
        relative = (self.folder / "partitions" / f"a{alpha}-p{partition}").relative_to(ROOT).as_posix()
        manifest = api(self.worker, "/datasets/prepare", dict(output=relative, dataset=self.config["dataset"],
            clients=self.config["totalClients"], seed=self.config["splitSeed"], partitionSeed=partition, alpha=alpha))
        immutable(self.folder / "dataset-identities" / f"a{alpha}-p{partition}.json", manifest)
        return relative

    def experiment(self, stage, policy, scenario, seed, alpha=.5, partition=None, rounds=None):
        partition = self.config["validationPartitionSeed"] if partition is None else partition
        manifest = self.partition(alpha, partition)
        rounds = self.config["rounds"] if rounds is None else rounds
        key = f"{stage}-{policy}-{scenario}-s{seed}-a{alpha}-p{partition}"
        identifier = "fu-" + digest(str(self.folder))[:8] + "-" + digest(key)[:20]
        selection, uncertainty = POLICIES[policy]
        config = dict(experimentId=identifier, manifestPath=manifest, totalClients=self.config["totalClients"],
            selectedPerRound=self.config["selectedPerRound"], rounds=rounds, seed=seed, selection=selection,
            aggregation="fedavg", localEpochs=1, batchSize=32, learningRate=.01, simulationEnabled=True,
            resourceProfile="heterogeneous", availability=.9, dropout=.05, jitter=.1, exploration=0.,
            deadlineSeconds=10., requiredRamMb=600., priorSecondsPerSample=.0005, targetAccuracy=.7,
            architecture="mlp_54_256_128_7", evaluationSplit="proxy", finalEvaluationSplit="test" if stage == "E3" else "proxy",
            timing={"mode": "deterministic", "secondsPerSample": .0005},
            fuzzySelection=dict(weights=dict(estimatedTime=.4, reliability=.35, learningUtility=.25),
                uncertaintyMode=uncertainty, uncertaintyFallback=.1, uncertaintyMax=.45,
                calibrationMinHistory=5, calibrationWindow=32, calibrationQuantile=.8,
                observationNoise=dict(scenario=scenario, timing=self.config["timingUncertainty"],
                                      reliability=self.config["reliabilityUncertainty"])),
            provenance={"runtimeIdentity": self.runtime, "workflowProtocolHash": digest(self.config)})
        # Persist the complete full-population trace once per pair, using the original generator.
        tracepath = self.folder / "traces" / f"s{seed}-r{rounds}.json"
        trace = api(self.base, "/research/trace", config)
        immutable(tracepath, trace)
        config["scenarioTracePath"] = tracepath.relative_to(ROOT).as_posix()
        run = dict(key=key, stage=stage, policy=policy, scenario=scenario, seed=seed, alpha=alpha,
                   partition=partition, config=config, status="PENDING", retries=0)
        if key in self.state["runs"]:
            stored = self.state["runs"][key]
            if stored["config"] != config:
                raise RuntimeError(f"Run config mismatch: {key}")
            run = stored
        else:
            self.state["runs"][key] = run
        return run

    def run(self, run):
        c = run["config"]
        identifier = c["experimentId"]
        # Completed reuse still verifies SQLite identity, runtime and all dataset files.
        try:
            existing = api(self.base, "/experiments/" + identifier)
        except RuntimeError as error:
            if not str(error).startswith("HTTP 404:"):
                raise
            existing = None
        if existing:
            if not contains(existing["config"], c):
                raise RuntimeError("Persisted experiment config/provenance mismatch")
            if existing["status"] == "COMPLETED":
                if existing["snapshot"]["round"] != c["rounds"]:
                    raise RuntimeError("Completed experiment has incomplete snapshot")
                self.verify_completed(run, existing)
                run["status"] = "COMPLETED"
                self.status(nextResumeAction="reuse completed run")
                return
        run_budget = int(os.environ.get("MINIFLS_FUZZY_RUN_BUDGET", self.config["runBudget"]))
        round_budget = int(os.environ.get("MINIFLS_FUZZY_ROUND_BUDGET", self.config["roundBudget"]))
        remaining = c["rounds"] - ((existing or {}).get("snapshot") or {}).get("round", 0)
        if (run_budget and self.admitted >= run_budget) or (round_budget and self.admitted_rounds + remaining > round_budget):
            raise BudgetReached()
        if shutil.disk_usage(self.folder).free < self.config["minimumFreeDiskGB"] * 1024**3:
            raise RuntimeError("Insufficient free disk before experiment admission")
        self.admitted += 1
        self.admitted_rounds += remaining
        while True:
            if existing and existing["status"] in ("FAILED", "INTERRUPTED"):
                # A crash is replayable; a scientific/application error is not.
                error = existing.get("error") or ""
                if existing["status"] == "FAILED" and not transient(error):
                    run["status"] = "BLOCKED"
                    raise RuntimeError(error)
                api(self.base, "/experiments/" + identifier + "/resume", {})
            elif existing is None:
                api(self.base, "/experiments", c)
            run["status"] = "RUNNING"
            last_round = -1
            last_progress = time.monotonic()
            while True:
                existing = api(self.base, "/experiments/" + identifier)
                snapshot = existing.get("snapshot") or {}
                round_id = snapshot.get("round", 0)
                self.status(currentExperimentId=identifier, currentRound=round_id, rounds=c["rounds"],
                    lastSuccessfulCheckpoint=snapshot.get("checkpointPath"), workerStatus="READY",
                    retryAttempts=run["retries"], transportRetryStatus=api(self.base, "/research/worker-status"), nextResumeAction="resume last committed snapshot")
                if round_id != last_round:
                    last_progress = time.monotonic()
                    stage_runs = [r for r in self.state["runs"].values() if r["stage"] == run["stage"]]
                    run_number = next(i for i, r in enumerate(stage_runs, 1) if r["key"] == run["key"])
                    print(f'[{run["stage"]}][{run["policy"]}][{run["scenario"]}][seed={run["seed"]}] '
                          f'round={round_id}/{c["rounds"]} | run={run_number}/{len(stage_runs)} | retries={run["retries"]} | checkpoint={round_id}', flush=True)
                    last_round = round_id
                if existing["status"] != "RUNNING":
                    break
                if time.monotonic()-last_progress > self.config["recoverySeconds"]:
                    run["status"] = "BLOCKED"
                    raise RuntimeError(f"Experiment progress recovery budget exhausted at committed round {round_id}; inspect worker/SQLite/disk errors")
                time.sleep(2)
            if existing["status"] == "COMPLETED":
                self.verify_completed(run, existing)
                run["status"] = "COMPLETED"
                self.status(lastError=None)
                return
            error = existing.get("error") or "Unknown experiment failure"
            run["lastError"] = error
            if not transient(error):
                run["status"] = "BLOCKED"
                raise RuntimeError(error)
            run["retries"] += 1
            run["status"] = "RETRYABLE_FAILURE"
            self.status(lastError=error)
            if run["retries"] > self.config["retryBudget"]:
                run["status"] = "FAILED"
                raise RuntimeError("Experiment recovery budget exhausted: " + identifier)
            self.ready()

    def verify_completed(self, run, existing):
        """Pin completed checkpoint bytes after worker validation; reuse checks disk identity."""
        c, snapshot = run["config"], existing["snapshot"]
        checkpoint = (ROOT / snapshot["checkpointPath"]).resolve()
        if not checkpoint.is_relative_to(ROOT) or not checkpoint.is_file():
            raise RuntimeError("Completed checkpoint is missing or escapes workspace")
        receipt = checkpoint.with_suffix(".response.json")
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        response = saved["response"]
        if saved.get("responseHash") != digest(response):
            raise RuntimeError("Completed checkpoint response receipt integrity mismatch")
        result = api(self.base, "/experiments/" + c["experimentId"] + "/result")
        if response.get("modelStateHash") != result["modelStateHash"]:
            raise RuntimeError("Completed checkpoint/committed metric tensor identity mismatch")
        identity_path = self.folder / "completed-artifact-identities" / (c["experimentId"] + ".json")
        if not identity_path.exists():
            # Uses proxy only, solely to verify the final tensor, never to select a checkpoint.
            verified = api(self.worker, "/models/evaluate", dict(manifestPath=c["manifestPath"],
                checkpointPath=snapshot["checkpointPath"], split="proxy"))
            if verified.get("modelStateHash") != result["modelStateHash"]:
                raise RuntimeError("Completed checkpoint failed worker tensor verification")
        def file_hash(path):
            h = hashlib.sha256()
            with path.open("rb") as stream:
                while block := stream.read(65536):
                    h.update(block)
            return h.hexdigest()
        immutable(identity_path, dict(configHash=digest(c), checkpointSHA256=file_hash(checkpoint),
            receiptSHA256=file_hash(receipt), modelStateHash=result["modelStateHash"], finalRound=c["rounds"]))
        immutable(self.folder / "initial-model-identities" / f'seed-{c["seed"]}.json',
            dict(seed=c["seed"], architecture=c["architecture"], initialModelStateHash=snapshot["initialModelStateHash"]))

    def audit(self):
        self.stage = "E0-AUDIT"
        audit_runs = [self.experiment("AUDIT" + str(i), "C4", "U0", 42, rounds=2) for i in range(2)]
        for run in audit_runs:
            self.run(run)
        import sqlite3
        with sqlite3.connect(f'file:{(self.folder / "experiments.db").as_posix()}?mode=ro', uri=True) as db:
            outputs = []
            for run in audit_runs:
                rows = [json.loads(row[0]) for row in db.execute("SELECT metrics FROM rounds WHERE experiment_id=? ORDER BY round_id", (run["config"]["experimentId"],))]
                outputs.append([(r["selectedIds"], r["acceptedIds"], r["modelStateHash"], r["scenarioTraceHash"]) for r in rows])
        if outputs[0] != outputs[1] or len(outputs[0]) != 2:
            raise RuntimeError("Executing-build reproducibility audit failed")
        immutable(self.folder / "e0-reproducibility-audit.json", dict(status="PASS", runtime=self.runtime,
            protocolHash=digest(self.config), repetitions=2, rounds=2, deterministicEvidence=outputs[0],
            limitation="Measured execution and selector wall times are excluded from equality"))

    def report(self):
        from fuzzy_uncertainty_reports import generate
        return generate(self)

    def execute(self):
        self.status(workflowStatus="RUNNING", lastError=None)
        if self.mode == "report-only":
            self.stage = "REPORT"
            self.report()
            self.status(workflowStatus="REPORT_ONLY_COMPLETED", nextResumeAction="none")
            return
        self.ready()
        if shutil.disk_usage(self.folder).free < self.config["minimumFreeDiskGB"] * 1024**3:
            raise RuntimeError("Insufficient free disk for configured batch")
        self.audit()
        self.stage = "E0"
        self.report()
        self.stage = "E1"
        self.report()  # Immutable saved pre-round inputs; no model or history mutations.
        self.stage = "E2"
        pilots = [self.experiment("E2", p, u, s) for u in self.config["scenarios"]
                  for s in self.config["trainingSeeds"] for p in ("C1", "C2", "C3", "C4")]
        self.status(expectedE2Runs=len(pilots))
        print(f'E2 pilot: {len(pilots)} runs; E4 additional: {len(self.config["scenarios"])*len(self.config["trainingSeeds"])}; audit: 2 x 2 rounds.', flush=True)
        for run in pilots:
            self.run(run)
        self.state["stages"]["E2"] = "COMPLETED"
        self.report()
        self.stage = "E4"
        calibrated = [self.experiment("E4", "C5", u, s) for u in self.config["scenarios"] for s in self.config["trainingSeeds"]]
        for run in calibrated:
            self.run(run)
        self.state["stages"]["E4"] = "COMPLETED"
        diagnostics = self.report()
        # Predeclared validation-only promotion; no test metrics are consumed here.
        promoted = diagnostics["calibrationEligible"]
        lock = dict(protocolHash=digest(self.config), runtime=self.runtime, policies=["C1", "C4"] + (["C5"] if promoted else []),
            validationDecision=diagnostics, rule="C5 mean paired final proxy accuracy >= C4 and >=50% C5 observations have >=5 past residuals",
            calibration={"quantile": .8, "window": 32, "minimum": 5, "prior": .1, "maximum": .45},
            confirmation={"alphas": self.config["confirmationAlphas"], "partitions": self.config["confirmationPartitions"],
                          "seeds": self.config["confirmationSeeds"], "scenario": "U0", "checkpoint": "final round only"})
        immutable(self.folder / "policy-lock.json", lock)
        self.lock = lock
        self.state["stages"]["POLICY_LOCK"] = "COMPLETED"
        if self.mode == "full":
            self.stage = "E3"
            if self.config["validationPartitionSeed"] in self.config["confirmationPartitions"]:
                raise RuntimeError("Held-out partition overlaps validation partition")
            total = len(lock["policies"])*len(self.config["confirmationAlphas"])*len(self.config["confirmationPartitions"])*len(self.config["confirmationSeeds"])
            remaining_runs = total - sum(r["stage"] == "E3" and r["status"] == "COMPLETED" for r in self.state["runs"].values())
            admission_budget = int(os.environ.get("MINIFLS_FUZZY_RUN_BUDGET", self.config["runBudget"]))
            if admission_budget:
                remaining_runs = min(remaining_runs, max(0, admission_budget-self.admitted))
            round_budget = int(os.environ.get("MINIFLS_FUZZY_ROUND_BUDGET", self.config["roundBudget"]))
            if round_budget:
                remaining_runs = min(remaining_runs, max(0, round_budget-self.admitted_rounds)//self.config["rounds"])
            # Conservative storage estimate, including checkpoint/receipt and evidence overhead.
            estimated_bytes = remaining_runs*self.config["rounds"]*(self.config["selectedPerRound"]+1)*350000 + len(self.config["confirmationAlphas"])*len(self.config["confirmationPartitions"])*160*1024**2
            required_bytes = max(self.config["minimumFreeDiskGB"]*1024**3, estimated_bytes)
            if shutil.disk_usage(self.folder).free < required_bytes:
                raise RuntimeError(f"Insufficient disk for budgeted confirmation: require about {required_bytes/1024**3:.1f} GiB free; lower admission budget or add capacity")
            print(f'E3 locked confirmation matrix: {total} runs ({len(lock["policies"])} policies). Sequential and resumable.', flush=True)
            immutable(self.folder / "confirmation-protocol.json", dict(policyLockHash=digest(lock), expectedRuns=total, protocol=self.config))
            confirmations = [self.experiment("E3", p, "U0", s, a, partition) for a in self.config["confirmationAlphas"]
                             for partition in self.config["confirmationPartitions"] for s in self.config["confirmationSeeds"] for p in lock["policies"]]
            for run in confirmations:
                self.run(run)
            self.state["stages"]["E3"] = "COMPLETED"
        self.stage = "REPORT"
        self.report()
        self.status(workflowStatus="COMPLETED", nextResumeAction="full confirmation" if self.mode == "pilot" else "none")
        atomic(self.folder / "completion.json", dict(mode=self.mode, status="COMPLETED", time=time.time()))


def main():
    workflow = Workflow()
    try:
        from research_watchdog import run_lock
        with run_lock(workflow.folder / "workflow.lock"):
            workflow.execute()
        return 0
    except BudgetReached:
        workflow.report()
        workflow.status(workflowStatus="BUDGET_REACHED", nextResumeAction="rerun same commands to continue")
        return 0
    except Exception as error:
        traceback.print_exc()
        retryable = transient(str(error))
        workflow.status(workflowStatus="RETRYABLE_FAILURE" if retryable else "BLOCKED", lastError=str(error),
                        nextResumeAction="restart same immutable batch" if retryable else "inspect integrity error; do not reset evidence")
        saved_mode = workflow.mode
        try:
            workflow.mode = "report-only"  # Never require a live worker to emit failure reports.
            workflow.report()
        except Exception:
            traceback.print_exc()
        finally:
            workflow.mode = saved_mode
        return 75 if retryable else 20


if __name__ == "__main__":
    sys.exit(main())
