import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # Xuất PNG trên máy hoặc CI không có giao diện đồ họa.
import matplotlib.pyplot as plt


def plot(paths, output):
    # Tách trục round và virtual time để tránh nhầm tốc độ hội tụ với thời gian chạy thật.
    fig, axes = plt.subplots(1,3,figsize=(14,4))
    for path in paths:
        with open(path,encoding="utf-8") as stream:
            rows=list(csv.DictReader(stream))
        label=Path(path).parent.name
        for ax,x,y in zip(axes,["round","cumulative_virtual_seconds","round"],["accuracy","accuracy","macro_f1"]):
            ax.plot([float(r[x]) for r in rows],[float(r[y]) for r in rows],label=label)
            ax.set_xlabel(x);ax.set_ylabel(y);ax.grid(alpha=.3)
    axes[-1].legend(fontsize=7)
    fig.tight_layout()
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("paths",nargs="+")
    p.add_argument("--output",default="artifacts/results/comparison.png")
    args=p.parse_args()
    plot(args.paths,args.output)
