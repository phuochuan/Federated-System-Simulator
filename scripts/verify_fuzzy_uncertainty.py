"""Isolated real Java/PyTorch workflow smoke; never runs Covertype research matrices."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

from verify_fuzzy import free_port

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "artifacts/fuzzy-uncertainty-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    config = json.loads((ROOT / "configurations/fuzzy-uncertainty.json").read_text())
    config.update(dataset="synthetic", rounds=3, trainingSeeds=[42], scenarios=["U0", "U2"], evidenceDatabases=[],
                  minimumFreeDiskGB=.05, restartDelaySeconds=1, readinessSeconds=90, confirmationAlphas=[.5],
                  confirmationPartitions=[3001], confirmationSeeds=[42])
    path = folder / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    java_port, worker_port = free_port(), free_port()
    env = dict(os.environ, MINIFLS_FUZZY_CONFIG=str(path), MINIFLS_FUZZY_OUTPUT=str(folder / "research"),
               MINIFLS_SERVER_PORT=str(java_port), MINIFLS_WORKER_URL=f"http://127.0.0.1:{worker_port}",
               PYTHONUTF8="1", MINIFLS_LOG_LEVEL="WARN")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

    def phase(name, mode, budget=0, inject=False):
        phase_env = dict(env, MINIFLS_FUZZY_MODE=mode, MINIFLS_FUZZY_RUN_BUDGET=str(budget))
        processes = []
        logs = []
        try:
            for role in ("worker", "java"):
                log = (folder / f"{name}-{role}.log").open("w", encoding="utf-8")
                logs.append(log)
                processes.append(subprocess.Popen([sys.executable, "-u", "scripts/research_watchdog.py", role],
                    cwd=ROOT, env=phase_env, stdout=log, stderr=log, **flags))
            deadline = time.monotonic()+600
            killed_worker = killed_java = False
            while processes[1].poll() is None:
                if time.monotonic()>deadline:
                    raise TimeoutError(f"{name}: see {folder}")
                if inject:
                    import psutil
                    from verify_fuzzy import get
                    if not killed_worker:
                        try:
                            get(f"http://127.0.0.1:{worker_port}", "/health")
                            children = psutil.Process(processes[0].pid).children(recursive=True)
                            candidates = [p for p in children if "uvicorn" in " ".join(p.cmdline())]
                            if candidates:
                                max(candidates, key=lambda p: p.create_time()).kill()
                                killed_worker = True
                        except (OSError, psutil.NoSuchProcess):
                            pass
                    pointer = folder / "research/active-batch.json"
                    if killed_worker and not killed_java and pointer.exists():
                        current = Path(json.loads(pointer.read_text())["folder"])
                        if (current / "experiments.db").exists():
                            with sqlite3.connect(current / "experiments.db") as db:
                                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                                partial = db.execute("SELECT id FROM experiments WHERE status='RUNNING' AND json_extract(snapshot,'$.round')>=1 AND json_extract(snapshot,'$.round')<json_extract(config,'$.rounds')").fetchall() if "experiments" in tables else []
                            if partial:
                                candidates = [p for p in psutil.Process(processes[1].pid).children(recursive=True) if p.name().lower() in ("java", "java.exe")]
                                if candidates:
                                    candidates[0].kill()
                                    killed_java = True
                time.sleep(.02 if inject else 1)
            assert processes[1].returncode == 0, f"{name} coordinator failed; see {folder}"
            processes[0].wait(timeout=45)
            assert processes[0].returncode == 0, f"{name} worker failed; see {folder}"
            if inject:
                assert killed_worker and killed_java, "Fault injection did not reach both service processes"
        finally:
            import psutil
            for process in processes:
                if process.poll() is None:
                    try:
                        children = psutil.Process(process.pid).children(recursive=True)
                    except psutil.NoSuchProcess:
                        children = []
                    for child in reversed(children):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    process.kill();process.wait()
            for log in logs:
                log.close()

    phase("budget", "pilot", 1)
    batch = Path(json.loads((folder / "research/active-batch.json").read_text())["folder"])
    assert json.loads((batch / "status.json").read_text())["workflowStatus"] == "BUDGET_REACHED"
    phase("pilot", "pilot", inject=True)
    lock = (batch / "policy-lock.json").read_bytes()
    assert json.loads((batch / "status.json").read_text())["workflowStatus"] == "COMPLETED"
    assert json.loads((batch / "e2-robustness-results.json").read_text())["status"] == "COMPLETED"
    phase("full", "full")
    assert (batch / "policy-lock.json").read_bytes() == lock
    assert json.loads((batch / "e3-heldout-results.json").read_text())["status"] == "COMPLETED"
    with sqlite3.connect(batch / "experiments.db") as db:
        count = db.execute("SELECT count(*) FROM rounds").fetchone()[0]
        assert db.execute("SELECT count(*) FROM (SELECT experiment_id,round_id,count(*) n FROM rounds GROUP BY experiment_id,round_id HAVING n>1)").fetchone()[0] == 0
        for status, config_json, snapshot in db.execute("SELECT status,config,snapshot FROM experiments"):
            assert status == "COMPLETED"
            assert json.loads(config_json)["rounds"] == json.loads(snapshot)["round"]
        final = db.execute("SELECT metrics FROM rounds r JOIN experiments e ON r.experiment_id=e.id WHERE json_extract(e.config,'$.finalEvaluationSplit')='test' AND r.round_id=json_extract(e.config,'$.rounds')").fetchall()
        assert final and all(json.loads(r[0])["evaluationSplit"] == "test" for r in final)
        import numpy as np
        traces = {}
        for config_json, metrics in db.execute("SELECT config,metrics FROM rounds r JOIN experiments e ON r.experiment_id=e.id"):
            config_row, metrics = json.loads(config_json), json.loads(metrics)
            paired_key = (config_row["seed"], config_row["rounds"], metrics["roundId"])
            if paired_key in traces:
                assert traces[paired_key] == metrics["scenarioTrace"]
            traces[paired_key] = metrics["scenarioTrace"]
            for profile in metrics["selectorInput"]["eligibleClients"]:
                assert not {"dropoutEvent", "jitterMultiplier", "actualTrainingMs", "completionSeconds"} & profile.keys()
            if config_row["selection"] != "crisp_topsis":
                continue
            matrix = metrics["fuzzyDecisionMatrix"]
            ids = list(matrix["rows"])
            if not ids:
                continue
            x = np.array([[cell["middle"] for cell in matrix["rows"][i]] for i in ids])
            norms = np.linalg.norm(x, axis=0)
            weighted = x/np.where(norms > 1e-9, norms, 1)*np.array([c["weight"] for c in matrix["criteria"]])
            cost = np.array([c["type"] == "COST" for c in matrix["criteria"]])
            plus = np.where(cost, weighted.min(axis=0), weighted.max(axis=0))
            minus = np.where(cost, weighted.max(axis=0), weighted.min(axis=0))
            dp, dn = np.linalg.norm(weighted-plus, axis=1), np.linalg.norm(weighted-minus, axis=1)
            reference = np.divide(dn, dp+dn, out=np.full_like(dn, .5), where=dp+dn>1e-9)
            np.testing.assert_allclose(reference, [metrics["finalSelectionScores"][i] for i in ids], rtol=1e-12, atol=1e-12)
    phase("reuse", "full")
    with sqlite3.connect(batch / "experiments.db") as db:
        assert count == db.execute("SELECT count(*) FROM rounds").fetchone()[0]
    phase("reports", "report-only")
    for name in ("e0-observations.csv", "e1-ranking-comparison.csv", "e2-robustness-results.csv", "e4-calibration-diagnostics.csv", "fuzzy-mcdm-research-summary.md"):
        assert (batch / name).stat().st_size > 0
    print(f"Fuzzy uncertainty workflow smoke PASS: {batch}", flush=True)
    (folder / "summary.json").write_text(json.dumps(dict(status="PASS", batch=str(batch), committedRounds=count,
        checks=["budget resume", "automatic worker watchdog restart", "automatic Java crash/round resume", "pilot-to-full immutable policy lock", "completed reuse", "final-only test evaluation", "unique commits", "report-only", "NumPy crisp reference", "paired scenario traces", "no future event fields in selector input"]), indent=2))


if __name__ == "__main__":
    main()
