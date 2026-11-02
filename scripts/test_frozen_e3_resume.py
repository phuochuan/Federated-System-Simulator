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
