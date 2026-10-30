"""Streaming analytics of committed evidence; absent observations remain absent."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import sqlite3
import statistics as stats
import time

from fuzzy_uncertainty_workflow import ROOT, api, atomic, digest


def summary(values):
    values = list(values)
    return dict(n=len(values), mean=stats.mean(values) if values else None,
                sampleSD=stats.stdev(values) if len(values) > 1 else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def errors(pairs):
    pairs = list(pairs)
    if not pairs:
        return dict(status="INSUFFICIENT_EVIDENCE", n=0)
    residuals = [actual-predicted for predicted, actual in pairs]
    return dict(status="OBSERVED", n=len(pairs), MAE=stats.mean(abs(e) for e in residuals),
                RMSE=math.sqrt(stats.mean(e*e for e in residuals)), bias=stats.mean(residuals),
                errorVariance=stats.pvariance(residuals),
                meanRelativeError=stats.mean(abs(a-p)/max(1e-9, abs(a)) for p, a in pairs),
                relativeErrorDenominator="max(abs(actual), 1e-9)")


class CSV:
    def __init__(self, folder, name, columns):
        self.path = folder / name
        self.tmp = self.path.with_suffix(".csv.tmp")
        self.stream = self.tmp.open("w", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.stream, fieldnames=columns, extrasaction="ignore")
        self.writer.writeheader()

    def row(self, **values):
        self.writer.writerow(values)

    def close(self):
        if self.stream.closed:
            return
        import os
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.tmp.replace(self.path)


def rounds(path):
    if not path.is_file():
        return
    # A read-only, disk-backed ordered cursor; never materialize all round JSON.
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"rounds", "experiments"} <= names:
            return
        for identifier, config, metrics in db.execute("SELECT e.id,e.config,r.metrics FROM rounds r JOIN experiments e ON e.id=r.experiment_id ORDER BY e.id,r.round_id"):
            yield identifier, json.loads(config), json.loads(metrics)


def correlation(left, right):
    # Spearman over complete strict rankings. Scores ties are separately reported.
    if len(left) < 2 or set(left) != set(right):
        return None
    positions = {client: rank for rank, client in enumerate(right)}
    n = len(left)
    return 1 - 6*sum((rank-positions[c])**2 for rank, c in enumerate(left))/(n*(n*n-1))


def generate(workflow):
    folder = workflow.folder
    outputs = []
    def table(name, columns):
        output = CSV(folder, name, columns.split(","))
        outputs.append(output)
        return output
    observations = table("e0-observations.csv", "database,experiment,round,client,selected,estimatedSeconds,baseEstimatedSeconds,measuredWorkerSeconds,simulationInputSeconds,effectiveSeconds,completed,reliability,selectionCount,completionCount,previousLoss,cpu,ramMb,status,deadline,dropoutEvent,jitterMultiplier,width,covered,residualHistorySize")
    diagnostics = table("e4-calibration-diagnostics.csv", "experiment,round,client,policy,width,relativeError,covered,residualHistorySize")
    comparisons = table("e1-ranking-comparison.csv", "experiment,round,scenario,width,reference,policy,topKOverlap,changedClients,spearman,rankingDisagreement,selectorMs,tiedScores,scoreMean,scoreSD")
    trajectories = table("accuracy-vs-rounds.csv", "experiment,stage,policy,scenario,alpha,partition,seed,round,split,accuracy,macroF1,loss,virtualSeconds,opportunityAdjustedGini")
    recalls = table("per-class-recall.csv", "experiment,stage,policy,alpha,partition,seed,classId,recall")
    run_csv = table("e2-robustness-results.csv", "experiment,stage,policy,scenario,alpha,partition,seed,status,accuracy,macroF1,loss,tailAccuracySD,maxAccuracyDrop,acceptedSelectedRatio,completionRate,virtualSeconds,selectorMs,deadlineMisses,feasibleSelectionCoverage,selectionGini,opportunityAdjustedGini,maxStaleness")
    robustness = table("ranking-robustness-vs-noise.csv", "experiment,round,policy,scenario,topKOverlap,changedClients,spearmanCommonCandidates,commonCandidates,observedFeasible,referenceFeasible")
    run_by_id = {r["config"]["experimentId"]: r for r in workflow.state["runs"].values()}
    final = {}
    tail = defaultdict(list)
    counters = defaultdict(lambda: defaultdict(float))
    # Scalar residuals can be large; online sufficient statistics avoid retaining them.
    sums = defaultdict(lambda: defaultdict(float))
    calibration_bins = defaultdict(lambda: [0, 0., 0.])
    known = selected = observed = missing = covered = coverage_n = 0
    eligible_c5 = total_c5 = 0
    replay_count = 0
    replay_summaries = defaultdict(list)
    databases = [ROOT / p for p in workflow.config.get("evidenceDatabases", [])] + [folder / "experiments.db"]
    def add_error(channel, predicted, actual):
        e = actual - predicted
        s = sums[channel]
        s["n"] += 1; s["sum"] += e; s["abs"] += abs(e); s["squared"] += e*e
        s["relative"] += abs(e)/max(1e-9, abs(actual))
    try:
        for database in dict.fromkeys(p.resolve() for p in databases):
            for identifier, config, row in rounds(database):
                run = run_by_id.get(identifier)
                pre = row.get("preRoundObservations", {})
                # Legacy evidence has immutable pre-round profiles and decision estimates.
                if not pre and row.get("selectorInput"):
                    fs = config.get("fuzzySelection") or {}
                    for p in row["selectorInput"].get("eligibleClients", []):
                        a, b = fs.get("reliabilityAlpha", 1), fs.get("reliabilityBeta", 1)
                        pre[str(p["clientId"])] = dict(estimatedTime=p.get("estimatedSeconds") if p.get("estimatedSeconds") is not None else
                            p["numSamples"]*config["localEpochs"]*config["priorSecondsPerSample"]/p["cpu"],
                            reliability=(p["completionCount"]+a)/(p["selectionCount"]+a+b), **p)
                participants = {str(p["clientId"]): p for p in row.get("participants", [])}
                chosen = set(row.get("selectedIds", []))
                for client, prediction in pre.items():
                    known += 1
                    participant = participants.get(str(client))
                    selected += int(int(client) in chosen)
                    record = dict(database=str(database.relative_to(ROOT)), experiment=identifier, round=row["roundId"], client=client,
                        selected=int(client) in chosen, estimatedSeconds=prediction.get("estimatedTime"),
                        baseEstimatedSeconds=prediction.get("baseEstimatedSeconds"), reliability=prediction.get("reliability"),
                        selectionCount=prediction.get("selectionCount"), completionCount=prediction.get("completionCount"),
                        previousLoss=prediction.get("previousLoss", prediction.get("recentTrainingLoss")), cpu=prediction.get("cpu"),
                        ramMb=prediction.get("ramMb"), deadline=config.get("deadlineSeconds"), residualHistorySize=prediction.get("residualHistorySize"))
                    if participant:
                        training, simulation = participant.get("training", {}), participant.get("simulation", {})
                        actual_ms = training.get("actualTrainingMs")
                        effective = simulation.get("virtualTrainingSeconds")
                        predicted = prediction.get("estimatedTime")
                        reliability = prediction.get("reliability")
                        outcome = int(participant["accepted"])
                        record.update(measuredWorkerSeconds=None if actual_ms is None else actual_ms/1000,
                            effectiveSeconds=effective, simulationInputSeconds=None if participant.get("durationInputMs") is None else participant["durationInputMs"]/1000,
                            completed=outcome, status=participant.get("status"), dropoutEvent=simulation.get("dropoutEvent"),
                            jitterMultiplier=simulation.get("jitterMultiplier"))
                        cell = row.get("fuzzyDecisionMatrix", {}).get("rows", {}).get(str(client), [])
                        criteria = row.get("fuzzyDecisionMatrix", {}).get("criteria", [])
                        time_index = next((i for i, c in enumerate(criteria) if c["name"] == "estimatedTime"), None)
                        if effective is not None and predicted is not None:
                            observed += 1
                            add_error("effectiveDuration", predicted, effective)
                            if record["simulationInputSeconds"] is not None and record["cpu"]:
                                base_duration = record["simulationInputSeconds"]/record["cpu"]
                                add_error("predictionBeforeSimulationJitter", predicted, base_duration)
                                add_error("stochasticSimulationEffect", base_duration, effective)
                            if actual_ms is not None:
                                # Worker runtime is physical, while prediction is a virtual device estimate.
                                add_error("workerExecutionDescriptiveOnly", predicted, actual_ms/1000)
                            if cell and time_index is not None:
                                tfn = cell[time_index]
                                width = (tfn["upper"]-tfn["middle"])/max(1e-9, tfn["middle"])
                                inside = tfn["lower"] <= effective <= tfn["upper"]
                                covered += int(inside); coverage_n += 1
                                record.update(width=width, covered=inside)
                                diagnostics.row(experiment=identifier, round=row["roundId"], client=client, policy=(run or {}).get("policy"),
                                    width=width, relativeError=abs(effective-predicted)/max(1e-9, predicted), covered=inside,
                                    residualHistorySize=prediction.get("residualHistorySize"))
                            if run and run["policy"] == "C5" and run["stage"] == "E4":
                                total_c5 += 1
                                eligible_c5 += int(prediction.get("residualHistorySize", 0) >= 5)
                        else:
                            missing += 1
                        if reliability is not None:
                            add_error("reliability", reliability, outcome)
                            bin_id = min(9, int(reliability*10))
                            bins = calibration_bins[bin_id]
                            bins[0] += 1; bins[1] += reliability; bins[2] += outcome
                    else:
                        missing += 1
                    observations.row(**record)
                if run:
                    ev = row.get("trajectoryEvaluation", row["evaluation"])
                    trajectories.row(experiment=identifier, stage=run["stage"], policy=run["policy"], scenario=run["scenario"], alpha=run["alpha"],
                        partition=run["partition"], seed=run["seed"], round=row["roundId"], split=row.get("trajectoryEvaluationSplit"),
                        accuracy=ev.get("accuracy"), macroF1=ev.get("macroF1"), loss=ev.get("loss"), virtualSeconds=row.get("cumulativeVirtualSeconds"),
                        opportunityAdjustedGini=row.get("fairness", {}).get("feasibleOpportunityAdjustedGini"))
                    values = tail[identifier]
                    accuracy = ev.get("accuracy")
                    if accuracy is not None:
                        if values:
                            counters[identifier]["maxDrop"] = max(counters[identifier]["maxDrop"], values[-1]-accuracy)
                        values.append(accuracy)
                        del values[:-10]
                    counter = counters[identifier]
                    counter["accepted"] += len(row.get("acceptedIds", [])); counter["selected"] += len(chosen)
                    counter["selectorMs"] += row.get("selectorComputationMs", 0)
                    counter["deadlines"] += sum(p.get("status") == "TIMEOUT" for p in participants.values())
                    final[identifier] = row  # At most one final row per run; strip bulky evidence below.
                    final[identifier] = {k: row.get(k) for k in ("roundId", "evaluation", "evaluationSplit", "fairness", "cumulativeVirtualSeconds")}
                if run and run["stage"] == "E2" and row["roundId"] <= 10 and row.get("selectorInput"):
                    decisions = []
                    for scenario in ("U0", run["scenario"]):
                        replay_config = json.loads(json.dumps(config))
                        replay_config["fuzzySelection"]["observationNoise"]["scenario"] = scenario
                        request = dict(config=replay_config, selectorInput=row["selectorInput"], round=row["roundId"])
                        cache = folder / "replay-cache" / (digest(request) + ".json")
                        if cache.exists():
                            result = json.loads(cache.read_text(encoding="utf-8"))
                        elif workflow.mode != "report-only" and workflow.stage == "REPORT":
                            result = api(workflow.base, "/research/replay", request)
                            atomic(cache, result)
                        else:
                            break
                        decisions.append(result[run["policy"]]["ranking"])
                    if len(decisions) == 2:
                        reference, noisy = decisions
                        k = config["selectedPerRound"]
                        common = set(reference) & set(noisy)
                        overlap = len(set(reference[:k]) & set(noisy[:k]))/max(1, min(k, len(reference)))
                        robustness.row(experiment=identifier, round=row["roundId"], policy=run["policy"], scenario=run["scenario"],
                            topKOverlap=overlap, changedClients=len(set(reference[:k])-set(noisy[:k])),
                            spearmanCommonCandidates=correlation([c for c in reference if c in common], [c for c in noisy if c in common]),
                            commonCandidates=len(common), observedFeasible=len(noisy), referenceFeasible=len(reference))
                # Diagnostic bounded sample, exact production replay. Cache is immutable evidence keyed by input/config.
                if row.get("selectorInput") and config.get("fuzzySelection") and replay_count < 100:
                    replay_count += 1
                    for width in (0., .1, .3):
                        replay_config = json.loads(json.dumps(config))
                        replay_config["fuzzySelection"]["uncertaintyFallback"] = width
                        request = dict(config=replay_config, selectorInput=row["selectorInput"], round=row["roundId"])
                        cache = folder / "replay-cache" / (digest(request) + ".json")
                        if cache.exists():
                            result = json.loads(cache.read_text(encoding="utf-8"))
                        elif workflow.mode == "report-only" or workflow.stage not in ("E1", "REPORT"):
                            continue
                        else:
                            result = api(workflow.base, "/research/replay", request)
                            atomic(cache, result)
                        baseline = result["C1"]["ranking"]
                        k = min(config["selectedPerRound"], len(baseline))
                        for policy, decision in result.items():
                            if policy == "C5":
                                continue
                            ranking = decision["ranking"]
                            overlap = len(set(baseline[:k]) & set(ranking[:k]))/k if k else None
                            spearman = correlation(baseline, ranking)
                            positions = {c: i for i, c in enumerate(ranking)}
                            n = len(baseline)
                            inversions = sum(positions[baseline[i]] > positions[baseline[j]] for i in range(n) for j in range(i+1, n))
                            disagreement = inversions/(n*(n-1)/2) if n > 1 else None
                            scores = list(decision["scores"].values())
                            comparisons.row(experiment=identifier, round=row["roundId"], scenario=(run or {}).get("scenario", "historical"), width=width, reference="C1", policy=policy,
                                topKOverlap=overlap, changedClients=None if overlap is None else round(k*(1-overlap)), spearman=spearman,
                                rankingDisagreement=disagreement, selectorMs=decision["selectorMs"], tiedScores=len(scores)-len(set(scores)),
                                scoreMean=stats.mean(scores) if scores else None, scoreSD=stats.stdev(scores) if len(scores)>1 else None)
                            if overlap is not None:
                                replay_summaries[f"{policy}/width={width}"].append(overlap)
    except BaseException:
        for output in outputs:
            output.close()
        raise
    finally:
        for output in outputs[:4]:
            output.close()
    error_summary = {}
    for channel, s in sums.items():
        n = s["n"]
        error_summary[channel] = dict(n=int(n), MAE=s["abs"]/n, RMSE=math.sqrt(s["squared"]/n), bias=s["sum"]/n,
            errorVariance=max(0, s["squared"]/n-(s["sum"]/n)**2), meanRelativeError=s["relative"]/n)
    reliability = sums["reliability"]
    measurement = dict(status="OBSERVED_SELECTION_CONDITIONAL" if observed else "INSUFFICIENT_EVIDENCE", observed=observed,
        availablePreRoundRecords=known, selected=selected, missingOutcomes=missing, errors=error_summary,
        BrierScore=reliability["squared"]/reliability["n"] if reliability["n"] else None,
        intervalCoverage=covered/coverage_n if coverage_n else None, intervalN=coverage_n,
        reliabilityCalibration=[dict(bin=i, n=b[0], predicted=b[1]/b[0], actual=b[2]/b[0]) for i, b in sorted(calibration_bins.items())],
        limitations=["Outcomes are observed only for executed clients; no population causal uncertainty claim.",
            "Virtual duration forecasts and physical worker runtime have different targets.",
            "Fuzzy TFNs are bounded decision representations; no nominal confidence coverage is claimed.",
            "Legacy observations without immutable pre-round profiles remain missing."])
    atomic(folder / "e0-uncertainty-measurement.json", measurement)
    atomic(folder / "e0-uncertainty-measurement.md", "# Uncertainty measurement\n\n" + json.dumps(measurement, indent=2) + "\n")
    replay = dict(status="OFFLINE_REPLAY" if replay_summaries else "INSUFFICIENT_EVIDENCE", decisionSampleLimit=100,
        topKOverlap={k: summary(v) for k, v in replay_summaries.items()},
        interpretation="Same immutable state. No model updates; these are not counterfactual FL outcomes. Spearman uses ID tie-broken strict ranks; tied score counts are exported.")
    atomic(folder / "e1-crisp-fuzzy-ablation.json", replay)
    atomic(folder / "e1-crisp-fuzzy-ablation.md", "# Crisp versus fuzzy diagnostic\n\nConventional Crisp uses column L2 normalization, weighted extrema ideals, Euclidean distance. Existing zero-width Fuzzy uses benefit maximum/cost reciprocal normalization and sums absolute criterion distances. They need not agree. Both tie by ascending client ID; identical alternatives score 0.5.\n\n" + json.dumps(replay, indent=2) + "\n")
    results = []
    for identifier, run in run_by_id.items():
        if run["stage"].startswith("AUDIT"):
            continue
        result = dict(experiment=identifier, **{k: run[k] for k in ("stage", "policy", "scenario", "alpha", "partition", "seed", "status")})
        row = final.get(identifier)
        if row:
            ev, fairness = row["evaluation"], row["fairness"]
            count = counters[identifier]
            result.update(accuracy=ev.get("accuracy"), macroF1=ev.get("macroF1"), loss=ev.get("loss"),
                evaluationSplit=row["evaluationSplit"], finalRound=row["roundId"],
                tailAccuracySD=stats.stdev(tail[identifier]) if len(tail[identifier]) > 1 else None,
                maxAccuracyDrop=count["maxDrop"], acceptedSelectedRatio=count["accepted"]/count["selected"] if count["selected"] else None,
                completionRate=count["accepted"]/count["selected"] if count["selected"] else None,
                virtualSeconds=row["cumulativeVirtualSeconds"], selectorMs=count["selectorMs"], deadlineMisses=count["deadlines"],
                feasibleSelectionCoverage=fairness.get("feasibleSelectionCoverage"), selectionGini=fairness.get("selectionGini"),
                opportunityAdjustedGini=fairness.get("feasibleOpportunityAdjustedGini"), maxStaleness=fairness.get("maxFeasibleSelectionStaleness"))
            for i, recall in enumerate(ev.get("perClassRecall", [])):
                recalls.row(experiment=identifier, stage=run["stage"], policy=run["policy"], alpha=run["alpha"], partition=run["partition"], seed=run["seed"], classId=i, recall=recall)
        results.append(result)
        run_csv.row(**result)
    recalls.close(); run_csv.close(); robustness.close()
    atomic(folder / "e2-robustness-results.json", dict(status=workflow.state["stages"].get("E2", "INCOMPLETE"), runs=[r for r in results if r["stage"] == "E2"]))
    pairs = []
    for r in results:
        if r["policy"] == "C5" and r["stage"] == "E4" and r["status"] == "COMPLETED":
            baseline = next((b for b in results if b["stage"] == "E2" and b["policy"] == "C4" and b["seed"] == r["seed"] and b["scenario"] == r["scenario"] and b["status"] == "COMPLETED"), None)
            if baseline:
                pairs.append(r["accuracy"]-baseline["accuracy"])
    required = len(workflow.config["scenarios"])*len(workflow.config["trainingSeeds"])
    calibration = dict(calibrationEligible=len(pairs) == required and bool(pairs) and stats.mean(pairs) >= 0 and total_c5 > 0 and eligible_c5/total_c5 >= .5,
        pairedProxyAccuracyDifference=summary(pairs), pairedValidationRuns=len(pairs), requiredPairs=required,
        matureObservationFraction=eligible_c5/total_c5 if total_c5 else None,
        interpretation="Validation screening only, not statistical evidence of superiority. Baselines retained when sparse or worse.")
    atomic(folder / "e4-calibration-results.json", dict(status=workflow.state["stages"].get("E4", "INCOMPLETE"), decision=calibration, runs=[r for r in results if r["policy"] in ("C3", "C4", "C5") and r["stage"] != "E3"]))
    atomic(folder / "e4-calibration-results.md", "# Prediction-error calibration\n\nPast selected-client residuals only; nearest-rank 80th percentile of last 32 absolute relative time errors and absolute reliability errors. Minimum five; prior .1; cap .45. Utility retains prior width because no validated utility prediction target exists. History-based equations are unchanged.\n\n" + json.dumps(calibration, indent=2) + "\n")
    atomic(folder / "plot-data-index.json", {
        "accuracyVsRounds": {"csv": "accuracy-vs-rounds.csv", "x": "round", "y": "accuracy"},
        "accuracyVsUncertainty": {"csv": "e2-robustness-results.csv", "x": "scenario", "y": "accuracy"},
        "macroF1VsUncertainty": {"csv": "e2-robustness-results.csv", "x": "scenario", "y": "macroF1"},
        "rankingRobustnessVsNoise": {"csv": "ranking-robustness-vs-noise.csv", "x": "scenario", "y": "spearmanCommonCandidates"},
        "topKOverlapVsNoise": {"csv": "ranking-robustness-vs-noise.csv", "x": "scenario", "y": "topKOverlap"},
        "predictionErrorDistribution": {"csv": "e0-observations.csv", "predicted": "estimatedSeconds", "actual": "effectiveSeconds"},
        "fuzzyWidthVsError": {"csv": "e4-calibration-diagnostics.csv", "x": "width", "y": "relativeError"},
        "accuracyVsVirtualTime": {"csv": "accuracy-vs-rounds.csv", "x": "virtualSeconds", "y": "accuracy"},
        "opportunityAdjustedGini": {"csv": "accuracy-vs-rounds.csv", "x": "round", "y": "opportunityAdjustedGini"},
        "perClassRecall": {"csv": "per-class-recall.csv", "x": "classId", "y": "recall"}})
    aggregates = defaultdict(list)
    paired = defaultdict(list)
    for r in results:
        if r["status"] == "COMPLETED" and "accuracy" in r:
            aggregates[f'{r["stage"]}/{r["policy"]}/{r["scenario"]}/alpha={r["alpha"]}'].append(r["accuracy"])
            if r["stage"] == "E3" and r["policy"] != "C1":
                baseline = next((b for b in results if b["stage"] == "E3" and b["policy"] == "C1" and b["seed"] == r["seed"] and b["alpha"] == r["alpha"] and b["partition"] == r["partition"] and b["status"] == "COMPLETED"), None)
                if baseline:
                    paired[f'{r["policy"]}-C1/alpha={r["alpha"]}'].append(r["accuracy"]-baseline["accuracy"])
    partition_summaries = defaultdict(lambda: defaultdict(list))
    alpha_summaries = defaultdict(lambda: defaultdict(list))
    paired_metrics = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r["status"] != "COMPLETED" or r["stage"] != "E3":
            continue
        for metric in ("accuracy", "macroF1", "loss", "tailAccuracySD", "maxAccuracyDrop", "virtualSeconds", "opportunityAdjustedGini", "acceptedSelectedRatio", "selectorMs"):
            if r.get(metric) is None:
                continue
            partition_summaries[f'{r["policy"]}/alpha={r["alpha"]}/partition={r["partition"]}'][metric].append(r[metric])
            alpha_summaries[f'{r["policy"]}/alpha={r["alpha"]}'][metric].append(r[metric])
            baseline = next((b for b in results if b["stage"] == "E3" and b["policy"] == "C1" and b["seed"] == r["seed"] and b["alpha"] == r["alpha"] and b["partition"] == r["partition"] and b["status"] == "COMPLETED"), None)
            if r["policy"] != "C1" and baseline and baseline.get(metric) is not None:
                paired_metrics[f'{r["policy"]}-C1/alpha={r["alpha"]}'][metric].append(r[metric]-baseline[metric])
    progress_status = workflow.state.get("progress", {}).get("workflowStatus", "INCOMPLETE")
    stages = workflow.state["stages"]
    finished = stages.get("E3") == "COMPLETED" or (workflow.mode == "pilot" and stages.get("E2") == "COMPLETED" and stages.get("E4") == "COMPLETED")
    report_status = progress_status if progress_status in ("BLOCKED", "RETRYABLE_FAILURE", "BUDGET_REACHED") else ("COMPLETED" if finished else "INCOMPLETE")
    report = dict(perPartition={k: {m: summary(v) for m, v in metrics.items()} for k, metrics in partition_summaries.items()},
        perAlpha={k: {m: summary(v) for m, v in metrics.items()} for k, metrics in alpha_summaries.items()},
        pairedMetrics={k: {m: summary(v) for m, v in metrics.items()} for k, metrics in paired_metrics.items()}, status=report_status,
        accuracySummaries={k: summary(v) for k, v in aggregates.items()}, pairedAccuracyDifferences={k: summary(v) for k, v in paired.items()},
        runs=results, anomalies=[dict(run=r["key"], status=r["status"], error=r.get("lastError")) for r in workflow.state["runs"].values() if r["status"] in ("FAILED", "BLOCKED", "RETRYABLE_FAILURE")])
    atomic(folder / "e3-heldout-results.json", report)
    atomic(folder / "e2-robustness-summary.md", "# Robustness\n\n" + json.dumps(report["accuracySummaries"], indent=2) + "\n\nPartial runs are excluded from complete-run summaries. U3, when configured, is counted separately from U0-U2.\n")
    sections = ["Research objectives and hypotheses", "Existing Fuzzy TOPSIS formulation", "Uncertainty measurement", "Crisp vs Fuzzy comparison",
        "Ranking sensitivity", "Uncertainty robustness", "Prediction-error calibration", "End-to-end FL results",
        "Accuracy, Macro-F1, fairness and efficiency comparisons", "Reproducibility and runtime provenance", "Limitations", "Supported and unsupported research claims"]
    texts = ["RQ1-RQ4 evaluate effectiveness and robustness without assuming Fuzzy superiority.",
        "Data-derived componentwise fuzzy ideals, vertex distances summed by criterion; see docs/fuzzy-mcdm-client-selection.md.",
        f'{observed} observed outcomes, {missing} missing. See e0-uncertainty-measurement.json. Selection bias prevents population-wide interpretation.',
        "See e1-crisp-fuzzy-ablation.json and ranking CSV; conventional Crisp and zero-width Fuzzy differ mathematically.",
        "Bounded 100-state immutable replay sample at widths 0/.1/.3. No counterfactual FL claim.",
        "See E2 JSON/CSV. Noise affects observations only; deterministic full-population scenario traces are paired.",
        json.dumps(calibration), "See e3-heldout-results.json. Only completed final-round checkpoints enter held-out summaries.",
        "CSV exports include proxy trajectories, final per-class recall, efficiency, opportunity Gini, staleness and stability. Per-run partition identities remain explicit.",
        "runtime-identity.json, protocol.json, trace files, policy-lock.json and e0-reproducibility-audit.json identify this executing batch.",
        "Two-seed pilots support screening. Correlated seed repeats within partitions are not independent partitions. Sample SD and ranges are descriptive uncertainty summaries, not significance tests. Deterministic timing is a simulator model; physical runtime differs. No recovery guarantee for power loss, sleep or full disk.",
        "No automatic superiority claim. Missing/incomplete outcomes remain explicit. Offline rank changes do not establish FL improvement."]
    content = f"# Fuzzy MCDM research summary\n\nWorkflow status: {report_status}. Stage: {workflow.stage}.\n\n" + "\n\n".join(f"## {i}. {title}\n\n{text}" for i, (title, text) in enumerate(zip(sections, texts), 1))
    content += "\n\nActual completed-run accuracy summaries:\n\n```json\n" + json.dumps(report["accuracySummaries"], indent=2) + "\n```\n"
    atomic(folder / "fuzzy-mcdm-research-summary.md", content)
    return calibration
