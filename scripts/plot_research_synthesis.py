"""Small static figures for the post-hoc evidence synthesis; no training."""
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/research-synthesis-20261104'


def main():
    folder = OUT / 'figures'
    folder.mkdir(exist_ok=True)
    runs = list(csv.DictReader((OUT / 'run-metrics.csv').open(encoding='utf-8')))
    runs = [r for r in runs if r['study'] == 'controlled-width-ablation']
    colors = dict(A0='#777777', A1='#1f77b4', A2='#ff9900', A3='#2b954b', A4='#a64ca6')

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(folder / (name + '.png'), dpi=160)
        fig.savefig(folder / (name + '.svg'))
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.3, 4.2))
    for policy in colors:
        y = [statistics.mean(float(r['accuracy']) for r in runs if r['policy'] == policy and float(r['alpha']) == a) * 100
             for a in (.1, .5, 1.)]
        ax.plot([.1, .5, 1.], y, 'o-', label=policy, color=colors[policy])
    ax.set(xlabel='Dirichlet alpha', ylabel='Final test Accuracy (%)', xticks=[.1, .5, 1.],
           title='Controlled ablation, U0: descriptive means')
    ax.legend(ncol=5)
    ax.grid(alpha=.2)
    save(fig, 'accuracy-by-alpha')

    data = json.loads((OUT / 'synthesis-data.json').read_text())['comparisons']
    fig, ax = plt.subplots(figsize=(7.3, 4.2))
    for i, policy in enumerate(('A2', 'A3', 'A4')):
        item = data[f'controlled-width-ablation/{policy}-A1/accuracy/all']
        lo, hi = item['exploratoryUnadjusted95PercentTInterval']
        mean = item['mean']
        ax.errorbar(mean * 100, i, xerr=[[(mean-lo)*100], [(hi-mean)*100]], fmt='o', color=colors[policy], capsize=4)
        for value in item['partitionEffects'].values():
            ax.plot(value*100, i+.12, 'x', color=colors[policy])
    ax.axvline(0, color='black', linewidth=.8)
    ax.set(yticks=[0, 1, 2], yticklabels=['A2 - A1', 'A3 - A1', 'A4 - A1'],
           xlabel='Paired Accuracy difference (percentage points)',
           title='Three partition means; exploratory unadjusted t intervals')
    ax.text(.01, -.22, 'x: partition effect. n=3 assignments; seeds/alphas are dependent repeats.', transform=ax.transAxes, fontsize=8)
    save(fig, 'partition-aware-accuracy-effects')

    rec = list(csv.DictReader((OUT / 'final-per-class-recall.csv').open(encoding='utf-8')))
    meta = {r['experiment']: r for r in runs}
    grid, labels = [], []
    for a in (.1, .5, 1.):
        for policy in ('A1', 'A3', 'A4'):
            ids = {eid for eid, r in meta.items() if r['policy'] == policy and float(r['alpha']) == a}
            grid.append([statistics.mean(float(r['recall']) for r in rec if r['experiment'] in ids and int(r['classIndex']) == c) for c in range(7)])
            labels.append(f'{policy}, alpha={a}')
    fig, ax = plt.subplots(figsize=(7.3, 4.6))
    im = ax.imshow(grid, vmin=0, vmax=1, cmap='viridis', aspect='auto')
    ax.set(xticks=range(7), yticks=range(9), yticklabels=labels,
           xlabel='Mapped class index (0..6 = original Covertype 1..7)',
           title='Final held-out class recall: mean across paired runs')
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            ax.text(j, i, f'{v:.2f}', ha='center', va='center', color='white' if v<.45 else 'black', fontsize=8)
    fig.colorbar(im, ax=ax, label='Recall')
    save(fig, 'per-class-recall')

    source = ROOT / 'results/research/controlled-fuzzy-ablation-20261104-002235-69ac39/offline-comparisons.csv'
    offline = list(csv.DictReader(source.open()))
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    policies = ('A2', 'A3', 'A4')
    means = [100 * statistics.mean(float(r['changedSelected']) > 0 for r in offline
                                  if r['treatment'] == p and r['control'] == 'A1') for p in policies]
    ax.bar(policies, means, color=[colors[p] for p in policies])
    ax.set(ylabel='States with a different selected set (%)', ylim=(0, 35),
           title='Offline same-state replay: decision changes, not FL gains')
    for i, v in enumerate(means):
        ax.text(i, v+.7, f'{v:.0f}%', ha='center')
    save(fig, 'offline-selection-changes')
    print('Generated four PNG/SVG figures')


if __name__ == '__main__':
    main()
