"""Rebuild compact, post-hoc research synthesis from immutable published evidence.

No training, model deserialization, checkpoint changes or selection of policies.
Only the newly named synthesis directory is written. Historical publications are
read-only. Published binary archives are hashed, not interpreted as learning data.
"""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/research-synthesis-20261104'
BASE = ROOT / 'results/research'
CONTROLLED = BASE / 'controlled-fuzzy-ablation-20261104-002235-69ac39'
FUZZY = BASE / 'fuzzy-uncertainty-20261031-004757-b6b730-full-20261103'
PARETO = BASE / 'pareto-20261028-204148'
METRICS = ('accuracy', 'macroF1', 'loss', 'minorityRecall', 'tailAccuracySD',
           'acceptedSelectedRatio', 'selectionGini', 'opportunityGini',
           'feasibleSelectionCoverage', 'maxStaleness', 'virtualSeconds')
ALIASES = dict(opportunityGini='opportunityAdjustedGini', tailAccuracySD='accuracyTailSd')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_out(name, data):
    path = OUT / name
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def csv_out(name, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def stats(values):
    values = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                sampleSD=statistics.stdev(values) if len(values) > 1 else None,
                median=statistics.median(values) if values else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def cluster_summary(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r['partition']].append(r['difference'])
    effects = {p: statistics.mean(v) for p, v in groups.items()}
    summary = stats(effects.values())
    values = list(effects.values())
    summary.update(independentPartitions=len(values), descriptiveSeedPairs=len(rows),
                   partitionEffects=effects,
                   positivePairs=sum(r['difference'] > 1e-12 for r in rows),
                   negativePairs=sum(r['difference'] < -1e-12 for r in rows),
                   tiedPairs=sum(abs(r['difference']) <= 1e-12 for r in rows),
                   positivePartitions=sum(v > 1e-12 for v in values),
                   negativePartitions=sum(v < -1e-12 for v in values),
                   leaveOnePartitionOut={p: statistics.mean(v for q, v in effects.items() if p != q)
                                            for p in effects} if len(values) > 1 else {},
                   inference='Exploratory descriptive synthesis; no new confirmatory tests or policy tuning')
    # All main completed studies have exactly three assignment clusters.
    # The normality assumption cannot be checked with n=3; never call this proof.
    if len(values) == 3 and summary['sampleSD'] is not None:
        radius = 4.302652729911275 * summary['sampleSD'] / math.sqrt(3)
        summary['exploratoryUnadjusted95PercentTInterval'] = [summary['mean'] - radius, summary['mean'] + radius]
    else:
        summary['exploratoryUnadjusted95PercentTInterval'] = None
    return summary


def read_runs():
    runs = []
    for folder, filename, study in [(CONTROLLED, 'controlled-ablation-results.json', 'controlled-width-ablation'),
                                     (FUZZY, 'e3-heldout-results.json', 'fuzzy-workflow')]:
        data = load(folder / filename)
        for raw in data['runs']:
            row = {k: raw.get(k, raw.get(ALIASES.get(k, ''))) for k in METRICS}
            row.update(study=study, experiment=raw['experiment'], stage=raw['stage'], policy=raw['policy'],
                       alpha=raw['alpha'], partition=raw['partition'], seed=raw['seed'],
                       scenario=raw.get('scenario', 'U0'),
                       evaluationSplit=raw.get('evaluationSplit', 'test'),
                       finalRound=raw.get('finalRound', 70),
                       source=(folder / filename).relative_to(ROOT).as_posix())
            runs.append(row)
    pareto = load(PARETO / 'pareto-tradeoff-results.json')
    for raw in pareto['results']:
        row = {k: raw.get(k, raw.get(ALIASES.get(k, ''))) for k in METRICS}
        row['opportunityGini'] = raw['feasibleOpportunityAdjustedGini']
        row.update(study='fairness-pareto', experiment=raw['experimentId'], stage='PARETO', policy=raw['policy'],
                   alpha=None, partition=raw['partitionSeed'], seed=raw['trainingScenarioSeed'], scenario=None,
                   evaluationSplit=raw['finalEvaluationSplit'], finalRound=70,
                   source=(PARETO / 'pareto-tradeoff-results.json').relative_to(ROOT).as_posix())
        runs.append(row)
    ids = [r['experiment'] for r in runs]
    if len(set(ids)) != len(ids):
        raise RuntimeError('Duplicate experiment counted in synthesis')
    expected = Counter({('controlled-width-ablation', 'FULL'): 225,
                        ('fuzzy-workflow', 'E2'): 24, ('fuzzy-workflow', 'E4'): 6,
                        ('fuzzy-workflow', 'E3'): 135, ('fairness-pareto', 'PARETO'): 60})
    if Counter((r['study'], r['stage']) for r in runs) != expected:
        raise RuntimeError('Unexpected study/stage counts; never silently pool snapshots')
    return runs


def comparisons(runs):
    result, paired = {}, []
    specifications = [('controlled-width-ablation', 'FULL', a, b) for a, b in
                      [('A2', 'A1'), ('A3', 'A1'), ('A4', 'A1'), ('A3', 'A2'), ('A4', 'A3'), ('A1', 'A0')]]
    specifications += [('fuzzy-workflow', 'E3', a, b) for a, b in [('C4', 'C1'), ('C5', 'C1'), ('C5', 'C4')]]
    specifications += [('fairness-pareto', 'PARETO', 'P4', p) for p in ('P1', 'P2', 'P3')]
    for study, stage, treatment, control in specifications:
        rows = [r for r in runs if (r['study'], r['stage']) == (study, stage)]
        index = {(r['policy'], r['alpha'], r['scenario'], r['partition'], r['seed']): r for r in rows}
        for metric in METRICS:
            cells = []
            for row in rows:
                if row['policy'] != treatment:
                    continue
                key = (control, row['alpha'], row['scenario'], row['partition'], row['seed'])
                other = index.get(key)
                if other is None:
                    raise RuntimeError('Missing paired control')
                if row[metric] is None or other[metric] is None:
                    continue
                cell = dict(study=study, stage=stage, treatment=treatment, control=control, metric=metric,
                            alpha=row['alpha'], scenario=row['scenario'], partition=row['partition'],
                            seed=row['seed'], difference=row[metric] - other[metric])
                paired.append(cell)
                cells.append(cell)
            if not cells:
                continue
            prefix = '/'.join([study, treatment + '-' + control, metric])
            result[prefix + '/all'] = cluster_summary(cells)
            for alpha in sorted({r['alpha'] for r in cells}, key=str):
                result[prefix + '/alpha=' + str(alpha)] = cluster_summary([r for r in cells if r['alpha'] == alpha])
    return result, paired


ROUND_FIELDS = ['study', 'experiment', 'stage', 'policy', 'alpha', 'partition', 'seed', 'scenario', 'round',
                'evaluationSplit', 'accuracy', 'macroF1', 'loss', 'trajectorySplit', 'proxyAccuracy', 'proxyMacroF1',
                'selectedIds', 'acceptedIds', 'feasibleCandidates', 'selectorMs', 'virtualRoundSeconds',
                'cumulativeVirtualSeconds', 'simulatedTrainingRoundSeconds', 'physicalRoundSeconds',
                'selectionGini', 'opportunityGini', 'feasibleSelectionCoverage', 'modelStateHash', 'scenarioTraceHash']


def audit_rounds(runs):
    index = {r['experiment']: r for r in runs}
    anomalies, studies, final_recalls, run_provenance = [], [], [], []
    counts = Counter()
    final_metrics = {}
    path = OUT / 'round-metrics.csv.gz'
    with path.open('wb') as raw, gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as compressed:
        with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, ROUND_FIELDS)
            writer.writeheader()
            for folder, study, expected_runs, expected_rounds in [(CONTROLLED, 'controlled-width-ablation', 227, 15754),
                                                                 (FUZZY, 'fuzzy-workflow', 167, 11554)]:
                configs, snapshots = {}, {}
                with gzip.open(folder / 'experiments.jsonl.gz', 'rt', encoding='utf-8') as inp:
                    for line in inp:
                        exp = json.loads(line)
                        if exp['status'] != 'COMPLETED':
                            anomalies.append('Non-completed experiment ' + exp['id'])
                        configs[exp['id']] = json.loads(exp['config'])
                        snapshots[exp['id']] = json.loads(exp['snapshot'])
                actual_rounds, audit_rounds, test_evaluations = 0, 0, 0
                for part in sorted(folder.glob('rounds-part-*.jsonl.gz')):
                    print('[ROUND AUDIT] ' + folder.name + '/' + part.name, flush=True)
                    with gzip.open(part, 'rt', encoding='utf-8') as inp:
                        for line in inp:
                            data = json.loads(line)
                            eid, rid = data['experiment_id'], data['round_id']
                            counts[eid] += 1
                            actual_rounds += 1
                            if rid != counts[eid] or data['outcome'] != 'COMMITTED':
                                anomalies.append('Duplicate/gap/uncommitted round ' + eid + ':' + str(rid))
                            m = json.loads(data['metrics'])
                            cfg = configs[eid]
                            summary = index.get(eid)
                            audit = summary is None
                            audit_rounds += int(audit)
                            stage = summary['stage'] if summary else 'AUDIT'
                            expected_split = 'test' if rid == cfg['rounds'] and stage in ('FULL', 'E3') else 'proxy'
                            if m['evaluationSplit'] != expected_split:
                                anomalies.append('Unexpected evaluation split ' + eid + ':' + str(rid))
                            test_evaluations += m['evaluationSplit'] == 'test'
                            if rid == cfg['rounds']:
                                final_metrics[eid] = m['evaluation']
                                for cls, recall in enumerate(m['evaluation']['perClassRecall']):
                                    final_recalls.append(dict(study=study, experiment=eid, stage=stage,
                                                              policy=summary['policy'] if summary else 'AUDIT',
                                                              evaluationSplit=m['evaluationSplit'], classIndex=cls, recall=recall))
                            selected, accepted = m.get('selectedIds', []), m.get('acceptedIds', [])
                            if len(selected) != len(set(selected)) or not set(accepted) <= set(selected):
                                anomalies.append('Invalid participant IDs ' + eid + ':' + str(rid))
                            ev = m['evaluation']
                            tr = m.get('trajectoryEvaluation') or ev
                            fairness = m.get('fairness') or {}
                            row = dict(study=study, experiment=eid, stage=stage,
                                       **({k: summary[k] for k in ('policy', 'alpha', 'partition', 'seed', 'scenario')} if summary else {}),
                                       round=rid, evaluationSplit=m['evaluationSplit'], accuracy=ev['accuracy'],
                                       macroF1=ev.get('macroF1'), loss=ev['loss'],
                                       trajectorySplit=m.get('trajectoryEvaluationSplit'), proxyAccuracy=tr['accuracy'], proxyMacroF1=tr.get('macroF1'),
                                       selectedIds=json.dumps(selected, separators=(',', ':')),
                                       acceptedIds=json.dumps(accepted, separators=(',', ':')),
                                       feasibleCandidates=m.get('feasibleCandidateCount'), selectorMs=m.get('selectorComputationMs'),
                                       virtualRoundSeconds=m.get('virtualRoundSeconds'), cumulativeVirtualSeconds=m.get('cumulativeVirtualSeconds'),
                                       simulatedTrainingRoundSeconds=m.get('simulatedTrainingRoundSeconds'), physicalRoundSeconds=m.get('wallClockSeconds'),
                                       selectionGini=fairness.get('selectionGini'), opportunityGini=fairness.get('feasibleOpportunityAdjustedGini'),
                                       feasibleSelectionCoverage=fairness.get('feasibleSelectionCoverage'), modelStateHash=m.get('modelStateHash'),
                                       scenarioTraceHash=m.get('scenarioTraceHash'))
                            writer.writerow(row)
                if len(configs) != expected_runs or actual_rounds != expected_rounds:
                    anomalies.append('Unexpected archive run/round count ' + study)
                for eid, cfg in configs.items():
                    if counts[eid] != cfg['rounds'] or snapshots[eid]['round'] != cfg['rounds']:
                        anomalies.append('Incomplete final snapshot ' + eid)
                    if eid in index:
                        for key in ('accuracy', 'macroF1', 'loss'):
                            if not math.isclose(final_metrics[eid][key], index[eid][key], abs_tol=1e-12):
                                anomalies.append('Summary/final evidence mismatch ' + eid + '/' + key)
                    snapshot = snapshots[eid]
                    run_provenance.append(dict(study=study, experiment=eid, audit=eid not in index,
                                               architecture=cfg['architecture'], rounds=cfg['rounds'],
                                               initializationSeed=snapshot.get('initializationSeed'),
                                               initialModelStateHash=snapshot.get('initialModelStateHash'),
                                               finalModelStateHash=final_metrics[eid].get('modelStateHash'),
                                               finalCheckpoint=snapshot['checkpointPath'],
                                               manifestHash=snapshot.get('manifest', {}).get('manifestHash'),
                                               scenarioTraceHash=snapshot.get('scenarioTraceHash'),
                                               uncertaintyMode=cfg['fuzzySelection']['uncertaintyMode']))
                studies.append(dict(study=study, experimentRows=len(configs), committedRounds=actual_rounds,
                                    auditRounds=audit_rounds, finalTestEvaluations=test_evaluations))
    csv_out('final-per-class-recall.csv', final_recalls)
    csv_out('run-provenance.csv', run_provenance)
    return dict(passed=not anomalies, anomalies=anomalies, streamedCommittedRounds=sum(s['committedRounds'] for s in studies), studies=studies)


def file_inventory():
    expected, inventory, anomalies = {}, [], []
    legacy = load(ROOT / 'results/archive-manifest.json')
    for archive in legacy['archives']:
        for part in archive['parts']:
            expected['results/' + part['path']] = part['sha256']
    for manifest in BASE.glob('*/publication-manifest.json'):
        for record in load(manifest)['files']:
            expected[(manifest.parent / record['path']).relative_to(ROOT).as_posix()] = record['sha256']
    for path in sorted((ROOT / 'results').rglob('*')):
        if not path.is_file() or path.is_relative_to(OUT):
            continue
        relative = path.relative_to(ROOT).as_posix()
        actual = sha(path)
        match = None if relative not in expected else actual == expected[relative]
        if match is False:
            anomalies.append(relative)
        inventory.append(dict(path=relative, bytes=path.stat().st_size, sha256=actual,
                              publicationManifestHashMatch=match,
                              contentType='compressed-binary-archive' if '/raw/' in relative else path.suffix))
    csv_out('published-file-inventory.csv', inventory)
    return dict(files=len(inventory), bytes=sum(r['bytes'] for r in inventory),
                filesWithPublicationHash=sum(r['publicationManifestHashMatch'] is not None for r in inventory),
                mismatches=anomalies, interpretation='Byte-level inventory; binaries are not interpreted as statistical observations')


def audit_pairing(runs):
    index = {r['experiment']: r for r in runs}
    identities, anomalies, clients, rows = {}, [], [], []
    for folder in (CONTROLLED, FUZZY):
        with gzip.open(folder / 'experiments.jsonl.gz', 'rt', encoding='utf-8') as inp:
            for line in inp:
                data = json.loads(line)
                row = index.get(data['id'])
                if not row:
                    continue
                snapshot = json.loads(data['snapshot'])
                hashes = snapshot['manifest']['hashes']
                value = (snapshot['initialModelStateHash'], hashes['partitions.npz'], hashes['splits.npz'], snapshot['scenarioTraceHash'])
                key = (row['study'], row['stage'], row['alpha'], row['partition'], row['seed'])
                if key in identities and identities[key] != value:
                    anomalies.append('Unpaired data/model/environment: ' + data['id'])
                identities[key] = value
                rows.append(dict(study=row['study'], experiment=row['experiment'], policy=row['policy'],
                                 initialModelStateHash=value[0], partitionHash=value[1], splitHash=value[2], scenarioTraceHash=value[3]))
                for client in snapshot['clients']:
                    clients.append(dict(study=row['study'], experiment=row['experiment'], policy=row['policy'],
                                        client=client['clientId'], selected=client['selectionCount'], completed=client['completionCount'],
                                        opportunities=client['opportunityCount'], feasibleOpportunities=client['feasibleOpportunityCount'],
                                        lastSelectedRound=client['lastSelectedRound'], lastCompletedRound=client['lastCompletedRound']))
    csv_out('paired-provenance.csv', rows)
    csv_out('client-participation.csv', clients)
    return dict(passed=not anomalies, anomalies=anomalies, checkedResearchRuns=len(rows), pairedConditionGroups=len(identities))


def audit_pareto(runs):
    data = load(PARETO / 'pareto-tradeoff-results.json')
    index = {r['experiment']: r for r in runs}
    anomalies, rows, recalls = [], [], []
    for trajectory in data['trajectories']:
        eid = trajectory['experimentId']
        summary = index[eid]
        if [r['roundId'] for r in trajectory['rounds']] != list(range(1, 71)):
            anomalies.append('Pareto round gap/duplicate: ' + eid)
        for m in trajectory['rounds']:
            ev, tr = m['evaluation'], m['trajectoryEvaluation']
            expected = 'test' if m['roundId'] == 70 else 'proxy'
            if ev['split'] != expected or tr['split'] != 'proxy':
                anomalies.append('Pareto split mismatch: ' + eid)
            rows.append(dict(study='fairness-pareto', experiment=eid, policy=summary['policy'],
                             partition=summary['partition'], seed=summary['seed'], round=m['roundId'],
                             evaluationSplit=ev['split'], accuracy=ev['accuracy'], macroF1=ev['macroF1'], loss=ev['loss'],
                             trajectorySplit=tr['split'], proxyAccuracy=tr['accuracy'], proxyMacroF1=tr['macroF1'],
                             selectionGini=m['fairness'].get('selectionGini'),
                             opportunityGini=m['fairness'].get('feasibleOpportunityAdjustedGini'),
                             feasibleSelectionCoverage=m['fairness'].get('feasibleSelectionCoverage'),
                             selectedIds=json.dumps(m['selectedIds']), acceptedIds=json.dumps(m['acceptedIds'])))
        ev = trajectory['rounds'][-1]['evaluation']
        for metric in ('accuracy', 'macroF1', 'loss'):
            if not math.isclose(ev[metric], summary[metric], abs_tol=1e-12):
                anomalies.append('Pareto summary/final mismatch: ' + eid)
        for cls, recall in enumerate(ev['perClassRecall']):
            recalls.append(dict(experiment=eid, policy=summary['policy'], partition=summary['partition'],
                                seed=summary['seed'], classIndex=cls, recall=recall, evaluationSplit='test'))
    csv_out('pareto-round-metrics.csv', rows)
    csv_out('pareto-per-class-recall.csv', recalls)
    return dict(passed=not anomalies, anomalies=anomalies, researchRuns=len(data['trajectories']), researchRounds=len(rows))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    runs = read_runs()
    csv_out('run-metrics.csv', runs)
    comparisons_result, pairs = comparisons(runs)
    csv_out('paired-effects.csv', pairs)
    partition_rows = []
    for key, result in comparisons_result.items():
        for partition, effect in result['partitionEffects'].items():
            partition_rows.append(dict(comparison=key, partition=partition, difference=effect,
                                       independentPartitions=result['independentPartitions']))
    csv_out('partition-effects.csv', partition_rows)
    groups = defaultdict(list)
    for row in runs:
        groups[(row['study'], row['stage'], row['policy'], row['alpha'], row['scenario'])].append(row)
    summaries = []
    for key, rows in groups.items():
        for metric in METRICS:
            summaries.append(dict(zip(('study', 'stage', 'policy', 'alpha', 'scenario'), key),
                                  metric=metric, **stats(r[metric] for r in rows)))
    csv_out('condition-summaries.csv', summaries)
    json_out('synthesis-data.json', dict(status='POST_HOC_DESCRIPTIVE_SYNTHESIS',
             researchRuns=len(runs), stageCounts={str(k): len(v) for k, v in groups.items()},
             comparisons=comparisons_result,
             caveats=['No cross-study causal pooling', 'Repeated seeds/alphas are clustered by partition',
                      'Three assignment clusters per completed main study', 'Reused fixed Covertype test examples',
                      'No completed324-run final robustness study', 'No inference from raw model weight values']))
    rounds = audit_rounds(runs)
    files = file_inventory()
    pairing, pareto = audit_pairing(runs), audit_pareto(runs)
    json_out('evidence-audit.json', dict(passed=rounds['passed'] and not files['mismatches'] and pairing['passed'] and pareto['passed'],
                                       rounds=rounds, publishedFiles=files, pairing=pairing, pareto=pareto))
    if not rounds['passed'] or files['mismatches'] or not pairing['passed'] or not pareto['passed']:
        raise RuntimeError('Evidence audit failed; inspect evidence-audit.json')
    print('[SYNTHESIS VERIFIED] researchRuns=' + str(len(runs)) + ' streamedRounds=' + str(rounds['streamedCommittedRounds']), flush=True)


if __name__ == '__main__':
    main()
