"""Disk-streamed paired replay and partition-aware controlled ablation reports."""
from collections import defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics as stats

from scipy.stats import spearmanr, kendalltau, t
from fuzzy_uncertainty_workflow import ROOT, api, atomic, digest, immutable
from fuzzy_uncertainty_reports import CSV, summary


def paired_statistics(pairs):
    """Seeds/alphas repeat within a partition; CI unit is partition, never run."""
    values = [p["difference"] for p in pairs]
    groups = defaultdict(list)
    cells = defaultdict(list)
    for p in pairs:
        groups[p["partition"]].append(p["difference"])
        cells[(p["partition"], p["alpha"])].append(p["difference"])
    means = [stats.mean(v) for v in groups.values()]
    sd = stats.stdev(means) if len(means)>1 else None
    mean = stats.mean(means) if means else None
    ci = None
    if len(means)>=3:
        radius = float(t.ppf(.975, len(means)-1))*sd/math.sqrt(len(means))
        ci = [mean-radius, mean+radius]
    return dict(runPairs=len(values), meanPairedDifference=stats.mean(values) if values else None,
        medianPairedDifference=stats.median(values) if values else None, sampleSD=stats.stdev(values) if len(values)>1 else None,
        positive=sum(v>1e-12 for v in values), negative=sum(v< -1e-12 for v in values), tied=sum(abs(v)<=1e-12 for v in values),
        independentPartitions=len(means), partitionWeightedMean=mean, partitionMeanSampleSD=sd,
        exploratoryPartitionTInterval95=ci, standardizedPartitionEffect=mean/sd if sd and sd>0 else None,
        perPartition=[dict(partition=k, pairs=len(v), mean=stats.mean(v), sampleSD=stats.stdev(v) if len(v)>1 else None)
                      for k,v in sorted(groups.items())],
        perPartitionAlpha=[dict(partition=k[0], alpha=k[1], pairs=len(v), mean=stats.mean(v)) for k,v in sorted(cells.items())],
        interpretation="Descriptive; t interval assumes independent partition effects and is unstable at n=3. No seed-level significance test; no multiplicity-adjusted superiority claim.")


def ranking_comparison(a, b, k):
    ids = sorted(set(a["scores"]) & set(b["scores"]), key=int)
    x, y = [a["scores"][i] for i in ids], [b["scores"][i] for i in ids]
    defined = len(ids)>1 and len(set(x))>1 and len(set(y))>1
    aa, bb = set(a["ranking"][:k]), set(b["ranking"][:k])
    overlap = len(aa & bb)
    return dict(spearman=float(spearmanr(x,y).statistic) if defined else None,
        kendall=float(kendalltau(x,y).statistic) if defined else None,
        topKOverlap=overlap/min(len(aa),len(bb)) if aa and bb else None,
        jaccard=overlap/len(aa|bb) if aa|bb else None, changedSelected=len(bb-aa),
        meanAbsoluteScoreDifference=stats.mean(abs(u-v) for u,v in zip(x,y)) if ids else None,
        commonCandidates=len(ids), tiedScoresA=len(x)-len(set(x)), tiedScoresB=len(y)-len(set(y)))


def replay(study):
    from controlled_fuzzy_ablation import COMPARISONS, POLICIES
    folder = study.folder
    marker = folder / "offline-replay-identity.json"
    if marker.exists():
        saved = json.loads(marker.read_text())
        if saved["runtime"] != study.runtime or saved["protocolHash"] != digest(study.config):
            raise RuntimeError("Offline replay identity mismatch")
        for name, expected in saved["files"].items():
            with (folder/name).open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=expected:
                    raise RuntimeError("Offline replay artifact corrupted: "+name)
        return
    comparisons = CSV(folder, "offline-comparisons.csv", ["state", "source", "round", "treatment", "control", "spearman", "kendall", "topKOverlap", "jaccard", "changedSelected", "meanAbsoluteScoreDifference", "commonCandidates", "tiedScoresA", "tiedScoresB", "selectorMs"])
    widths = CSV(folder, "offline-widths.csv", ["state", "policy", "client", "criterion", "width", "lower", "middle", "upper", "score", "rank", "selected", "selectionCount", "timeHistory", "reliabilityHistory"])
    sensitivity = CSV(folder, "width-sensitivity.csv", ["state", "width", "spearman", "kendall", "topKOverlap", "jaccard", "changedSelected", "selectorMs"])
    sources = [ROOT/p for p in study.config["evidenceDatabases"]] or [folder/"experiments.db"]
    inputs_path = folder / "offline-inputs.jsonl"
    temp = inputs_path.with_suffix('.tmp')
    count = 0
    changes = {p:0 for p in ("A2", "A3", "A4")}
    width_samples = defaultdict(list)
    try:
        with temp.open('w',encoding='utf-8') as inputs:
            for database in sources:
                if not database.exists():
                    continue
                with sqlite3.connect(database.as_uri()+"?mode=ro",uri=True) as db:
                    total = db.execute('SELECT count(*) FROM rounds').fetchone()[0]
                    stride = max(1,total//study.config["replayStates"])
                    cursor = db.execute('SELECT e.config,r.metrics FROM rounds r JOIN experiments e ON e.id=r.experiment_id WHERE (r.rowid-1)%?=0 ORDER BY r.rowid LIMIT ?', (stride,study.config["replayStates"]-count))
                    for config_json, metrics_json in cursor:
                        c, m = json.loads(config_json), json.loads(metrics_json)
                        if "selectorInput" not in m:
                            continue
                        c["fuzzySelection"] = dict(study.config["widthSettings"], weights=study.config["weights"],
                            observationNoise=dict(scenario=study.config["scenario"], timing=study.config["timingUncertainty"], reliability=study.config["reliabilityUncertainty"]))
                        payload = dict(config=c, selectorInput=m["selectorInput"], round=m["roundId"])
                        state_id = digest(payload)
                        inputs.write(json.dumps(dict(state=state_id,source=database.relative_to(ROOT).as_posix(),**payload))+'\n')
                        result = api(study.base,"/research/controlled-replay",payload)
                        baseline = result["A1"]["observations"]
                        assert all(v["observations"]==baseline for v in result.values()), "Replay criteria differ"
                        profiles = {str(p["clientId"]):p for p in payload["selectorInput"]["eligibleClients"]}
                        for policy,r in result.items():
                            assert r["engine"] == ("CrispTopsisEngine" if policy=="A0" else "FuzzyTopsisEngine")
                            for client,columns in r["widths"].items():
                                p = profiles[client]
                                for j,(criterion,width) in enumerate(columns.items()):
                                    # Lookup by matrix criterion name, never JSON map iteration order.
                                    idx = next(i for i,v in enumerate(r["matrix"]["criteria"]) if v["name"]==criterion)
                                    cell = r["matrix"]["rows"][client][idx]
                                    if policy=="A1":
                                        assert width==0 and cell["lower"]==cell["middle"]==cell["upper"]
                                    widths.row(state=state_id,policy=policy,client=client,criterion=criterion,width=width,
                                        **cell,score=r['scores'][client],rank=r['ranking'].index(int(client))+1,selected=int(client) in r['ranking'][:c['selectedPerRound']],selectionCount=p["selectionCount"],timeHistory=len(p.get("timeResiduals",[])),reliabilityHistory=len(p.get("reliabilityResiduals",[])))
                                    width_samples[(policy,criterion)].append(width)
                        for treatment,control in COMPARISONS:
                            metrics=ranking_comparison(result[control],result[treatment],c["selectedPerRound"])
                            comparisons.row(state=state_id,source=database.relative_to(ROOT).as_posix(),round=m["roundId"],treatment=treatment,control=control,**metrics,selectorMs=result[treatment]["selectorMs"])
                            if control=="A1":changes[treatment]+=int(metrics["changedSelected"]>0)
                        for width in study.config["widthSensitivity"]:
                            altered=copy.deepcopy(payload);altered["config"]["fuzzySelection"]["uncertaintyFallback"]=width
                            rr=api(study.base,"/research/controlled-replay",altered)
                            sensitivity.row(state=state_id,width=width,**ranking_comparison(rr["A1"],rr["A2"],c["selectedPerRound"]),selectorMs=rr["A2"]["selectorMs"])
                        count+=1
                        if count%10==0: print(f"[OFFLINE] {count}/{study.config['replayStates']} immutable states",flush=True)
                        if count>=study.config["replayStates"]:break
                if count>=study.config["replayStates"]:break
            inputs.flush()
            import os
            os.fsync(inputs.fileno())
        temp.replace(inputs_path)
    finally:
        for stream in (comparisons,widths,sensitivity):stream.close()
    atomic(folder/'offline-summary.json',dict(status='COMPLETED' if count else 'INSUFFICIENT_EVIDENCE',states=count,
        changedSelectionStates=changes,changedSelectionFractions={p:v/count if count else None for p,v in changes.items()},
        widthDistributions={p+'/'+criterion:dict(**summary(values),median=stats.median(values),cappedFraction=sum(v>=.45 for v in values)/len(values)) for (p,criterion),values in sorted(width_samples.items())},
        interpretation='Paired offline decision diagnostic; no counterfactual training or FL outcome claim'))
    files={}
    for name in ('offline-inputs.jsonl','offline-comparisons.csv','offline-widths.csv','width-sensitivity.csv','offline-summary.json'):
        with (folder/name).open('rb') as f:files[name]=hashlib.file_digest(f,'sha256').hexdigest()
    immutable(marker,dict(protocolHash=digest(study.config),runtime=study.runtime,files=files))


def generate(study):
    from controlled_fuzzy_ablation import COMPARISONS
    folder=study.folder
    trajectory_columns=['experiment','stage','policy','alpha','partition','seed','round','accuracy','macroF1','loss','selectionGini','opportunityGini','virtualSeconds','physicalSeconds','selectorMs','selected','accepted','deadlineMisses']
    trajectory=CSV(folder,'trajectories.csv',trajectory_columns)
    recalls=CSV(folder,'per-class-recall.csv',['experiment','stage','policy','alpha','partition','seed','classId','recall','trainingSupport','minorityClass'])
    calibration=CSV(folder,'calibration-diagnostics.csv',['experiment','stage','alpha','partition','seed','policy','round','client','predictedTime','effectiveTime','physicalSeconds','timeRelativeError','signedTimeError','predictedAcceptance','accepted','brier','timeWidth','reliabilityWidth','timeHistory','reliabilityHistory','coldStart','widthCapped','timeIntervalCovered','acceptanceIntervalCovered'])
    runs=[];anomalies=[];paired={};calibration_bins=defaultdict(lambda:[0,0.,0.]);calibration_values=defaultdict(lambda:defaultdict(list))
    dbpath=folder/'experiments.db'
    try:
        if dbpath.exists():
            with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
                for run in study.state['runs'].values():
                    c=run['config'];eid=c['experimentId']
                    row=db.execute('SELECT status,snapshot,error FROM experiments WHERE id=?',(eid,)).fetchone()
                    if not row:continue
                    status,snapshot,error=row;snapshot=json.loads(snapshot) if snapshot else {}
                    accuracy=[];times=[];selector=[];physical=[];selected=accepted=misses=0;final=None;round_count=0;trace_hashes=[]
                    meta={k:run[k] for k in ('stage','policy','alpha','partition','seed')}
                    for (encoded,) in db.execute('SELECT metrics FROM rounds WHERE experiment_id=? ORDER BY round_id',(eid,)):
                        m=json.loads(encoded);round_count+=1
                        if m['roundId']!=round_count:anomalies.append(eid+': noncontiguous rounds')
                        expected='test' if run['stage'] in ('CONFIRMATION','FULL') and round_count==c['rounds'] else 'proxy'
                        if m['evaluationSplit']!=expected or m['trajectoryEvaluationSplit']!='proxy':anomalies.append(eid+': evaluation split violation')
                        ev=m['trajectoryEvaluation'];fair=m['fairness'];accuracy.append(ev['accuracy']);times.append(m['cumulativeVirtualSeconds']);selector.append(m['selectorComputationMs']);physical.append(m['wallClockSeconds'])
                        selected+=len(m['selectedIds']);accepted+=len(m['acceptedIds'])
                        deadlines=sum(p['status']=='TIMEOUT' for p in m['participants']);misses+=deadlines
                        trajectory.row(experiment=eid,**meta,round=m['roundId'],accuracy=ev['accuracy'],macroF1=ev['macroF1'],loss=ev['loss'],selectionGini=fair['selectionGini'],opportunityGini=fair['feasibleOpportunityAdjustedGini'],virtualSeconds=m['cumulativeVirtualSeconds'],physicalSeconds=sum(physical),selectorMs=m['selectorComputationMs'],selected=len(m['selectedIds']),accepted=len(m['acceptedIds']),deadlineMisses=deadlines)
                        trace_hashes.append(m['scenarioTraceHash'])
                        profiles={str(p['clientId']):p for p in m['selectorInput']['eligibleClients']}
                        widths=m.get('criterionUncertaintyWidths',{})
                        for p in m['participants']:
                            key=str(p['clientId']);pred=m['preRoundObservations'][key];profile=profiles[key];w=widths.get(key,{})
                            delta=abs(p['simulation']['virtualTrainingSeconds']-pred['estimatedTime'])/max(1e-9,pred['estimatedTime'])
                            u=w.get('estimatedTime');v=w.get('reliability');prob=pred['reliability'];outcome=int(p['accepted'])
                            covered=None if u is None else max(1e-9,pred['estimatedTime']*(1-u))<=p['simulation']['virtualTrainingSeconds']<=pred['estimatedTime']*(1+u)
                            acceptance_covered=None if v is None else max(0,prob-v)<=outcome<=min(1,prob+v)
                            signed=p['simulation']['virtualTrainingSeconds']-pred['estimatedTime']
                            if not run['stage'].startswith('AUDIT'):
                                bucket=calibration_bins[(run['policy'],run['alpha'],run['partition'],min(9,int(prob*10)))];bucket[0]+=1;bucket[1]+=prob;bucket[2]+=outcome
                                cv=calibration_values[run['policy']]
                                for field,value in dict(timeRelativeError=delta,signedTimeError=signed,brier=(outcome-prob)**2,timeWidth=u,reliabilityWidth=v,timeIntervalCovered=covered,acceptanceIntervalCovered=acceptance_covered).items():
                                    if value is not None:cv[field].append(value)
                            calibration.row(experiment=eid,**meta,round=m['roundId'],client=key,predictedTime=pred['estimatedTime'],effectiveTime=p['simulation']['virtualTrainingSeconds'],physicalSeconds=p['training']['actualTrainingMs']/1000,timeRelativeError=delta,signedTimeError=signed,predictedAcceptance=prob,accepted=outcome,brier=(outcome-prob)**2,timeWidth=u,reliabilityWidth=v,timeHistory=len(profile.get('timeResiduals',[])),reliabilityHistory=len(profile.get('reliabilityResiduals',[])),coldStart=len(profile.get('timeResiduals',[]))<5,widthCapped=any(v>=.45 for v in w.values()),timeIntervalCovered=covered,acceptanceIntervalCovered=acceptance_covered)
                        final=m
                    if status!='COMPLETED' or round_count!=c['rounds']:
                        anomalies.append(eid+': '+status+' '+str(error));continue
                    if snapshot.get('round')!=round_count:anomalies.append(eid+': snapshot round mismatch')
                    if run['stage'].startswith('AUDIT'):continue
                    ev=final['evaluation'];fair=final['fairness']
                    item=dict(experiment=eid,**meta,accuracy=ev['accuracy'],macroF1=ev['macroF1'],loss=ev['loss'],
                        tailAccuracySD=stats.stdev(accuracy[-10:]) if len(accuracy)>1 else None,
                        maximumAccuracyDrop=max((max(accuracy[:i])-accuracy[i] for i in range(1,len(accuracy))),default=0),
                        roundsToTarget=next((i for i,a in enumerate(accuracy,1) if a>=c['targetAccuracy']),None),
                        sustainedTargetAtEnd=all(a>=c['targetAccuracy'] for a in accuracy[next((i for i,a in enumerate(accuracy) if a>=c['targetAccuracy']),len(accuracy)):]) if any(a>=c['targetAccuracy'] for a in accuracy) else False,acceptedSelectedRatio=accepted/selected if selected else None,
                        completionRate=accepted/selected if selected else None,deadlineMisses=misses,virtualSeconds=times[-1],
                        physicalSeconds=sum(physical),selectorTotalMs=sum(selector),selectorMeanMs=stats.mean(selector),
                        selectionGini=fair['selectionGini'],opportunityGini=fair['feasibleOpportunityAdjustedGini'],
                        feasibleSelectionCoverage=fair['feasibleSelectionCoverage'],maxStaleness=fair['maxFeasibleSelectionStaleness'],
                        selectionFrequency={str(p['clientId']):p['selectionCount'] for p in snapshot['clients']},
                        initialHash=snapshot['initialModelStateHash'],scenarioTraceHashes=trace_hashes)
                    manifest_path=ROOT/c['manifestPath']/'manifest.json'
                    manifest=json.loads(manifest_path.read_text());parts=manifest['hashes']['partitions.npz']
                    item['partitionHash']=parts
                    pair_key=(run['alpha'],run['partition'],run['seed'],run['scenario'])
                    identity=(item['initialHash'],parts,trace_hashes)
                    if pair_key in paired and identity!=paired[pair_key]:anomalies.append(eid+': paired model/partition/trace mismatch')
                    paired[pair_key]=identity
                    # Minority classes defined using training assignments only, never test scores.
                    support=[sum(p['labelHistogram'][i] for p in manifest['clients']) for i in range(7)]
                    minority=set(sorted(range(7),key=lambda i:(support[i],i))[:2])
                    item['minorityRecall']=stats.mean(ev['perClassRecall'][i] for i in minority)
                    for i,value in enumerate(ev['perClassRecall']):recalls.row(experiment=eid,**meta,classId=i,recall=value,trainingSupport=support[i],minorityClass=i in minority)
                    runs.append(item)
    finally:
        for stream in (trajectory,recalls,calibration):stream.close()
    results_csv=CSV(folder,'run-results.csv',['experiment','stage','policy','alpha','partition','seed','accuracy','macroF1','loss','minorityRecall','tailAccuracySD','maximumAccuracyDrop','roundsToTarget','sustainedTargetAtEnd','acceptedSelectedRatio','completionRate','deadlineMisses','virtualSeconds','physicalSeconds','selectorMeanMs','selectionGini','opportunityGini','feasibleSelectionCoverage','maxStaleness'])
    for run in runs:results_csv.row(**run)
    results_csv.close()
    pairs=[];comparisons={}
    index={(r['alpha'],r['partition'],r['seed'],r['policy']):r for r in runs}
    for treatment,control in COMPARISONS:
        for metric in ('accuracy','macroF1','loss','minorityRecall','tailAccuracySD','maximumAccuracyDrop','virtualSeconds','physicalSeconds','selectorMeanMs','selectionGini','opportunityGini','completionRate'):
            sample=[]
            for key,r in index.items():
                if key[-1]!=treatment:continue
                baseline=index.get((*key[:-1],control))
                if baseline and r.get(metric) is not None and baseline.get(metric) is not None:
                    sample.append(dict(alpha=r['alpha'],partition=r['partition'],seed=r['seed'],difference=r[metric]-baseline[metric]))
            name=treatment+'-'+control
            comparisons[name+'/'+metric]=paired_statistics(sample)
            pairs.extend(dict(comparison=name,metric=metric,**v) for v in sample)
    pairs_csv=CSV(folder,'paired-differences.csv',['comparison','metric','alpha','partition','seed','difference'])
    for p in pairs:pairs_csv.row(**p)
    pairs_csv.close()
    expected=len(study.config['alphas'])*len(study.config['partitionSeeds'])*len(study.config['trainingSeeds'])*5
    integrity=dict(passed=not anomalies and len(runs)==expected,anomalies=anomalies,completedResearchRuns=len(runs),expectedResearchRuns=expected,
        checks=['unique contiguous round commits','final-only held-out evaluation','proxy-only trajectories/pilot','paired initial tensor/partition/scenario hashes'])
    calibration_report=dict(selectedOnly=True,coverageIsNotNominalConfidence=True,
        byPolicy={p:{field:summary(values) for field,values in fields.items()} for p,fields in calibration_values.items()},
        acceptanceBins=[dict(policy=p,alpha=a,partition=part,bin=b,n=v[0],predicted=v[1]/v[0],observed=v[2]/v[0]) for (p,a,part,b),v in sorted(calibration_bins.items())])
    result=dict(status='COMPLETED' if integrity['passed'] else 'INCOMPLETE',workflowStatus=study.state.get('progress',{}).get('workflowStatus'),protocol=study.config,integrity=integrity,runs=runs,comparisons=comparisons,calibration=calibration_report)
    atomic(folder/'controlled-ablation-results.json',result)
    atomic(folder/'integrity-report.json',integrity)
    lines=['# Controlled fuzzy uncertainty ablation','',f"Evidence status: {result['status']}. Completed research runs: {len(runs)}/{expected}.",'',
        'A1-A4 share the unchanged production fuzzy scoring engine. Only TFN widths vary. A0 is a formulation reference. Criteria/feasibility are identical on fixed replay states; end-to-end histories may diverge as a treatment effect.',
        '', '## Does Fuzzy Uncertainty Improve Federated Learning Client Selection?', '',
        'No conclusion is available until the complete paired evidence is examined. Completion alone is not evidence of superiority. Positive, negative and tied differences are reported below; pilot outcomes are exploratory proxy diagnostics.', '',
        '## Paired evidence (treatment minus control)', '', '| Contrast | Accuracy mean | Positive / negative / tied | Independent partitions |', '| --- | --- | --- | --- |']
    for treatment,control in COMPARISONS:
        name=treatment+'-'+control;r=comparisons[name+'/accuracy']
        lines.append(f"| {name} | {r['meanPairedDifference']} | {r['positive']} / {r['negative']} / {r['tied']} | {r['independentPartitions']} |")
    lines += ['', 'Primary: A2-A1, A3-A1, A4-A1. Secondary: A3-A2, A4-A3. A1-A0 is a formulation diagnostic, not an uncertainty effect.', '',
        '## Statistical and causal limits', '',
        'Seeds within a partition and alpha variants sharing its seed are clustered. Partition means, exploratory t intervals (only with >=3 partitions) and standardized partition effects are in JSON. Two/three independent assignments give weak uncertainty estimates; no p-values or superiority claims are generated. The fixed underlying test split has been inspected in prior research. Unseen client assignments do not imply a new untouched test dataset.', '',
        'Reliability target: accepted given selected and executed, including simulation dropout/deadline failures. Missing/unselected outcomes are not negatives. Calibrated widths use past selected-only residuals and cannot justify population calibration or nominal interval coverage. Virtual time and physical CPU/wall time remain separate.', '',
        '## Outputs and diagnostics', '',
        'See run-results.csv, trajectories.csv, paired-differences.csv, per-class-recall.csv, calibration-diagnostics.csv, offline-comparisons.csv, offline-widths.csv and width-sensitivity.csv. Minority recall is the mean recall of the two least frequent training classes. Maximum accuracy drop is the largest drawdown from any earlier proxy accuracy; tail SD uses the last ten proxy rounds. Offline rank correlations use average score ranks and Kendall tau-b with tie handling; undefined correlations are null. Top-K uses production ID tie breaks.', '',
        'Selection-frequency distributions, feasible coverage, opportunity-adjusted Gini, staleness, accepted/selected ratio, deadline misses and physical/virtual efficiency are retained in JSON/CSV. Completion rate and accepted/selected ratio coincide under the audited selected/executed target.', '',
        '## Failure and integrity report', '',json.dumps(integrity,indent=2), '',
        '## Provenance', '', 'protocol.json, source-identity.json, build-identity.json, runtime-identity.json, partition-reservation.json, reproducibility-audit.json, completed-artifact-identities/ and the policy/confirmation lock retain executing identities. This directory is separate from all previous results.', '']
    if study.config['studyStage']=='full':
        lines.insert(4,'Execution design: full predeclared ablation without the separate Covertype pilot, at user request. All five policies/parameters were fixed before execution; this is not pilot-validated confirmation. See full-policy-lock.json.\n')
    if integrity['passed']:
        answer=[]
        for treatment in ('A2','A3','A4'):
            r=comparisons[treatment+'-A1/accuracy']
            effect=r['meanPairedDifference']
            direction='higher' if effect>1e-12 else 'lower' if effect< -1e-12 else 'tied'
            signs=[v['mean'] for v in r['perPartition']]
            consistency='same direction across recorded partitions' if all(v>1e-12 for v in signs) or all(v< -1e-12 for v in signs) else 'mixed or tied partition effects'
            answer.append(f"{treatment} had {direction} mean final accuracy than A1 (difference {effect:+.6f}; {consistency}).")
        answer.append('These are observed paired effects under this protocol, not a claim of statistical superiority or universal benefit. See Macro-F1, stability, efficiency and partition uncertainty before drawing a research conclusion.')
        lines[lines.index('No conclusion is available until the complete paired evidence is examined. Completion alone is not evidence of superiority. Positive, negative and tied differences are reported below; pilot outcomes are exploratory proxy diagnostics.')]=' '.join(answer)
    atomic(folder/'controlled-fuzzy-ablation-report.md','\n'.join(lines))
    from controlled_ablation_plots import generate_plots
    generate_plots(folder)
    return result
