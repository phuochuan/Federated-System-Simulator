import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from fuzzy_uncertainty_workflow import atomic, immutable, contains, transient
from fuzzy_uncertainty_reports import correlation, errors, summary
from research_watchdog import RestartBudget, run_lock, completed


def test_retry_classification():
    for value in ("HTTP 503: unavailable", "java.net.ConnectException", "Worker busy; only one active ML operation allowed"):
        assert transient(value)
    for value in ("HTTP 400: invalid config", "HTTP 409: operation ID request hash mismatch", "Invalid JSON response",
                  "HTTP 400: Connection reset", "HTTP 409: timed out", "Java/Python runtime changed", "ambiguous checkpoint without receipt", "scientific validation failure"):
        assert not transient(value)
    assert transient('HTTP 409: {"detail":"Worker busy; only one active ML operation allowed"}')
    assert not transient('HTTP 409: {"error":"Worker busy; only one active ML operation allowed"}')
    assert transient("Worker request failed method=POST route=/train reason=interrupted")
    assert not transient("HTTP 400: reason=interrupted")


def test_immutable_identity_and_atomic_write(tmp_path):
    path = tmp_path / "protocol.json"
    immutable(path, {"value": [1, 2]})
    immutable(path, {"value": (1, 2)})
    with pytest.raises(RuntimeError):
        immutable(path, {"value": [3]})
    assert json.loads(path.read_text()) == {"value": [1, 2]}
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_replacement_retries_only_temporary_windows_access_error(tmp_path, monkeypatch):
    import os
    original = os.replace
    attempts = []
    def replace(source, target):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("Windows reader holds destination")
        original(source, target)
    monkeypatch.setattr(os, "replace", replace)
    atomic(tmp_path / "status.json", {"status": "COMPLETED"})
    assert len(attempts) == 3
    assert json.loads((tmp_path / "status.json").read_text())["status"] == "COMPLETED"


def test_config_subset_preserves_default_fields_and_checks_provenance():
    actual = {"config": {"defaults": .1, "mode": "fixed"}, "runtime": {"hash": "abc"}}
    expected = {"config": {"mode": "fixed"}, "runtime": {"hash": "abc"}}
    assert contains(actual, expected)
    expected["runtime"]["hash"] = "changed"
    assert not contains(actual, expected)


def test_watchdog_sliding_budget_and_completion(tmp_path):
    budget = RestartBudget(2, 60)
    assert budget.admit(0) and budget.admit(5)
    assert not budget.admit(30)
    assert budget.admit(61)
    atomic(tmp_path / "completion.json", {"mode": "pilot", "status": "COMPLETED"})
    assert completed(tmp_path, "pilot")
    assert not completed(tmp_path, "full")
    atomic(tmp_path / "completion.json", {"mode": "full", "status": "COMPLETED"})
    assert completed(tmp_path, "pilot")


def test_run_lock_excludes_competitors(tmp_path):
    with run_lock(tmp_path / "run.lock"):
        with pytest.raises(RuntimeError):
            with run_lock(tmp_path / "run.lock"):
                pass
    with run_lock(tmp_path / "run.lock"):
        pass


def test_insufficient_evidence_and_rank_reference():
    assert errors([])["status"] == "INSUFFICIENT_EVIDENCE"
    assert errors([(2, 3), (2, 1)])["MAE"] == 1
    assert errors([(1, 0)])["meanRelativeError"] == pytest.approx(1e9)
    assert correlation([1, 2, 3], [1, 2, 3]) == 1
    assert correlation([1, 2, 3], [3, 2, 1]) == -1
    assert correlation([], []) is None
    assert summary([1])["sampleSD"] is None


def test_failure_reports_remain_explicit(tmp_path):
    from types import SimpleNamespace
    from fuzzy_uncertainty_reports import generate
    workflow = SimpleNamespace(folder=tmp_path, state={"runs": {}, "stages": {}, "progress": {"workflowStatus": "BLOCKED"}},
        config={"evidenceDatabases": [], "scenarios": ["U0"], "trainingSeeds": [42]}, stage="E0", mode="report-only")
    # Folder is external to root; no database exists so report must still be complete.
    result = generate(workflow)
    assert not result["calibrationEligible"]
    assert json.loads((tmp_path / "e0-uncertainty-measurement.json").read_text())["status"] == "INSUFFICIENT_EVIDENCE"
    assert json.loads((tmp_path / "e2-robustness-results.json").read_text())["status"] == "INCOMPLETE"
    assert (tmp_path / "fuzzy-mcdm-research-summary.md").exists()


def test_dead_experiment_cannot_poll_forever_after_sqlite_or_worker_failure(tmp_path, monkeypatch):
    import fuzzy_uncertainty_workflow as module
    workflow = module.Workflow.__new__(module.Workflow)
    workflow.base, workflow.folder = "http://unused", tmp_path
    workflow.config = dict(runBudget=0, roundBudget=0, minimumFreeDiskGB=0, recoverySeconds=2)
    workflow.admitted = workflow.admitted_rounds = 0
    run = dict(key="x", config={"experimentId": "x", "rounds": 3}, stage="E2", policy="C1", scenario="U0", seed=42, retries=0)
    workflow.state = {"runs": {"x": run}}
    workflow.status = lambda **fields: None
    monkeypatch.setattr(module, "api", lambda *args, **kwargs: dict(status="RUNNING", config=run["config"], snapshot={"round": 0}))
    ticks = iter([0, 0, 1, 10])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError, match="progress recovery budget exhausted"):
        workflow.run(run)
    assert run["status"] == "BLOCKED"
