"""E0 gate -> validation-only lambda match -> locked held-out evaluation.

Each stage uses a frozen JAR/Python runtime, separate databases and fresh services.
--stage all runs E1 only after exact decision/model replay passes E0.
Existing completed runs can be re-analysed without resubmitting experiments.
"""
import argparse
import copy
import csv
from datetime import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys

from audit_seed45 import ROOT, audit, comparison, load_run, read, repeat, save, sha


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def scenario(config):
    """Same independent SHA-256 event channels as ScenarioTrace.generate (Java)."""
    def draw(round_id, client, channel):
        data = f"minifls-trace-v1|{config['seed']}|{round_id}|{client}|{channel}".encode()
        return (int.from_bytes(hashlib.sha256(data).digest()[:8], "big") >> 11) * 2.0**-53
    return {"version": 1, "generator": "sha256-independent-channels-v1",
            "scenario": {k: config[k] for k in ("seed", "rounds", "totalClients", "resourceProfile", "availability", "dropout", "jitter", "requiredRamMb", "deadlineSeconds")},
            "rounds": [{"roundId": r, "clients": [{"clientId": c,
                        "available": draw(r, c, "availability") < config["availability"],
                        "dropoutEvent": draw(r, c, "dropout") < config["dropout"],
                        "jitterMultiplier": 1 + config["jitter"] * (2 * draw(r, c, "jitter") - 1)}
                        for c in range(config["totalClients"])]} for r in range(1, config["rounds"] + 1)]}


def freeze_runtime(folder, protocol):
    frozen = folder / "freeze"
    frozen.mkdir()
    shutil.copy2(ROOT / "ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar", frozen / "runtime.jar")
    shutil.copytree(ROOT / "ml-python/minifls", frozen / "python/minifls", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for directory in ("ferderatedsystem/src", "configurations"):
        shutil.copytree(ROOT / directory, frozen / directory)
    for name in ("fairness_matched.py", "audit_seed45.py", "verify_fuzzy.py"):
        shutil.copy2(ROOT / "scripts" / name, frozen / name)
    save(frozen / "protocol.json", protocol)
    base = read(ROOT / protocol["baseProtocol"])
    save(frozen / "base-protocol.json", base)
    for name, cmd in {"git.diff": ["git", "diff", "--binary", "HEAD"],
                      "git-status.txt": ["git", "status", "--short"],
                      "git-commit.txt": ["git", "rev-parse", "HEAD"],
                      "pip-freeze.txt": [sys.executable, "-m", "pip", "freeze"],
                      "java-version.txt": ["java", "-version"]}.items():
        output = subprocess.check_output(cmd, cwd=ROOT, encoding="utf-8", errors="replace", stderr=subprocess.STDOUT)
        (frozen / name).write_text(output, encoding="utf-8")
    files = {p.relative_to(folder).as_posix(): sha(p) for p in frozen.rglob("*") if p.is_file()}
    save(folder / "frozen-hashes.json", files)


def verify_freeze(folder):
    for name, digest in read(folder / "frozen-hashes.json").items():
        assert sha(folder / name) == digest, f"Frozen runtime changed: {name}"


def base_config(folder, protocol):
    source = read(folder / "freeze/base-protocol.json")
    config = {**source["baseConfig"], **source["heterogeneousScenario"],
              "fuzzySelection": source["fuzzySelection"], "architecture": "mlp_54_256_128_7",
              "timing": protocol["timing"], "rounds": protocol["rounds"],
              "totalClients": protocol["clients"], "selectedPerRound": protocol["selectedPerRound"]}
    return config


def validate_protocol(p):
    assert p["timing"]["mode"] == "deterministic"
    assert p["validation"]["evaluationSplit"] == "proxy" and p["evaluation"]["evaluationSplit"] == "test"
    assert not set(p["validation"]["partitionSeeds"]) & set(p["evaluation"]["partitionSeeds"])
    assert len(set(p["fixedLambdas"])) == len(p["fixedLambdas"])
    assert all(0 <= value <= 1 for value in p["fixedLambdas"])
    assert p["e0"]["repeats"] >= 2
    assert set(p["e0"]["modes"]) == {"deterministic", "measured"}


def execute(folder, stage, name, config):
    if (folder / "STOP").exists():
        raise InterruptedError("STOP file present")
    verify_freeze(folder)
    directory = folder / stage / "runs" / name
    config = copy.deepcopy(config)
    config["experimentId"] = name
    trace = folder / "traces" / f"s{config['seed']}.json"
    document = scenario(config)
    if trace.exists():
        assert read(trace) == document
    else:
        save(trace, document)
    config["scenarioTracePath"] = trace.relative_to(ROOT).as_posix()
    if (directory / "experiment.json").exists():
        run = load_run(directory)
        assert {k:v for k,v in run["state"]["config"].items() if v is not None} == {k:v for k,v in config.items() if v is not None}, "Refusing reuse of a different config"
        assert run["state"]["status"] == "COMPLETED"
    else:
        assert not directory.exists(), f"Incomplete evidence exists; inspect before recovery: {directory}"
        run = repeat(directory, config, folder / "freeze/runtime.jar", folder / "freeze/python")
    snapshot = run["state"]["snapshot"]
    assert snapshot["scenarioTraceHash"] == sha(trace)
    manifest_dir = ROOT / config["manifestPath"]
    assert snapshot["manifest"] == read(manifest_dir / "manifest.json")
    for file, digest in snapshot["manifest"]["hashes"].items():
        assert sha(manifest_dir / file) == digest
    for row in run["rounds"]:
        assert row["scenarioTrace"] == document["rounds"][row["roundId"] - 1]
        assert row["evaluationSplit"] == config["evaluationSplit"]
        assert len(row["modelStateHash"]) == 64
        assert row["modelStateHash"] == row["evaluation"]["modelStateHash"]
        assert set(row["eligibleIds"]) == {c["clientId"] for c in row["scenarioTrace"]["clients"] if c["available"]}
        for participant in row["participants"]:
            assert len(participant["training"]["modelStateHash"]) == 64
    save(directory / "audit.json", audit(run))
    return run


def replay_projection(run):
    fields = ("selectedIds", "acceptedIds", "estimatedFeasibleIds", "criteriaObservations", "fuzzyTopsisScores",
              "fairnessCredits", "finalSelectionScores", "currentFairnessLambda", "nextFairnessLambda",
              "fairnessCreditsAfterRound", "fairness", "modelStateHash", "simulatedTrainingRoundSeconds")
    rows = []
    for row in run["rounds"]:
        projected = {key: row[key] for key in fields}
        projected["evaluation"] = {k: v for k, v in row["evaluation"].items() if k != "evaluationMs"}
        projected["localUpdates"] = {str(p["clientId"]): {
            "hash": p["training"]["modelStateHash"], "loss": p["training"]["trainingLoss"]} for p in row["participants"]}
        projected["decisionHistory"] = row["selectorInput"]["history"]
        rows.append(projected)
    return rows


def conditional_training_check(a, b):
    """Equal base tensors + client + round seed must give equal local tensor updates."""
    base_a = a["state"]["snapshot"]["initialModelStateHash"]
    base_b = b["state"]["snapshot"]["initialModelStateHash"]
    checked, failures = 0, []
    for x, y in zip(a["rounds"], b["rounds"]):
        if base_a == base_b:
            local_a = {p["clientId"]: p["training"] for p in x["participants"]}
            local_b = {p["clientId"]: p["training"] for p in y["participants"]}
            for client in local_a.keys() & local_b.keys():
                checked += 1
                if any(local_a[client][key] != local_b[client][key] for key in ("modelStateHash", "trainingLoss")):
                    failures.append({"round": x["roundId"], "client": client})
        base_a, base_b = x["modelStateHash"], y["modelStateHash"]
    return {"equalInputJobsChecked": checked, "differentOutputJobs": failures, "passed": not failures}


def e0(folder, protocol):
    config = base_config(folder, protocol)
    config.update(seed=protocol["e0"]["seed"], evaluationSplit="test")
    if protocol.get("smoke"):
        config["manifestPath"] = prepare_partition(folder, protocol, 45)
    groups, results = {}, []
    # Alternate policies; preserve the same protocol/build for both timing modes.
    for mode in protocol["e0"]["modes"]:
        for replicate in range(protocol["e0"]["repeats"]):
            for label, fixed_lambda in protocol["e0"]["policies"].items():
                c = copy.deepcopy(config)
                c["timing"]["mode"] = mode
                c["selection"] = "adaptive_fuzzy_topsis_fair" if fixed_lambda is None else "fuzzy_topsis_fair"
                if fixed_lambda is not None:
                    c["fuzzySelection"]["fairness"]["lambda"] = fixed_lambda
                name = f"e0-{folder.name}-{mode[:3]}-{label}-r{replicate+1}"
                run = execute(folder, "e0", name, c)
                groups.setdefault((mode, label), []).append(run)
                print(f"E0 completed {mode} {label} repeat {replicate+1}", flush=True)
    for (mode, label), runs in groups.items():
        for i, j in itertools.combinations(range(len(runs)), 2):
            a, b = runs[i], runs[j]
            assert a["state"]["snapshot"]["initialModelStateHash"] == b["state"]["snapshot"]["initialModelStateHash"]
            projected_a, projected_b = replay_projection(a), replay_projection(b)
            first = next((r+1 for r, (x, y) in enumerate(zip(projected_a, projected_b)) if x != y), None)
            result = comparison(a, b, folder / "e0" / f"{mode}-{label}-{i+1}-vs-{j+1}.csv")
            result.update(mode=mode, policy=label, firstProjectionDifference=first,
                          exactReplay=projected_a == projected_b,
                          conditionalTraining=conditional_training_check(a, b),
                          firstGlobalModelDifference=next((x["roundId"] for x,y in zip(a["rounds"], b["rounds"]) if x["modelStateHash"] != y["modelStateHash"]), None))
            results.append(result)
    initial = {r["state"]["snapshot"]["initialModelStateHash"] for runs in groups.values() for r in runs}
    assert len(initial) == 1
    passed = (all(r["exactReplay"] for r in results if r["mode"] == "deterministic")
              and all(r["conditionalTraining"]["passed"] for r in results))
    report = {"status": "PASS" if passed else "FAIL", "pairs": results,
              "exemptFromExactEquality": ["actualTrainingMs", "workerRssMb", "selectorComputationMs", "fairnessUpdateMs", "wallClockSeconds", "evaluationMs", "virtualSecondsIncludingMeasuredServerOverhead"],
              "meaning": "Exact replay gate is for deterministic decisions, local/global tensor hashes, learning metrics and pure simulated training time. Measured overhead remains observational."}
    save(folder / "e0/report.json", report)
    verify_freeze(folder)
    print(f"E0 {report['status']}: {folder / 'e0/report.json'}", flush=True)
    assert passed, "E0 deterministic replay failed: E1 is blocked"


def prepare_partition(folder, protocol, seed):
    directory = ROOT / "artifacts/partitions" / f"fm-{'smoke-' if protocol.get('smoke') else ''}{folder.name}-p{seed}"
    if not directory.exists():
        subprocess.run([sys.executable, "-m", "minifls.data", "--output", str(directory),
                        "--dataset", "synthetic" if protocol.get("smoke") else protocol["dataset"],
                        "--clients", str(protocol["clients"]), "--seed", str(protocol["splitSeed"]),
                        "--strategy", "dirichlet_label_skew", "--alpha", str(protocol["alpha"]),
                        "--partition-seed", str(seed)], cwd=folder,
                       env={**os.environ, "PYTHONPATH": str(folder / "freeze/python")}, check=True)
    manifest = read(directory / "manifest.json")
    assert manifest["partitionSeed"] == seed and manifest["seed"] == protocol["splitSeed"]
    assert manifest["alpha"] == protocol["alpha"]
    return directory.relative_to(ROOT).as_posix()


def select_lambda(records, settings):
    """Only partition/seed/policy/lambda/Gini fields are inspected, never learning scores."""
    adaptive = {(r["partition"], r["seed"]): r["gini"] for r in records if r["policy"] == "adaptive"}
    candidates = []
    for value in sorted({r["lambda"] for r in records if r["policy"] == "fixed"}):
        fixed = {(r["partition"], r["seed"]): r["gini"] for r in records if r["policy"] == "fixed" and r["lambda"] == value}
        assert fixed.keys() == adaptive.keys() and fixed, "Incomplete validation pairing"
        gaps = {key: abs(fixed[key] - adaptive[key]) for key in fixed}
        means = {p: statistics.mean(v for (part, _), v in gaps.items() if part == p) for p, _ in gaps}
        candidates.append({"lambda": value, "meanAbsolutePairedGap": statistics.mean(gaps.values()),
                           "partitionMeanAbsoluteGaps": means,
                           "maxPartitionMeanAbsoluteGap": max(means.values())})
    best = min(candidates, key=lambda r: (r["meanAbsolutePairedGap"], r["lambda"]))
    matched = (best["meanAbsolutePairedGap"] <= settings["meanAbsoluteGapTolerance"]
               and best["maxPartitionMeanAbsoluteGap"] <= settings["maxPartitionMeanAbsoluteGap"])
    return {"status": "MATCHED" if matched else "NO_MATCH", "selectedLambda": best["lambda"] if matched else None,
            "nearestCandidate": best, "candidates": candidates, "selectionUsedLearningMetrics": False}


def outcomes(run, protocol):
    rounds = run["rounds"]
    last = rounds[-1]
    window = rounds[-protocol["stabilityWindow"]:]
    accuracy = [r["evaluation"]["accuracy"] for r in rounds]
    fairness = last["fairness"]
    targets = {}
    initial = run["state"]["snapshot"]["initialEvaluation"]["accuracy"]
    for target in protocol["accuracyTargets"]:
        reached = next((i for i, value in enumerate([initial] + accuracy) if value >= target), None)
        targets[str(target)] = {"firstRound": reached, "sustainedThroughFinal": reached is not None and all(v >= target for v in ([initial] + accuracy)[reached:]),
                                "virtualWithSelectorSeconds": None if reached is None else 0 if reached == 0 else rounds[reached-1]["cumulativeVirtualSecondsWithSelector"]}
    selected = sum(len(r["selectedIds"]) for r in rounds)
    gini = [r["fairness"]["feasibleOpportunityAdjustedGini"] for r in rounds]
    threshold = run["state"]["config"]["fuzzySelection"]["fairness"]["targetFeasibleGini"]
    transition = next((i+1 for i in range(len(gini)-2) if all(v <= threshold for v in gini[i:i+3])), None)
    return {"accuracy": accuracy[-1], "macroF1": last["evaluation"]["macroF1"],
            "gini": fairness["feasibleOpportunityAdjustedGini"],
            "feasibleCoverage": fairness["feasibleSelectionCoverage"],
            "accuracyTailSd": statistics.stdev(r["evaluation"]["accuracy"] for r in window) if len(window)>1 else None,
            "macroF1TailSd": statistics.stdev(r["evaluation"]["macroF1"] for r in window) if len(window)>1 else None,
            "maxAccuracyDropPp": max([0] + [(a-b)*100 for a,b in zip(accuracy, accuracy[1:])]),
            "maxFeasibleStaleness": fairness["maxFeasibleSelectionStaleness"],
            "meanFeasibleStaleness": fairness["meanFeasibleSelectionStaleness"],
            "populationNeverSelectedRatio": 1-len({c for r in rounds for c in r["selectedIds"]})/run["state"]["config"]["totalClients"],
            "feasibleNeverSelectedRatio": 1-fairness["feasibleSelectionCoverage"],
            "firstThreeRoundsBelowControllerTarget": transition,
            "finalLambda": last["nextFairnessLambda"],
            "slotsChangedRatio": sum(r["slotsChangedVsTopsis"] for r in rounds)/selected if selected else None,
            "acceptedRatio": sum(len(r["acceptedIds"]) for r in rounds)/selected if selected else None,
            "simulatedTrainingSeconds": sum(r["simulatedTrainingRoundSeconds"] for r in rounds),
            "virtualWithSelectorSeconds": last["cumulativeVirtualSecondsWithSelector"],
            "wallSeconds": sum(r["wallClockSeconds"] for r in rounds), "targets": targets}


def stage_runs(folder, protocol, stage, lambdas):
    settings = protocol[stage]
    records, initialization, manifests = [], {}, {}
    for partition_seed in settings["partitionSeeds"]:
        manifest_path = prepare_partition(folder, protocol, partition_seed)
        manifest = read(ROOT / manifest_path / "manifest.json")
        common = {k: v for k, v in manifest["hashes"].items() if k != "partitions.npz"}
        if manifests:
            assert common == next(iter(manifests.values())), "Partition seeds changed train/proxy/test pools"
        manifests[partition_seed] = common
        for seed in settings["trainingSeeds"]:
            policies = [("fixed", value) for value in lambdas] + [("adaptive", None)]
            random.Random(partition_seed*1000 + seed).shuffle(policies)
            for policy, value in policies:
                config = copy.deepcopy(base_config(folder, protocol))
                config.update(manifestPath=manifest_path, seed=seed, evaluationSplit=settings["evaluationSplit"],
                              selection="adaptive_fuzzy_topsis_fair" if policy == "adaptive" else "fuzzy_topsis_fair")
                if value is not None:
                    config["fuzzySelection"]["fairness"]["lambda"] = value
                tag = "adapt" if value is None else str(value).replace(".", "p")
                name = f"{stage[:3]}-{folder.name}-p{partition_seed}-s{seed}-{tag}"
                run = execute(folder, stage, name, config)
                initial = run["state"]["snapshot"]["initialModelStateHash"]
                assert initialization.setdefault(seed, initial) == initial
                records.append({"name": name, "partition": partition_seed, "seed": seed,
                                "policy": policy, "lambda": value, **outcomes(run, protocol)})
                save(folder / stage / "progress.json", {"completed": len(records), "records": records})
                print(f"{stage}: {len(records)}/{len(settings['partitionSeeds'])*len(settings['trainingSeeds'])*(len(lambdas)+1)}", flush=True)
    summarize(folder, stage, records)
    return records


def summarize(folder, stage, records):
    save(folder / stage / "outcomes.json", records)
    # Keep seeds nested inside partitions; no claim that all cells are independent.
    summaries = {}
    for partition_seed in sorted({r["partition"] for r in records}):
        for policy, value in sorted({(r["policy"], r["lambda"]) for r in records}, key=str):
            rows = [r for r in records if r["partition"] == partition_seed and (r["policy"], r["lambda"]) == (policy, value)]
            entry = {}
            for key in ("accuracy", "macroF1", "gini", "accuracyTailSd", "maxAccuracyDropPp", "virtualWithSelectorSeconds", "acceptedRatio"):
                values = [r[key] for r in rows if r[key] is not None]
                entry[key] = {"mean": statistics.mean(values), "sampleSd": statistics.stdev(values) if len(values)>1 else None,
                              "min": min(values), "max": max(values)}
            summaries[f"p{partition_seed}:{policy}:{value}"] = entry
    save(folder / stage / "summary-by-partition.json", summaries)
    adaptive = {(r["partition"], r["seed"]): r for r in records if r["policy"] == "adaptive"}
    contrasts = []
    for row in records:
        if row["policy"] == "fixed":
            other = adaptive[(row["partition"], row["seed"])]
            contrasts.append({"partition": row["partition"], "seed": row["seed"], "fixedLambda": row["lambda"],
                              "direction": "adaptive_minus_fixed",
                              **{k: other[k]-row[k] for k in ("accuracy", "macroF1", "gini", "accuracyTailSd", "maxAccuracyDropPp", "virtualWithSelectorSeconds")
                                 if other[k] is not None and row[k] is not None}})
    save(folder / stage / "paired-differences.json", contrasts)
    with (folder / stage / "outcomes.csv").open("w", newline="", encoding="utf-8") as stream:
        keys = [k for k in records[0] if k != "targets"]
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5))
    means = []
    for policy, value in sorted({(r["policy"], r["lambda"]) for r in records}, key=str):
        rows = [r for r in records if (r["policy"], r["lambda"]) == (policy, value)]
        x, y = statistics.mean(r["gini"] for r in rows), statistics.mean(r["accuracy"] for r in rows)
        label = "Adaptive" if value is None else f"Fixed {value}"
        ax.scatter([r["gini"] for r in rows], [r["accuracy"] for r in rows], alpha=.18)
        ax.scatter([x], [y], marker="D", label=label)
        means.append((x, y))
    frontier = sorted((x,y) for x,y in means if not any(xx<=x and yy>=y and (xx<x or yy>y) for xx,yy in means))
    ax.plot([x for x,y in frontier], [y for x,y in frontier], linestyle="--", color="grey", label="Observed mean Pareto frontier")
    ax.set(xlabel="Final opportunity-adjusted selection Gini (lower is better)", ylabel="Final accuracy", title=f"{stage}: descriptive Accuracy–Gini trade-off")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(folder / stage / "accuracy-gini-pareto.png", dpi=160)
    fig.savefig(folder / stage / "accuracy-gini-pareto.svg")
    plt.close(fig)
    trajectories = []
    for record in records:
        run = load_run(folder / stage / "runs" / record["name"])
        ever_selected = set()
        for row in run["rounds"]:
            ever_selected.update(row["selectedIds"])
            trajectories.append({"name": record["name"], "partition": record["partition"], "seed": record["seed"],
                                 "policy": record["policy"], "lambda": record["lambda"], "round": row["roundId"],
                                 "accuracy": row["evaluation"]["accuracy"], "gini": row["fairness"]["feasibleOpportunityAdjustedGini"],
                                 "adaptiveLambda": row["currentFairnessLambda"],
                                 "maxFeasibleStaleness": row["fairness"]["maxFeasibleSelectionStaleness"],
                                 "populationNeverSelectedRatio": 1-len(ever_selected)/run["state"]["config"]["totalClients"],
                                 "slotsChangedVsTopsisRatio": row["slotsChangedVsTopsisRatio"],
                                 "modelStateHash": row["modelStateHash"]})
    with (folder / stage / "trajectories.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=trajectories[0])
        writer.writeheader()
        writer.writerows(trajectories)
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, field in zip(axes.flat, ("accuracy", "gini", "adaptiveLambda", "maxFeasibleStaleness", "populationNeverSelectedRatio", "slotsChangedVsTopsisRatio")):
        for policy, value in sorted({(r["policy"], r["lambda"]) for r in records}, key=str):
            values = {r: [t[field] for t in trajectories if t["round"] == r and (t["policy"],t["lambda"]) == (policy,value) and t[field] is not None] for r in range(1,len(run["rounds"])+1)}
            ax.plot(list(values), [statistics.mean(v) if v else float("nan") for v in values.values()], label="Adaptive" if value is None else f"Fixed {value}")
        ax.set(xlabel="Round", title=field)
    axes.flat[0].legend(fontsize=7)
    fig.suptitle(f"{stage}: descriptive means across partition/seed cells")
    fig.tight_layout()
    fig.savefig(folder / stage / "trajectories.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("e0", "validation", "evaluation", "all"), default="e0")
    parser.add_argument("--protocol", type=Path, default=ROOT / "configurations/fairness-matched.json")
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--smoke", action="store_true", help="3-round synthetic E0; never valid for the research E1 gate")
    args = parser.parse_args()
    folder = (args.folder or ROOT / "artifacts/fairness-matched" / datetime.now().strftime("%Y%m%d-%H%M%S")).resolve()
    assert folder.is_relative_to(ROOT)
    if not (folder / "frozen-hashes.json").exists():
        folder.mkdir(parents=True, exist_ok=False)
        protocol = read(args.protocol)
        if args.smoke:
            protocol.update(smoke=True, rounds=3)
        validate_protocol(protocol)
        freeze_runtime(folder, protocol)
    protocol = read(folder / "freeze/protocol.json")
    validate_protocol(protocol)
    verify_freeze(folder)
    print(f"Evidence: {folder}", flush=True)
    if args.stage in ("e0", "all"):
        e0(folder, protocol)
    if args.stage in ("validation", "evaluation", "all"):
        assert not protocol.get("smoke"), "Synthetic smoke does not authorize E1"
        assert read(folder / "e0/report.json")["status"] == "PASS", "E0 must pass first"
    if args.stage in ("validation", "all"):
        records = stage_runs(folder, protocol, "validation", protocol["fixedLambdas"])
        # Freeze a separate matching-only view: no test/accuracy/F1 fields enter matching.
        matching_records = [{k:r[k] for k in ("partition", "seed", "policy", "lambda", "gini")} for r in records]
        result = select_lambda(matching_records, protocol["matching"])
        result.update(protocolHash=canonical_hash(protocol), frozenRuntimeHash=canonical_hash(read(folder / "frozen-hashes.json")),
                      validationGiniHash=canonical_hash(matching_records), adaptiveConfig=base_config(folder, protocol)["fuzzySelection"])
        lock = folder / "policy-lock.json"
        if lock.exists():
            assert read(lock) == result, "Policy lock is immutable"
        else:
            save(lock, result)
        print(f"Validation: {result['status']}; fixed lambda={result['selectedLambda']}", flush=True)
    if args.stage in ("evaluation", "all"):
        lock = read(folder / "policy-lock.json")
        if lock["status"] != "MATCHED":
            print("NO_MATCH: held-out evaluation was not started. Do not claim fairness equivalence.", flush=True)
            return
        assert lock["protocolHash"] == canonical_hash(protocol)
        assert lock["frozenRuntimeHash"] == canonical_hash(read(folder / "frozen-hashes.json"))
        records = stage_runs(folder, protocol, "evaluation", [lock["selectedLambda"]])
        match = select_lambda(records, protocol["matching"])
        save(folder / "evaluation/fairness-check.json", {"status": match["status"], "details": match,
                                                      "policyRetuned": False,
                                                      "interpretation": "If held-out fairness is not matched, report a trade-off, not a fairness-matched learning advantage."})
    verify_freeze(folder)
    print("Stage complete", flush=True)


if __name__ == "__main__":
    main()
