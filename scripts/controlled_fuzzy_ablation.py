"""Controlled width-only study; reuses Java admission, snapshots and frozen recovery.

No training is performed by preflight/report-only. Confirmation needs a completed
pilot lock, explicit operational acceptance and a positive admission budget.
"""
import copy
import itertools
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import sys
import threading
import time
import traceback

from fuzzy_uncertainty_workflow import ROOT, Workflow, BudgetReached, api, atomic, digest, immutable, transient
from resume_frozen_e3 import FrozenE3Controller, prevent_idle_sleep, verify_frozen_files
from research_watchdog import run_lock

POLICIES = {"A0": ("crisp_topsis", "crisp"), "A1": ("fuzzy_topsis", "crisp"),
            "A2": ("fuzzy_topsis", "fixed"), "A3": ("fuzzy_topsis", "history_based"),
            "A4": ("fuzzy_topsis", "error_calibrated")}
COMPARISONS = [("A2", "A1"), ("A3", "A1"), ("A4", "A1"), ("A3", "A2"), ("A4", "A3"), ("A1", "A0")]


def validate_protocol(c):
    if (c["studyStage"],c["protocolVersion"]) not in (("pilot","controlled-fuzzy-width-v1"),
            ("confirmation","controlled-fuzzy-width-v1"),("full","controlled-fuzzy-width-full-v1")):
        raise ValueError("Unknown controlled protocol/stage")
    if c["policies"] != list(POLICIES) or c["reliabilityTarget"] != "accepted-given-selected-executed-v1":
        raise ValueError("Policy set or reliability target changed")
    for key in ("runBudget", "roundBudget", "retryBudget"):
        if not isinstance(c[key], int) or c[key] < 0:
            raise ValueError("Invalid nonnegative admission/retry budget")
    for key in ("rounds", "totalClients", "selectedPerRound", "replayStates"):
        if not isinstance(c[key], int) or c[key] < 1:
            raise ValueError("Invalid positive study size")
    for key in ("alphas", "partitionSeeds", "trainingSeeds"):
        if not c[key] or len(c[key]) != len(set(c[key])):
            raise ValueError("Empty/duplicate matrix axis: " + key)
    if set(c["partitionSeeds"]) & set(c["otherStagePartitions"]):
        raise ValueError("Pilot and confirmation partitions overlap")
    if c["selectedPerRound"] > c["totalClients"] or c["scenario"] not in ("U0", "U1", "U2", "U3"):
        raise ValueError("Invalid K/scenario")
    expected = dict(uncertaintyFallback=.1, uncertaintyMax=.45, calibrationMinHistory=5,
                    calibrationWindow=32, calibrationQuantile=.8)
    if c["widthSettings"] != expected or c["weights"] != dict(estimatedTime=.4, reliability=.35, learningUtility=.25):
        raise ValueError("Established weights/calibration settings must remain locked in v1")


def scientific_controls(c):
    return {key:c[key] for key in ('protocolVersion','reliabilityTarget','policies','dataset','splitSeed',
        'rounds','totalClients','selectedPerRound','scenario','weights','widthSettings','torchThreads',
        'timingUncertainty','reliabilityUncertainty')}


def partition_inventory(c, output):
    """Inspect recorded assignments, not arbitrary seed substrings in prose."""
    evidence = []
    proposed = set(c["partitionSeeds"])
    for directory in ("artifacts", "data", "results", "configurations"):
        base = ROOT / directory
        if not base.exists():
            continue
        for p in base.rglob("*.json"):
            if p.name not in ("manifest.json", "protocol.json", "confirmation-protocol.json") and directory != "configurations":
                continue
            if p.resolve().is_relative_to(output.resolve()) or p.name.startswith("controlled-fuzzy-ablation-"):
                continue
            try:
                value = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            found = set()
            def visit(x):
                if isinstance(x, dict):
                    for k, v in x.items():
                        # Reservations are future designs, not executed/tuning assignments.
                        if k == 'confirmationDesign':
                            continue
                        if k in ("partitionSeed", "validationPartitionSeed") and isinstance(v, int):
                            found.add(v)
                        if k in ("partitionSeeds", "confirmationPartitions") and isinstance(v, list):
                            found.update(i for i in v if isinstance(i, int))
                        visit(v)
                elif isinstance(x, list):
                    for v in x:
                        visit(v)
            visit(value)
            if found:
                evidence.append(dict(path=p.relative_to(ROOT).as_posix(), seeds=sorted(found), sha256=digest(value)))
    used = {s for row in evidence for s in row["seeds"]}
    return dict(proposed=sorted(proposed), previouslyRecorded=sorted(used), conflicts=sorted(proposed & used), evidence=evidence,
                limitation="Repository-visible assignments only; fixed underlying test examples have been inspected previously")


class ControlledStudy(FrozenE3Controller):
    def __init__(self):
        requested = os.environ.get("MINIFLS_FUZZY_MODE", "pilot")
        if requested == "preflight":
            os.environ["MINIFLS_FUZZY_MODE"] = "pilot"
        try:
            Workflow.__init__(self)
        finally:
            os.environ["MINIFLS_FUZZY_MODE"] = requested
        self.mode = requested
        self.partition_cache = {}
        validate_protocol(self.config)
        expected_mode = "pilot" if self.config["studyStage"] == "pilot" else "full"
        if self.mode not in (expected_mode, "preflight", "report-only"):
            raise ValueError("Mode/stage mismatch; use separate pilot and confirmation roots")

    def partition(self, alpha, partition):
        key = (alpha, partition)
        if key not in self.partition_cache:
            print(f"[ABLATION] Verify partition alpha={alpha} seed={partition}", flush=True)
            self.partition_cache[key] = Workflow.partition(self, alpha, partition)
        return self.partition_cache[key]

    def run(self, run):
        try:
            row = api(self.base, "/experiments/"+run["config"]["experimentId"])
        except RuntimeError as error:
            if not str(error).startswith("HTTP 404:"):
                raise
            row = None
        if row and (row["status"] == "INTERRUPTED" or
                    (row["status"] == "FAILED" and transient(row.get("error") or ""))):
            self.wait_for_idle_worker()
            self.verify_resume_checkpoint(run, row)
        return super().run(run)

    def experiment(self, stage, policy, scenario, seed, alpha=None, partition=None, rounds=None):
        c = self.config
        alpha = c["alphas"][0] if alpha is None else alpha
        partition = c["partitionSeeds"][0] if partition is None else partition
        rounds = c["rounds"] if rounds is None else rounds
        key = f"{stage}-{policy}-{scenario}-s{seed}-a{alpha}-p{partition}"
        selection, width = POLICIES[policy]
        settings = dict(c["widthSettings"], weights=c["weights"], uncertaintyMode=width,
                        observationNoise=dict(scenario=scenario, timing=c["timingUncertainty"], reliability=c["reliabilityUncertainty"]))
        config = dict(experimentId="ca-"+digest(str(self.folder))[:8]+"-"+digest(key)[:20],
            manifestPath=self.partition(alpha, partition), totalClients=c["totalClients"], selectedPerRound=c["selectedPerRound"],
            rounds=rounds, seed=seed, selection=selection, aggregation="fedavg", localEpochs=1, batchSize=32,
            learningRate=.01, simulationEnabled=True, resourceProfile="heterogeneous", availability=.9, dropout=.05,
            jitter=.1, exploration=0., deadlineSeconds=10., requiredRamMb=600., priorSecondsPerSample=.0005,
            targetAccuracy=.7, architecture="mlp_54_256_128_7", evaluationSplit="proxy",
            finalEvaluationSplit="test" if stage in ("CONFIRMATION","FULL") else "proxy",
            timing=dict(mode="deterministic", secondsPerSample=.0005), fuzzySelection=settings,
            provenance=dict(runtimeIdentity=self.runtime, workflowProtocolHash=digest(c)))
        tracepath = self.folder / "traces" / f"s{seed}-r{rounds}.json"
        immutable(tracepath, api(self.base, "/research/trace", config))
        config["scenarioTracePath"] = tracepath.relative_to(ROOT).as_posix()
        run = dict(key=key, stage=stage, policy=policy, scenario=scenario, seed=seed, alpha=alpha,
                   partition=partition, config=config, status="PENDING", retries=0)
        saved = self.state["runs"].get(key)
        if saved:
            if saved["config"] != config:
                raise RuntimeError("Controlled run config/provenance mismatch: "+key)
            return saved
        self.state["runs"][key] = run
        return run

    def preflight(self):
        c = self.config
        count = len(POLICIES)*len(c["alphas"])*len(c["partitionSeeds"])*len(c["trainingSeeds"])
        budget = int(os.environ.get("MINIFLS_FUZZY_RUN_BUDGET", c["runBudget"]))
        round_budget = int(os.environ.get("MINIFLS_FUZZY_ROUND_BUDGET", c["roundBudget"]))
        if budget < 0 or round_budget < 0:
            raise ValueError("Budgets cannot be negative")
        admitted = min(count, budget or count, (round_budget//c["rounds"]) if round_budget else count)
        # MLP47879 measured over 800 artifacts: checkpoint+receipt <=197519 B.
        # Existing 11554-round SQLite cohort: maximum JSON row159164 B.
        # Retain >50% checkpoint and >38% row headroom plus explicit reserves.
        per_round = (c["selectedPerRound"]+1)*300000 + 220000
        dataset_bytes = len(c["alphas"])*len(c["partitionSeeds"])*160*1024**2
        overhead_bytes = 256*1024**2 + 4*per_round  # JAR/reports/logs/WAL and audit rounds.
        full_bytes = count*c["rounds"]*per_round+dataset_bytes+overhead_bytes+c["minimumFreeDiskGB"]*1024**3
        admission_bytes = admitted*c["rounds"]*per_round+dataset_bytes+overhead_bytes+c["minimumFreeDiskGB"]*1024**3
        # Bounded physical timing sample, explicitly not a runtime guarantee.
        durations = []
        for relative in c["evidenceDatabases"]:
            path = ROOT / relative
            if path.is_file():
                with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as db:
                    for row in db.execute("SELECT metrics FROM rounds ORDER BY rowid DESC LIMIT 100"):
                        value = json.loads(row[0]).get("wallClockSeconds")
                        if value is not None:
                            durations.append(value)
        median = statistics.median(durations) if durations else None
        report = dict(protocolVersion=c["protocolVersion"], studyStage=c["studyStage"], runs=count,
            storageEstimateVersion='measured-mlp47879-v2',
            storageBounds=dict(checkpointAndReceiptBytes=300000,roundSQLiteEvidenceBytes=220000,
                datasetAssignmentBytes=160*1024**2,otherAndAuditBytes=overhead_bytes,
                protectedFreeReserveGiB=c['minimumFreeDiskGB']),
            rounds=count*c["rounds"], auditRuns=2, auditRounds=4, maximumAdmittedResearchRuns=admitted,
            freeDiskGiB=shutil.disk_usage(self.folder).free/1024**3, fullEstimatedDiskGiB=full_bytes/1024**3,
            admissionEstimatedDiskGiB=admission_bytes/1024**3, memoryPlan="Sequential; Java heap512MiB; one Uvicorn; torchThreads1; disk cursors",
            memoryPlanningMiB=dict(coordinatorRSSRange=[300,900],workerRSSRange=[400,2000],
                limitation="Planning ranges, not measured bounds; mmap page residency, report plots, dataset preparation and OS/IDE add memory. Close unnecessary IDE/browser processes on 8GB machines."),
            sampledRoundSecondsMedian=median, physicalTimingSampleCount=len(durations),
            approximateTrainingHours=None if median is None else median*count*c["rounds"]/3600,
            runtimeLimitation="Recent 100 physical round times; load/standby/partition/IO can change elapsed time substantially",
            partitionReservation=json.loads((self.folder / "partition-reservation.json").read_text()),
            confirmationAutomaticallyAccepted=False)
        atomic(self.folder / "preflight.json", report)
        print(f"[PREFLIGHT] {c['studyStage']}: {count} research runs x {c['rounds']} = {count*c['rounds']} rounds; audit 2 x 2 extra. Full disk estimate={report['fullEstimatedDiskGiB']:.1f} GiB; free={report['freeDiskGiB']:.1f} GiB; admission={admitted} runs.", flush=True)
        return report

    def audit(self):
        self.stage = "AUDIT"
        runs = [self.experiment("AUDIT"+str(i), "A3", self.config["scenario"], 42, rounds=2) for i in range(2)]
        for run in runs:
            self.run(run)
        evidence = []
        with sqlite3.connect((self.folder / "experiments.db").as_uri()+"?mode=ro", uri=True) as db:
            for run in runs:
                rows = [json.loads(r[0]) for r in db.execute("SELECT metrics FROM rounds WHERE experiment_id=? ORDER BY round_id", (run["config"]["experimentId"],))]
                evidence.append([(r["selectedIds"], r["acceptedIds"], r["modelStateHash"], r["scenarioTraceHash"]) for r in rows])
        if len(evidence[0]) != 2 or evidence[0] != evidence[1]:
            raise RuntimeError("Executing-build deterministic audit failed")
        immutable(self.folder / "reproducibility-audit.json", dict(status="PASS", runtime=self.runtime,
                  protocolHash=digest(self.config), evidence=evidence[0]))

    def replay(self):
        from controlled_ablation_reports import replay
        replay(self)

    def report(self):
        from controlled_ablation_reports import generate
        previous_stage = self.stage
        self.stage = 'REPORT'
        self.status(nextResumeAction='stream committed evidence and regenerate reports/figures')
        done = threading.Event()
        def heartbeat():
            while not done.wait(15):
                print('[ABLATION-REPORT] Streaming SQLite evidence and writing reports/figures; no training.', flush=True)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        print('[ABLATION-REPORT] Generate committed-evidence reports and ten figures.', flush=True)
        try:
            return generate(self)
        finally:
            done.set(); thread.join(timeout=2)
            self.stage = previous_stage

    def confirmation_gate(self):
        c = self.config
        pointer = ROOT / c["pilotPointer"]
        pilot = Path(json.loads(pointer.read_text())["folder"]).resolve()
        if not pilot.is_relative_to(ROOT):
            raise RuntimeError("Pilot pointer escapes workspace")
        lock = json.loads((pilot / "pilot-validation-lock.json").read_text())
        status = json.loads((pilot / "completion.json").read_text())
        if status.get("status") != "COMPLETED" or lock["protocolVersion"] != c["protocolVersion"]:
            raise RuntimeError("Completed pilot validation lock required")
        if (not lock['integrity']['passed'] or lock['policies'] != list(POLICIES) or
            lock['scientificControls'] != scientific_controls(c) or lock['runtime'] != self.runtime or
            lock['sourceIdentityHash'] != digest(json.loads((self.folder/'source-identity.json').read_text())) or
            lock['confirmationDesign'] != dict(alphas=c['alphas'],partitionSeeds=c['partitionSeeds'],trainingSeeds=c['trainingSeeds'])):
            raise RuntimeError('Confirmation scientific controls/source/runtime differ from validated pilot lock')
        if lock["confirmationPartitions"] != c["partitionSeeds"] or lock["widthSettings"] != c["widthSettings"] or lock["weights"] != c["weights"]:
            raise RuntimeError("Confirmation differs from the pilot-frozen design")
        if os.environ.get("MINIFLS_ABLATION_ACCEPT_CONFIRMATION") != "1":
            raise RuntimeError("Confirmation requires explicit acceptance after reviewing preflight and pilot diagnostics")
        if not int(os.environ.get("MINIFLS_FUZZY_RUN_BUDGET", c["runBudget"])) and not int(os.environ.get("MINIFLS_FUZZY_ROUND_BUDGET", c["roundBudget"])):
            raise RuntimeError("Confirmation requires an explicit positive run or round admission budget")
        immutable(self.folder / "confirmation-lock.json", dict(pilotLockHash=digest(lock), protocolHash=digest(c), policies=list(POLICIES)))

    def full_policy_lock(self):
        c=self.config
        if c['confirmationDesign'] != dict(alphas=c['alphas'],partitionSeeds=c['partitionSeeds'],trainingSeeds=c['trainingSeeds']):
            raise RuntimeError('Full study axes differ from the predefined full design')
        immutable(self.folder/'full-policy-lock.json',dict(protocolVersion=c['protocolVersion'],protocolHash=digest(c),
            scientificControls=scientific_controls(c),runtime=self.runtime,policies=list(POLICIES),
            design=c['confirmationDesign'],pilotExecutedForThisStudy=False,
            executionBasis='User requested all predefined runs without the separate Covertype pilot; all five policies and established parameters fixed before execution',
            interpretation='Full predeclared ablation; not a pilot-validated confirmation; prior fixed test examples have been inspected'))

    def execute(self):
        verify_frozen_files(self.folder)
        preflight = self.preflight()
        if self.mode == "preflight":
            self.status(workflowStatus="PREFLIGHT_COMPLETED", nextResumeAction="review preflight; start worker then run same stage")
            return
        if self.mode == "report-only":
            self.stage = "REPORT"
            self.report()
            self.status(workflowStatus="REPORT_ONLY_COMPLETED", nextResumeAction="none")
            return
        self.status(workflowStatus="RUNNING", lastError=None)
        self.ready()
        if self.config["studyStage"] == "confirmation":
            self.confirmation_gate()
        elif self.config['studyStage']=='full':
            self.full_policy_lock()
        if preflight["freeDiskGiB"] < preflight["admissionEstimatedDiskGiB"]:
            raise RuntimeError("Insufficient disk for admission and protected reserve; reduce budget or add capacity")
        self.audit()
        self.stage = "OFFLINE"
        self.replay()
        self.stage = {'pilot':'PILOT','confirmation':'CONFIRMATION','full':'FULL'}[self.config['studyStage']]
        runs = [self.experiment(self.stage, p, self.config["scenario"], s, a, part)
                for a, part, s, p in itertools.product(self.config["alphas"], self.config["partitionSeeds"], self.config["trainingSeeds"], POLICIES)]
        self.status()
        for run in runs:
            self.run(run)
        diagnostics = self.report()
        if not diagnostics["integrity"]["passed"]:
            raise RuntimeError("Paired/final-checkpoint integrity verification failed; inspect report")
        if self.config["studyStage"] == "pilot":
            immutable(self.folder / "pilot-validation-lock.json", dict(protocolVersion=self.config["protocolVersion"],
                protocolHash=digest(self.config), runtime=self.runtime, policies=list(POLICIES),
                weights=self.config["weights"], widthSettings=self.config["widthSettings"],
                confirmationPartitions=self.config["otherStagePartitions"],
                scientificControls=scientific_controls(self.config),
                sourceIdentityHash=digest(json.loads((self.folder/'source-identity.json').read_text())),
                confirmationDesign=self.config['confirmationDesign'],
                rule="All five retained regardless of pilot proxy outcomes; no test-based tuning", integrity=diagnostics["integrity"]))
        self.status(workflowStatus="COMPLETED", nextResumeAction="review pilot/preflight before confirmation" if self.stage == "PILOT" else "none")
        # Refresh textual completion status; no evaluation or training.
        self.report()
        # Completion is durable only after every final report/plot succeeds.
        atomic(self.folder / "completion.json", dict(status="COMPLETED", mode=self.mode, time=time.time()))


def main():
    study = ControlledStudy()
    try:
        with run_lock(study.folder / "workflow.lock"), prevent_idle_sleep():
            study.execute()
        return 0
    except BudgetReached:
        study.status(workflowStatus="BUDGET_REACHED", nextResumeAction="rerun same stage/batch; committed work is reused")
        study.report()
        return 0
    except Exception as error:
        traceback.print_exc()
        retryable = transient(str(error))
        study.status(workflowStatus="RETRYABLE_FAILURE" if retryable else "BLOCKED", lastError=str(error), nextResumeAction="inspect error; keep batch/checkpoints")
        try:
            study.report()
        except Exception:
            traceback.print_exc()
        return 75 if retryable else 20


if __name__ == "__main__":
    sys.exit(main())
