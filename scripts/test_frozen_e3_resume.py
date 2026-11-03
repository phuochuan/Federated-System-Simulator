import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import resume_frozen_e3 as resume
from fuzzy_uncertainty_workflow import Workflow, digest


def fixture_controller(tmp_path):
    controller = resume.FrozenE3Controller.__new__(resume.FrozenE3Controller)
    controller.folder = tmp_path
    controller.config = dict(confirmationAlphas=[.5], confirmationPartitions=[3001], confirmationSeeds=[42], validationPartitionSeed=2001)
    controller.runtime = {"javaBuildHash": "frozen"}
    controller.state = {"stages": {s: "COMPLETED" for s in ("E2", "E4", "POLICY_LOCK")}}
    lock = dict(protocolHash=digest(controller.config), runtime=controller.runtime, policies=["C1", "C4", "C5"],
        confirmation=dict(alphas=[.5], partitions=[3001], seeds=[42], scenario="U0", checkpoint="final round only"))
    (tmp_path / "policy-lock.json").write_text(json.dumps(lock))
    (tmp_path / "e0-reproducibility-audit.json").write_text(json.dumps(dict(status="PASS", runtime=controller.runtime, protocolHash=digest(controller.config))))
    return controller, lock


def test_existing_policy_lock_is_used_without_validation_reselection(tmp_path):
    controller, lock = fixture_controller(tmp_path)
    original = (tmp_path / "policy-lock.json").read_bytes()
    assert controller.validate_lock() == lock
    assert (tmp_path / "policy-lock.json").read_bytes() == original
    assert json.loads((tmp_path / "confirmation-protocol.json").read_text())["expectedRuns"] == 3


@pytest.mark.parametrize("change", ["policies", "runtime", "scenario", "audit"])
def test_incompatible_lock_or_audit_fails_closed(tmp_path, change):
    controller, lock = fixture_controller(tmp_path)
    if change == "policies":
        lock["policies"] = ["C1", "C3", "C5"]
    elif change == "runtime":
        controller.runtime = {"javaBuildHash": "new-build"}
    elif change == "scenario":
        lock["confirmation"]["scenario"] = "U2"
    else:
        audit = tmp_path / "e0-reproducibility-audit.json"
        v = json.loads(audit.read_text());v["status"] = "FAIL";audit.write_text(json.dumps(v))
    (tmp_path / "policy-lock.json").write_text(json.dumps(lock))
    with pytest.raises(RuntimeError):
        controller.validate_lock()


def test_partition_is_verified_once_per_pair_per_launch(monkeypatch):
    controller = resume.FrozenE3Controller.__new__(resume.FrozenE3Controller)
    controller.partition_cache = {}
    calls = []
    def partition(self, alpha, seed):
        calls.append((alpha, seed));return f"a{alpha}-p{seed}"
    monkeypatch.setattr(Workflow, "partition", partition)
    for _ in range(15):
        assert controller.partition(.5, 3001) == "a0.5-p3001"
    controller.partition(.5, 3002)
    assert calls == [(.5, 3001), (.5, 3002)]


def test_frozen_source_and_build_validation_keeps_original_records(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, "ROOT", tmp_path)
    batch = tmp_path / "artifacts/batch";batch.mkdir(parents=True)
    original = tmp_path / "scientific.py";original.write_text("original")
    jar = batch / "coordinator.jar";jar.write_text("frozen")
    (batch / "source-identity.json").write_text(json.dumps({"scientific.py": resume.file_hash(original)}))
    (batch / "build-identity.json").write_text(json.dumps({"jarSHA256": resume.file_hash(jar)}))
    resume.verify_frozen_files(batch)
    original.write_text("changed")
    with pytest.raises(RuntimeError, match="Frozen source differs"):
        resume.verify_frozen_files(batch)


def test_only_exact_checkpoint_transport_budget_errors_are_recoverable():
    text = "Worker request failed method=POST route=/train worker=http://127.0.0.1:8000 attempts=2/8 reason=recovery budget exhausted"
    assert resume.known_checkpoint_transport_budget_error(text, "http://127.0.0.1:8000", 8)
    for changed in (text.replace("POST", "GET"), text.replace("/train", "/unknown"),
                    text.replace("2/8", "2/4"), text.replace("2/8", "9/8"),
                    "HTTP 409: "+text, text+" receipt mismatch", "Invalid scientific response"):
        assert not resume.known_checkpoint_transport_budget_error(changed, "http://127.0.0.1:8000", 8)
    assert not resume.known_checkpoint_transport_budget_error(text, "http://other-worker", 8)


def test_idle_sleep_guard_is_scoped_and_released_on_error():
    calls = []
    def set_state(flags):
        calls.append(flags);return 0x80000000
    with pytest.raises(ValueError):
        with resume.prevent_idle_sleep(set_state):
            raise ValueError("operation failed")
    assert calls == [0x80000001, 0x80000000]


def test_idle_sleep_guard_failure_does_not_claim_protection():
    with pytest.raises(OSError, match="refused"):
        with resume.prevent_idle_sleep(lambda flags: 0):
            pytest.fail("A failed sleep inhibitor must stop before training")


def test_transport_recovery_is_bounded_before_dispatch(monkeypatch):
    controller = resume.FrozenE3Controller.__new__(resume.FrozenE3Controller)
    controller.worker, controller.base = "http://127.0.0.1:8000", "http://api"
    controller.runtime = {"workerTransport": {"maxAttempts": 8}}
    controller.config = {"retryBudget": 3}
    controller.admitted = controller.admitted_rounds = 0
    run = {"config": {"experimentId": "x", "rounds": 70}, "retries": 3}
    calls = []
    def api(base, route, payload=None):
        calls.append((route, payload))
        return dict(status="FAILED", error="Worker request failed method=POST route=/train worker=http://127.0.0.1:8000 attempts=2/8 reason=recovery budget exhausted")
    monkeypatch.setattr(resume, "api", api)
    with pytest.raises(RuntimeError, match="attempt budget exhausted"):
        controller.run(run)
    assert calls == [("/experiments/x", None)]


def test_transport_recovery_verifies_before_resume(monkeypatch):
    controller = resume.FrozenE3Controller.__new__(resume.FrozenE3Controller)
    controller.worker, controller.base = "http://127.0.0.1:8000", "http://api"
    controller.runtime = {"workerTransport": {"maxAttempts": 8}}
    controller.config = {"retryBudget": 3}
    controller.admitted = controller.admitted_rounds = 0
    controller.status = lambda **fields: None
    sequence = []
    controller.wait_for_idle_worker = lambda: sequence.append("idle")
    controller.verify_resume_checkpoint = lambda run, row: sequence.append("verify") or 45
    def api(base, route, payload=None):
        if route.endswith("/resume"):
            sequence.append("resume");return {"status": "RUNNING"}
        return dict(status="FAILED", error="Worker request failed method=POST route=/train worker=http://127.0.0.1:8000 attempts=2/8 reason=recovery budget exhausted")
    monkeypatch.setattr(resume, "api", api)
    monkeypatch.setattr(Workflow, "run", lambda self, run: sequence.append("admit") or "done")
    run = {"config": {"experimentId": "x", "rounds": 70}, "retries": 0}
    assert controller.run(run) == "done"
    assert sequence == ["idle", "verify", "resume", "admit"]
    assert run["retries"] == 1


def test_same_run_transport_retry_keeps_one_admission_and_maximum_round_reservation(monkeypatch):
    controller = resume.FrozenE3Controller.__new__(resume.FrozenE3Controller)
    controller.worker, controller.base = "http://127.0.0.1:8000", "http://api"
    controller.runtime = {"workerTransport": {"maxAttempts": 8}}
    controller.config = {"retryBudget": 3}
    controller.admitted, controller.admitted_rounds = 2, 140
    controller.status = lambda **fields: None
    controller.wait_for_idle_worker = lambda: None
    controller.verify_resume_checkpoint = lambda run, row: 45
    error = "Worker request failed method=POST route=/train worker=http://127.0.0.1:8000 attempts=2/8 reason=recovery budget exhausted"
    failed = False
    def api(base, route, payload=None):
        if route.endswith("/resume"):
            return {"status": "RUNNING"}
        return {"status": "FAILED" if failed else "RUNNING", "error": error, "snapshot": {"round": 45}}
    monkeypatch.setattr(resume, "api", api)
    attempts = []
    def original(self, run):
        nonlocal failed
        attempts.append((self.admitted, self.admitted_rounds))
        self.admitted += 1
        self.admitted_rounds += 25 if failed else 70
        if not failed:
            failed = True
            raise RuntimeError(error)
    monkeypatch.setattr(Workflow, "run", original)
    controller.run({"config": {"experimentId": "x", "rounds": 70}, "retries": 0})
    assert attempts == [(2, 140), (2, 140)]
    assert (controller.admitted, controller.admitted_rounds) == (3, 210)


def test_recovery_checkpoint_corruption_prevents_resume(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(resume, "ROOT", tmp_path)
    controller = resume.FrozenE3Controller.__new__(resume.FrozenE3Controller)
    controller.folder, controller.worker = tmp_path, "http://worker"
    target = tmp_path / "artifacts/global.pt";target.parent.mkdir();target.write_bytes(b"unit-fixture")
    config = {"experimentId": "x", "manifestPath": "partition", "provenance": {"runtimeIdentity": "frozen"}}
    snapshot = {"round": 1, "modelVersion": 1, "checkpointPath": "artifacts/global.pt", "executionProvenance": config["provenance"]}
    response = {"modelStateHash": "expected"}
    receipt = target.with_suffix(".response.json")
    receipt.write_text(json.dumps({"response": response, "responseHash": digest(response)}))
    with sqlite3.connect(tmp_path / "experiments.db") as db:
        db.execute("CREATE TABLE rounds(experiment_id TEXT, round_id INTEGER, metrics TEXT)")
        db.execute("INSERT INTO rounds VALUES(?,?,?)", ("x", 1, json.dumps({"modelStateHash": "expected"})))
    monkeypatch.setattr(resume, "api", lambda *args: {"modelStateHash": "expected"})
    assert controller.verify_resume_checkpoint({"config": config}, {"config": config, "snapshot": snapshot}) == 1
    monkeypatch.setattr(resume, "api", lambda *args: {"modelStateHash": "corrupt"})
    with pytest.raises(RuntimeError, match="tensor integrity"):
        controller.verify_resume_checkpoint({"config": config}, {"config": config, "snapshot": snapshot})
    receipt.write_text(json.dumps({"response": response, "responseHash": "changed"}))
    with pytest.raises(RuntimeError, match="receipt integrity"):
        controller.verify_resume_checkpoint({"config": config}, {"config": config, "snapshot": snapshot})
