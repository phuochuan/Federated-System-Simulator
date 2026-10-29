"""Prepare locked Pareto/E0 profiles from completed NO_MATCH Phase A; no training."""
import argparse
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--phase-a-root", type=Path, default=ROOT / "artifacts/research/retry-20261028-183037/e1")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", args.name):
        parser.error("Use only letters, digits, '-' and '_' in the profile name")
    source = args.phase_a_root.resolve()
    if not source.is_relative_to(ROOT):
        parser.error("Phase A source must stay in workspace")
    report_path, lock_path = source / "validation/fairness-matched-results.json", source / "policy-lock.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if not report["complete"] or lock["status"] != "NO_MATCH":
        parser.error("A completed NO_MATCH Phase A is required")
    protocol = copy.deepcopy(lock["protocol"])
    folder = ROOT / "artifacts/research" / ("pareto-"+args.name)
    protocol.update(analysisType="PARETO_COMPARISON", requireAudit=True, dataset="covertype", alpha=.5,
                    auditReportPath=(folder / "e0/reproducibility-audit.json").relative_to(ROOT).as_posix(), largeAccuracyDropPp=10.0)
    protocol["policies"] = [dict(id=f"P{i}", selection="adaptive_fuzzy_topsis_fair" if i == 4 else "fuzzy_topsis_fair", **{"lambda": value})
                            for i, value in enumerate((.65, .675, .725, .3), 1)]
    protocol["phaseA"] = dict(reportPath=report_path.relative_to(ROOT).as_posix(), lockPath=lock_path.relative_to(ROOT).as_posix(),
                              reportSha256=hashlib.sha256(report_path.read_bytes()).hexdigest(), lockSha256=hashlib.sha256(lock_path.read_bytes()).hexdigest())
    audit = json.loads((ROOT / "configurations/reproducibility-audit.json").read_text(encoding="utf-8"))
    for key in ("baseConfig", "heterogeneousScenario", "fuzzySelection", "timing"):
        audit[key] = copy.deepcopy(protocol[key])
    audit["nonIidManifestPath"] = protocol["nonIidManifestPath"]
    folder.mkdir(parents=True, exist_ok=False)
    for name, value in (("pareto-tradeoff-input.json", protocol), ("e0-input.json", audit)):
        (folder / name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    common = {"minifls.launch.workspace": ROOT.as_posix(), "spring.datasource.url": "jdbc:sqlite:"+(folder / "minifls.db").as_posix(),
              "minifls.launch.enabled": "true", "minifls.audit.config": (folder / "e0-input.json").as_posix(),
              "minifls.audit.output": (folder / "e0").as_posix(), "minifls.pareto.config": (folder / "pareto-tradeoff-input.json").as_posix(),
              "minifls.pareto.output": folder.as_posix()}
    for label, mode in (("e0", "reproducibility_audit"), ("preflight", "pareto_preflight"), ("pareto", "heldout_pareto"),
                        ("workflow", "pareto_workflow")):
        properties = {**common, "minifls.launch.method": mode}
        text = "\n".join(f"{key}={value}" for key, value in properties.items())+"\n"
        escaped = []
        for char in text:
            if ord(char) < 128:
                escaped.append(char)
            else:
                units = char.encode("utf-16-be")
                escaped.extend(f"\\u{int.from_bytes(units[i:i+2], 'big'):04x}" for i in range(0, len(units), 2))
        path = folder / f"{label}.properties"
        path.write_text("".join(escaped), encoding="ascii")
        argument = "--spring.config.additional-location="+path.as_uri()
        (folder / f"{label}-program-argument.txt").write_text(argument+"\n", encoding="utf-8")
        print(f"{label}: {argument}")
    print(f"Prepared ONLY: {folder}. Use workflow for sequential preflight -> E0 -> Pareto, or run stages separately on the SAME frozen build/runtime.")
    print("Clear conflicting old MINIFLS_* overrides from the IDE; paste ONE argument at a time, without wrapping quotes.")


if __name__ == "__main__":
    main()
