"""Figures consume exported evidence only; never return inputs to policy tuning."""
import json
from pathlib import Path
import statistics


def plot_report(results_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    path = Path(results_path)
    report = json.loads(path.read_text(encoding="utf-8"))
    if not report["complete"] or not report["results"]:
        return []
    records = report["results"]
    policies = sorted({r["policy"] for r in records})
    partitions = sorted({r["partitionSeed"] for r in records})
    colors = {p: plt.get_cmap("tab10")(i) for i, p in enumerate(policies)}
    labels = {p: f"{p} Adaptive" if p in ("M7", "P4") else f"{p} fixed λ={next(r['configuredLambda'] for r in records if r['policy'] == p):g}" for p in policies}
    title_prefix = "SYNTHETIC SMOKE — " if report.get("smoke") else ""
    written = []

    def save(fig, name):
        fig.tight_layout()
        for ext in ("png", "svg"):
            target = path.parent / f"{name}.{ext}"
            fig.savefig(target, dpi=160)
            written.append(target.name)
        plt.close(fig)

    fig, axes = plt.subplots(1, len(partitions), figsize=(5*len(partitions), 4), squeeze=False)
    for ax, partition in zip(axes.flat, partitions):
        means = []
        declared = None
        if report.get("analysisType") == "PARETO_COMPARISON":
            declared = next(p["accuracyGini2D"] for p in report["frontier"]["perPartition"] if p["partitionSeed"] == partition)
        for policy in policies:
            rows = [r for r in records if r["partitionSeed"] == partition and r["policy"] == policy and r["feasibleOpportunityAdjustedGini"] is not None and r["accuracy"] is not None]
            if not rows:
                continue
            x = [r["feasibleOpportunityAdjustedGini"] for r in rows]
            y = [r["accuracy"] for r in rows]
            ax.scatter(x, y, color=colors[policy], alpha=.3)
            if declared is not None:
                point = next(p for p in declared["points"] if p["policy"] == policy)
                if point["status"] == "UNASSESSED":
                    continue
                mx, my = point["means"]["feasibleOpportunityAdjustedGini"], point["means"]["accuracy"]
            else:
                mx, my = statistics.mean(x), statistics.mean(y)
            means.append((mx, my))
            ax.scatter([mx], [my], color=colors[policy], marker="D", label=labels[policy])
        frontier = sorted((x, y) for x, y in means if not any(xx <= x and yy >= y and (xx < x or yy > y) for xx, yy in means))
        if declared is not None:
            frontier = sorted((p["means"]["feasibleOpportunityAdjustedGini"], p["means"]["accuracy"]) for p in declared["points"] if p["status"] == "NONDOMINATED")
        ax.plot([x for x, y in frontier], [y for x, y in frontier], "--", color="grey")
        ax.set(xlabel="Final feasible opportunity-adjusted selection Gini", ylabel="Final accuracy", title=f"Partition {partition}")
        ax.legend(fontsize=8)
    fig.suptitle(f"{title_prefix}{report['phase']}: observed trade-off, no equivalence/superiority test")
    save(fig, "accuracy-gini-pareto")

    fig, axes = plt.subplots(1, len(partitions), figsize=(5*len(partitions), 4), squeeze=False)
    for ax, partition in zip(axes.flat, partitions):
        for policy in policies:
            rows = [r for r in records if r["partitionSeed"] == partition and r["policy"] == policy and r["accuracyTailSd"] is not None]
            ax.scatter([r["accuracyTailSd"] for r in rows], [r["accuracy"] for r in rows], color=colors[policy], label=labels[policy])
        ax.set(xlabel="Within-run proxy accuracy tail sample SD", ylabel="Final accuracy", title=f"Partition {partition}")
        ax.legend(fontsize=8)
    fig.suptitle(f"{title_prefix}Final accuracy vs within-run stability")
    save(fig, "learning-stability")

    if report.get("analysisType") == "PARETO_COMPARISON":
        fig, axes = plt.subplots(1, len(partitions), figsize=(5*len(partitions), 4), squeeze=False)
        for ax, partition in zip(axes.flat, partitions):
            for policy in policies:
                rows = [r for r in records if r["partitionSeed"] == partition and r["policy"] == policy and r["virtualSecondsWithSelector"] is not None]
                ax.scatter([r["virtualSecondsWithSelector"] for r in rows], [r["accuracy"] for r in rows], color=colors[policy], label=labels[policy])
            ax.set(xlabel="Virtual seconds including measured selector/fairness overhead", ylabel="Final test accuracy", title=f"Partition {partition}")
            ax.legend(fontsize=8)
        fig.suptitle(title_prefix + "Accuracy–efficiency trade-off")
        save(fig, "accuracy-virtual-time")

    def trajectories(name, fields):
        fig, axes = plt.subplots(len(fields), len(partitions), figsize=(5*len(partitions), 2.8*len(fields)), squeeze=False)
        for column, partition in enumerate(partitions):
            for row_index, (label, extract) in enumerate(fields):
                ax = axes[row_index, column]
                for policy in policies:
                    traces = [t["rounds"] for t in report["trajectories"] if t["policy"] == policy and t["cell"].startswith(f"{partition}:")]
                    if not traces:
                        continue
                    values = np.asarray([[extract(r) for r in trace] for trace in traces], dtype=float)
                    x = np.arange(1, values.shape[1]+1)
                    mean = values.mean(axis=0)
                    ax.plot(x, mean, color=colors[policy], label=labels[policy])
                    if len(values) > 1:
                        sd = values.std(axis=0, ddof=1)
                        ax.fill_between(x, mean-sd, mean+sd, color=colors[policy], alpha=.12)
                ax.set(xlabel="Round", ylabel=label, title=f"Partition {partition}")
                if row_index == 0:
                    ax.legend(fontsize=8)
        fig.suptitle(title_prefix + "Line: mean across seeds within partition; band: sample SD, not confidence interval")
        save(fig, name)

    trajectories("fairness-evolution", [
        ("Feasible selection Gini", lambda r: r["fairness"]["feasibleOpportunityAdjustedGini"]),
        ("Feasible completion/opportunity Gini", lambda r: r["fairness"]["feasibleCompletionOpportunityAdjustedGini"]),
        ("Max feasible selection staleness", lambda r: r["fairness"]["maxFeasibleSelectionStaleness"]),
        ("Population clients never selected", lambda r: r["populationNeverSelected"]),
    ])
    trajectories("adaptive-behavior", [
        ("Applied lambda", lambda r: r["currentFairnessLambda"]),
        ("Smoothed Gini (adaptive only)", lambda r: r.get("smoothedFeasibleSelectionGini") if r.get("smoothedFeasibleSelectionGini") is not None else float("nan")),
        ("Median credit after round", lambda r: statistics.median(r["fairnessCreditsAfterRound"].values()) if r["fairnessCreditsAfterRound"] else 0),
        ("Max credit after round", lambda r: max(r["fairnessCreditsAfterRound"].values(), default=0)),
        ("Slots changed / selected slots", lambda r: r["slotsChangedVsTopsisRatio"] if r["slotsChangedVsTopsisRatio"] is not None else float("nan")),
    ])
    return written
