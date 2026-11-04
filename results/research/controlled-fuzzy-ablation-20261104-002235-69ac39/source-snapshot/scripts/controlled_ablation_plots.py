"""Standalone publication artifacts, regenerated without model evaluation/training."""
import csv
from collections import defaultdict
from pathlib import Path
import statistics


def read(folder,name):
    path=folder/name
    if path.exists():
        with path.open(encoding='utf-8',newline='') as f:
            yield from csv.DictReader(f)


def generate_plots(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=Path(folder);output=folder/'figures';output.mkdir(exist_ok=True)
    def save(name,title,draw):
        fig,ax=plt.subplots(figsize=(8,4.8));ax.set_title(title)
        draw(ax)
        if not ax.has_data():ax.text(.5,.5,'Insufficient evidence / no completed observations',ha='center',transform=ax.transAxes)
        if ax.get_legend_handles_labels()[0]:ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(output/(name+'.png'),dpi=180)
        fig.savefig(output/(name+'.svg'))
        plt.close(fig)
    def trajectories(ax,metric,label):
        groups=defaultdict(list)
        for r in read(folder,'trajectories.csv'):
            if r['stage'].startswith('AUDIT'):continue
            groups[(r['policy'],int(r['round']))].append(float(r[metric]))
        for policy in sorted({k[0] for k in groups}):
            rounds=sorted(k[1] for k in groups if k[0]==policy)
            ax.plot(rounds,[statistics.mean(groups[(policy,r)]) for r in rounds],label=policy)
        ax.set(xlabel='Round (proxy evaluation)',ylabel=label)
    save('accuracy-rounds','Proxy accuracy trajectories',lambda ax:trajectories(ax,'accuracy','Accuracy'))
    save('macro-f1-rounds','Proxy Macro-F1 trajectories',lambda ax:trajectories(ax,'macroF1','Macro-F1'))
    save('selection-gini-rounds','Population selection Gini trajectories',lambda ax:trajectories(ax,'selectionGini','Selection Gini'))
    def alpha(ax):
        groups=defaultdict(list)
        for r in read(folder,'run-results.csv'):groups[(r['policy'],float(r['alpha']))].append(float(r['accuracy']))
        for policy in sorted({k[0] for k in groups}):
            xx=sorted(k[1] for k in groups if k[0]==policy)
            ax.plot(xx,[statistics.mean(groups[(policy,x)]) for x in xx],marker='o',label=policy)
        ax.set(xlabel='Non-IID alpha',ylabel='Final accuracy (stage-specific split)')
    save('accuracy-alpha','Final accuracy by alpha (descriptive seed/partition means)',alpha)
    def paired(ax):
        groups=defaultdict(list)
        for r in read(folder,'paired-differences.csv'):
            if r['metric']=='accuracy':groups[r['comparison']].append(float(r['difference']))
        for i,(name,values) in enumerate(sorted(groups.items())):
            ax.scatter([i]*len(values),values,s=12,alpha=.5,label=name)
        ax.axhline(0,color='black',lw=.7);ax.set(xlabel='Contrast (see legend)',ylabel='Paired accuracy difference')
    save('paired-accuracy','All paired accuracy differences (correlated seed repeats)',paired)
    def fairness(ax):
        groups=defaultdict(list)
        for r in read(folder,'run-results.csv'):groups[r['policy']].append((float(r['opportunityGini']),float(r['accuracy'])))
        for policy,points in sorted(groups.items()):ax.scatter([p[0] for p in points],[p[1] for p in points],label=policy,s=16,alpha=.6)
        ax.set(xlabel='Opportunity-adjusted selection Gini',ylabel='Final accuracy')
    save('fairness-accuracy','Fairness and final accuracy',fairness)
    def sensitivity(ax,metric,label):
        groups=defaultdict(list)
        for r in read(folder,'width-sensitivity.csv'):
            if r[metric]!='':groups[float(r['width'])].append(float(r[metric]))
        xx=sorted(groups)
        if xx:ax.plot(xx,[statistics.mean(groups[x]) for x in xx],marker='o')
        ax.set(xlabel='Fixed TFN width (offline replay)',ylabel=label)
    save('width-ranking-change','Offline width sensitivity',lambda ax:sensitivity(ax,'changedSelected','Mean changed top-K clients vs A1'))
    save('width-selection-stability','Offline selection stability',lambda ax:sensitivity(ax,'topKOverlap','Mean top-K overlap with A1'))
    def effects(ax):
        groups=defaultdict(list)
        for r in read(folder,'paired-differences.csv'):
            if r['metric']=='accuracy':groups[(r['comparison'],r['partition'])].append(float(r['difference']))
        for contrast in sorted({k[0] for k in groups}):
            points=sorted((p,statistics.mean(v)) for (name,p),v in groups.items() if name==contrast)
            ax.plot([p[0] for p in points],[p[1] for p in points],marker='o',label=contrast)
        ax.axhline(0,color='black',lw=.7);ax.set(xlabel='Independent partition seed',ylabel='Mean within-partition accuracy effect')
    save('partition-effects','Per-partition effects (seed/alpha repeats averaged)',effects)
    def diagnostics(ax):
        # Aggregate into bins while streaming instead of plotting 80k points.
        groups=defaultdict(list)
        for r in read(folder,'calibration-diagnostics.csv'):
            if r['stage'].startswith('AUDIT'):continue
            if r['timeWidth']!='':groups[(r['policy'],round(float(r['timeWidth']),2))].append(float(r['timeRelativeError']))
        for policy in sorted({k[0] for k in groups}):
            points=sorted((x,statistics.mean(v)) for (p,x),v in groups.items() if p==policy)
            ax.plot([v[0] for v in points],[v[1] for v in points],marker='.',label=policy)
        ax.set(xlabel='Past-only time width (binned)',ylabel='Mean observed relative duration error')
    save('uncertainty-error-diagnostics','Selected-only width/error diagnostics',diagnostics)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    generate_plots(parser.parse_args().folder)
