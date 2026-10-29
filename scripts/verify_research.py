"""Small real HTTP/SQLite/PyTorch smoke for Java E0, reuse, Phase A and Phase B.

Synthetic, 3 rounds only. Uses isolated ports, database, manifests and output.
Matching tolerances are deliberately wide to exercise locking, not research evidence.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from verify_fuzzy import free_port, get
from minifls.data import prepare

ROOT = Path(__file__).resolve().parents[1]


def stop(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        process.terminate()
    process.wait(timeout=20)


def main():
    folder = ROOT / "artifacts/research-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    prepare(folder / "partition", dataset="synthetic", clients=100, seed=42,
            strategy="dirichlet_label_skew", partition_seed=45)
    audit = json.loads((ROOT / "configurations/reproducibility-audit.json").read_text())
    audit.update(smoke=True, nonIidManifestPath=(folder / "partition").relative_to(ROOT).as_posix())
    audit["baseConfig"]["rounds"] = 3
    (folder / "audit.json").write_text(json.dumps(audit), encoding="utf-8")
    matched = json.loads((ROOT / "configurations/fairness-matched-lambda.json").read_text())
    matched.update(smoke=True, requireAudit=False,
                   partitionPattern=(folder / "partitions/p{partitionSeed}").relative_to(ROOT).as_posix())
    matched["baseConfig"]["rounds"] = 3
    matched["validation"]["seeds"] = [42]
    matched["evaluation"]["seeds"] = [42]
    matched["matching"] = {key: 100 if "Staleness" in key else 1 for key in matched["matching"]}
    (folder / "matched.json").write_text(json.dumps(matched), encoding="utf-8")
    worker_port = free_port()
    worker_base = f"http://127.0.0.1:{worker_port}"
    env = {**os.environ, "MINIFLS_WORKSPACE": str(ROOT), "MINIFLS_WORKER_URL": worker_base,
           "MINIFLS_DATABASE": str(folder / "research.db"), "MINIFLS_TORCH_THREADS": "1"}
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = None
    with (folder / "worker.log").open("w", encoding="utf-8") as log:
        try:
            worker = subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(worker_port), "--workers", "1"], cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic() + 90
            while True:
                if worker.poll() is not None:
                    raise RuntimeError("Worker exited")
                try:
                    get(worker_base, "/health")
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Worker startup")
                    time.sleep(.25)

            def launch(mode, output, config, report_name, expected_runs):
                server_port = free_port()
                server = None
                report = output / report_name
                # A fresh completion marker distinguishes rerun/reuse from an old report.
                previous_mtime = report.stat().st_mtime_ns if report.exists() else None
                local_env = {**env, "MINIFLS_METHOD": mode, "MINIFLS_SERVER_PORT": str(server_port),
                             "MINIFLS_RESEARCH_OUTPUT": str(output), "MINIFLS_AUDIT_CONFIG": str(config), "MINIFLS_MATCHED_CONFIG": str(config)}
                with (folder / f"{mode}-{uuid.uuid4().hex[:4]}.log").open("w", encoding="utf-8") as java_log:
                    try:
                        server = subprocess.Popen(["java", "-Xmx384m", "-jar", str(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")], cwd=ROOT, env=local_env, stdout=java_log, stderr=java_log, **flags)
                        deadline = time.monotonic() + 240
                        while time.monotonic() < deadline:
                            if server.poll() is not None:
                                raise RuntimeError(f"Java exited: {mode}; inspect {folder}")
                            if report.exists() and report.stat().st_mtime_ns != previous_mtime:
                                data = json.loads(report.read_text(encoding="utf-8"))
                                assert data["complete"], data.get("error")
                                if mode.startswith("fairness_matched") and not (report.parent / "adaptive-behavior.svg").exists():
                                    time.sleep(.1)
                                    continue
                                # Phase A writes the policy lock immediately after the report.
                                if mode == "fairness_matched_validation" and not (output / "policy-lock.json").exists():
                                    time.sleep(.1)
                                    continue
                                if mode == "fairness_matched_evaluation" and not (output / "evaluation/heldout-fairness-check.json").exists():
                                    time.sleep(.1)
                                    continue
                                assert len(data.get("runs", data.get("results", []))) == expected_runs
                                return data
                            time.sleep(.25)
                        raise TimeoutError(mode)
                    finally:
                        stop(server)

            a = launch("reproducibility_audit", folder / "e0", folder / "audit.json", "reproducibility-audit.json", 12)
            assert a["deterministicReplayPassed"], a["conclusion"]
            assert all(r["savedStateAndTimingReplayPassed"] for r in a["runs"])
            assert len(a["repeatSummaryByGroup"]) == 4
            assert all(s["metrics"]["accuracy"]["n"] == 3 and s["metrics"]["accuracy"]["sampleSd"] is not None for s in a["repeatSummaryByGroup"])
            # Real SQLite reuse: same completed identities, no duplicate rounds or exports.
            import sqlite3
            def counts():
                with sqlite3.connect(folder / "research.db") as db:
                    return db.execute("SELECT count(*) FROM experiments").fetchone(), db.execute("SELECT count(*) FROM rounds").fetchone()
            before = counts()
            launch("reproducibility_audit", folder / "e0", folder / "audit.json", "reproducibility-audit.json", 12)
            assert counts() == before
            v = launch("fairness_matched_validation", folder / "e1", folder / "matched.json", "validation/fairness-matched-results.json", 14)
            assert v["fairnessMatching"]["status"] == "MATCHED"
            b = launch("fairness_matched_evaluation", folder / "e1", folder / "matched.json", "evaluation/fairness-matched-results.json", 6)
            assert all(r["finalEvaluationSplit"] == "test" and r["stabilityAndTargetSplit"] == "proxy" for r in b["results"])
            for run in b["results"]:
                rounds = json.loads((folder / "e1/evaluation/runs" / run["experimentId"] / "rounds.json").read_text())
                assert [r["evaluationSplit"] for r in rounds] == ["proxy", "proxy", "test"]
                assert all(r["trajectoryEvaluationSplit"] == "proxy" for r in rounds)
            print(f"Java E0/E1 smoke PASS: {folder}", flush=True)
        finally:
            stop(worker)


if __name__ == "__main__":
    main()
