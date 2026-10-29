"""Small real Java/HTTP/SQLite smoke: E0 -> NO_MATCH pilot -> Pareto/resume/reuse.

Synthetic, three rounds, one pilot partition/seed, two held-out partitions/one seed.
No Covertype training and no external worker/production database is touched.
"""
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

from minifls.data import prepare
from verify_fuzzy import free_port, get, post
from verify_research import stop

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "artifacts/pareto-smoke" / uuid.uuid4().hex[:10]
    folder.mkdir(parents=True)
    prepare(folder / "partition", dataset="synthetic", clients=100, strategy="dirichlet_label_skew")
    audit = json.loads((ROOT / "configurations/reproducibility-audit.json").read_text())
    audit.update(smoke=True, nonIidManifestPath=(folder / "partition").relative_to(ROOT).as_posix())
    audit["baseConfig"]["rounds"] = 3
    pilot = json.loads((ROOT / "configurations/fairness-matched-lambda.json").read_text())
    pilot.update(smoke=True, requireAudit=False, partitionPattern=(folder / "partitions/p{partitionSeed}").relative_to(ROOT).as_posix())
    pilot["baseConfig"]["rounds"] = 3
    pilot["validation"] = {"partitionSeeds": [1001], "seeds": [42]}
    pilot["evaluation"] = {"partitionSeeds": [2001, 2002], "seeds": [42]}
    pilot["matching"] = {key: 0 for key in pilot["matching"]}  # Strict smoke pilot must return NO_MATCH.
    for name, data in (("audit.json", audit), ("pilot.json", pilot)):
        (folder / name).write_text(json.dumps(data), encoding="utf-8")
    backend_port = free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    inject_failure = False

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def forward(self):
            nonlocal inject_failure
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))) if self.command == "POST" else None
            if self.path == "/train" and inject_failure and json.loads(body)["roundId"] == 2:
                inject_failure = False
                status, result = 400, b'{"detail":"Synthetic resume smoke interruption after committed round1"}'
            else:
                request = Request(backend+self.path, data=body, method=self.command, headers={"Content-Type": "application/json"})
                try:
                    with urlopen(request, timeout=60) as response:
                        status, result = response.status, response.read()
                except HTTPError as error:
                    status, result = error.code, error.read()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        do_GET = forward
        do_POST = forward

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    env = {**os.environ, "MINIFLS_WORKSPACE": str(ROOT), "MINIFLS_WORKER_URL": f"http://127.0.0.1:{proxy.server_port}",
           "MINIFLS_DATABASE": str(folder / "test.db"), "MINIFLS_TORCH_THREADS": "1", "MINIFLS_LAUNCH_ENABLED": "true"}
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    worker = None
    with (folder / "worker.log").open("w", encoding="utf-8") as log:
        try:
            worker = subprocess.Popen([sys.executable, "-m", "uvicorn", "minifls.api:app", "--host", "127.0.0.1", "--port", str(backend_port), "--workers", "1"], cwd=ROOT, env=env, stdout=log, stderr=log, **flags)
            deadline = time.monotonic()+90
            while True:
                try:
                    get(backend, "/health")
                    break
                except OSError:
                    if worker.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError("Worker startup failed")
                    time.sleep(.25)

            def launch(mode, config, output, target, expect_failure=False):
                process = None
                marker = output / target
                before = marker.stat().st_mtime_ns if marker.exists() else None
                local = {**env, "MINIFLS_METHOD": mode, "MINIFLS_SERVER_PORT": str(free_port()),
                         "MINIFLS_AUDIT_CONFIG": str(config), "MINIFLS_MATCHED_CONFIG": str(config), "MINIFLS_PARETO_CONFIG": str(config),
                         "MINIFLS_AUDIT_OUTPUT": str(output), "MINIFLS_MATCHED_OUTPUT": str(output), "MINIFLS_PARETO_OUTPUT": str(output)}
                with (folder / f"{mode}-{uuid.uuid4().hex[:4]}.log").open("w", encoding="utf-8") as java_log:
                    try:
                        process = subprocess.Popen(["java", "-Xmx512m", "-jar", str(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")], cwd=ROOT, env=local, stdout=java_log, stderr=java_log, **flags)
                        deadline = time.monotonic()+300
                        while time.monotonic()<deadline:
                            if expect_failure and process.poll() is not None:
                                assert process.returncode != 0
                                return
                            if not expect_failure and marker.exists() and marker.stat().st_mtime_ns!=before:
                                return json.loads(marker.read_text(encoding="utf-8"))
                            if process.poll() is not None:
                                raise RuntimeError(f"{mode} exited; inspect {folder}")
                            time.sleep(.25)
                        raise TimeoutError(mode)
                    finally:
                        stop(process)

            real_protocol = json.loads((ROOT / "configurations/pareto-tradeoff.json").read_text())
            if (ROOT / real_protocol["phaseA"]["reportPath"]).exists():
                real_gate = launch("pareto_preflight", ROOT / "configurations/pareto-tradeoff.json", folder / "real-protocol-preflight", "pareto-preflight.json")
                assert not real_gate["ready"] and not real_gate["determinismClaimed"]
                with sqlite3.connect(folder / "test.db") as db:
                    assert db.execute("SELECT count(*) FROM experiments").fetchone()[0] == 0
            a = launch("reproducibility_audit", folder / "audit.json", folder / "e0", "reproducibility-audit.json")
            assert a["deterministicReplayPassed"]
            lock = launch("fairness_matched_validation", folder / "pilot.json", folder / "pilot", "policy-lock.json")
            assert lock["status"] == "NO_MATCH"
            pareto = copy.deepcopy(pilot)
            template = json.loads((ROOT / "configurations/pareto-tradeoff.json").read_text())
            pareto.update(analysisType="PARETO_COMPARISON", policies=template["policies"], requireAudit=True, dataset="synthetic", alpha=.5,
                          auditReportPath=(folder / "e0/reproducibility-audit.json").relative_to(ROOT).as_posix(), largeAccuracyDropPp=10)
            report_path, lock_path = folder / "pilot/validation/fairness-matched-results.json", folder / "pilot/policy-lock.json"
            pareto["phaseA"] = dict(reportPath=report_path.relative_to(ROOT).as_posix(), lockPath=lock_path.relative_to(ROOT).as_posix(),
                                    reportSha256=hashlib.sha256(report_path.read_bytes()).hexdigest(), lockSha256=hashlib.sha256(lock_path.read_bytes()).hexdigest())
            (folder / "pareto.json").write_text(json.dumps(pareto), encoding="utf-8")
            blocked = {**pareto, "auditReportPath": (folder / "missing-audit.json").relative_to(ROOT).as_posix()}
            (folder / "blocked.json").write_text(json.dumps(blocked), encoding="utf-8")
            gate = launch("pareto_preflight", folder / "blocked.json", folder / "blocked", "pareto-preflight.json")
            assert not gate["ready"] and not gate["determinismClaimed"]
            inject_failure = True
            launch("heldout_pareto", folder / "pareto.json", folder / "pareto", "pareto-completion.json", expect_failure=True)
            with sqlite3.connect(folder / "test.db") as db:
                failed = db.execute("SELECT id,snapshot FROM experiments WHERE status='FAILED'").fetchall()
            assert len(failed)==1 and json.loads(failed[0][1])["round"]==1
            # Resume through the normal API on the SAME JAR/runtime, without startup experiments.
            server = None
            with (folder / "resume.log").open("w", encoding="utf-8") as resume_log:
                try:
                    port = free_port()
                    server = subprocess.Popen(["java", "-Xmx512m", "-jar", str(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar")], cwd=ROOT,
                                              env={**env, "MINIFLS_LAUNCH_ENABLED": "false", "MINIFLS_SERVER_PORT": str(port)}, stdout=resume_log, stderr=resume_log, **flags)
                    base = f"http://127.0.0.1:{port}"
                    deadline = time.monotonic()+120
                    while True:
                        try:
                            get(base, "/experiments")
                            break
                        except OSError:
                            if time.monotonic()>deadline:
                                raise TimeoutError("API-only startup")
                            time.sleep(.25)
                    post(base, f"/experiments/{failed[0][0]}/resume")
                    while True:
                        state = get(base, f"/experiments/{failed[0][0]}")
                        if state["status"] != "RUNNING":
                            break
                        if time.monotonic()>deadline:
                            raise TimeoutError("Resume")
                        time.sleep(.25)
                    assert state["status"] == "COMPLETED", state.get("error")
                finally:
                    stop(server)
            launch("heldout_pareto", folder / "pareto.json", folder / "pareto", "pareto-completion.json")
            result = json.loads((folder / "pareto/pareto-tradeoff-results.json").read_text())
            assert result["complete"] and len(result["results"])==8 and len(result["pairedDifferences"])==6
            assert result["analysisType"] == "PARETO_COMPARISON" and result["phaseAStatus"] == "NO_MATCH"
            assert set(r["policy"] for r in result["results"]) == {"P1","P2","P3","P4"}
            assert all(r["finalEvaluationSplit"]=="test" and r["stabilityAndTargetSplit"]=="proxy" for r in result["results"])
            for filename in ("pareto-tradeoff-config.json","pareto-tradeoff-frontier.json","pareto-tradeoff-summary.md","pareto-tradeoff-results.csv","accuracy-virtual-time.svg"):
                assert (folder / "pareto" / filename).exists(), filename
            with sqlite3.connect(folder / "test.db") as db:
                before = db.execute("SELECT count(*) FROM rounds").fetchone()[0]
            launch("heldout_pareto", folder / "pareto.json", folder / "pareto", "pareto-completion.json")
            with sqlite3.connect(folder / "test.db") as db:
                assert db.execute("SELECT count(*) FROM rounds").fetchone()[0] == before
            print(f"Pareto smoke PASS (8 synthetic held-out runs, gate/resume/reuse/plots): {folder}", flush=True)
        finally:
            stop(worker)
            proxy.shutdown()
            proxy.server_close()
            proxy_thread.join(timeout=5)


if __name__ == "__main__":
    main()
