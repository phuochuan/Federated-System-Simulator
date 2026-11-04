import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

sys.path.insert(0,str(Path(__file__).parent))
import controlled_fuzzy_ablation as workflow
from controlled_ablation_reports import paired_statistics, ranking_comparison, generate
REPOSITORY = workflow.ROOT


def config():
    return json.loads((REPOSITORY/'configurations/controlled-fuzzy-ablation-pilot.json').read_text())


def test_protocol_and_counts():
    c=config();workflow.validate_protocol(c)
    assert len(c['policies'])*len(c['alphas'])*len(c['partitionSeeds'])*len(c['trainingSeeds'])==40
    full=json.loads((workflow.ROOT/'configurations/controlled-fuzzy-ablation-confirmation.json').read_text())
    workflow.validate_protocol(full)
    assert 5*len(full['alphas'])*len(full['partitionSeeds'])*len(full['trainingSeeds'])==225
    assert not set(c['partitionSeeds']) & set(full['partitionSeeds'])
    direct=json.loads((REPOSITORY/'configurations/controlled-fuzzy-ablation-full.json').read_text())
    workflow.validate_protocol(direct)
    assert direct['studyStage']=='full' and direct['runBudget']==direct['roundBudget']==0
    assert 'pilotPointer' not in direct and len(direct['policies'])*len(direct['alphas'])*len(direct['partitionSeeds'])*len(direct['trainingSeeds'])==225
    for mutate in (lambda v:v.update(weights={'estimatedTime':1}),lambda v:v.update(otherStagePartitions=[5001]),lambda v:v.update(runBudget=-1)):
        changed=copy.deepcopy(c);mutate(changed)
        with pytest.raises(ValueError):workflow.validate_protocol(changed)


def test_partition_cluster_statistics_do_not_count_seed_repeats_as_partitions():
    pairs=[dict(partition=p,alpha=a,seed=s,difference=p/100) for p in (1,2,3) for a in (.1,.5,1) for s in range(5)]
    r=paired_statistics(pairs)
    assert r['runPairs']==45 and r['independentPartitions']==3
    assert r['partitionWeightedMean']==pytest.approx(.02)
    assert r['standardizedPartitionEffect']==pytest.approx(2)
    assert r['exploratoryPartitionTInterval95'] is not None
    assert paired_statistics(pairs[:15])['exploratoryPartitionTInterval95'] is None
    assert paired_statistics([])['meanPairedDifference'] is None


def test_correlations_and_set_metrics_with_score_ties():
    a=dict(scores={'1':.5,'2':.5,'3':.2},ranking=[1,2,3])
    b=dict(scores={'1':.2,'2':.5,'3':.5},ranking=[2,3,1])
    r=ranking_comparison(a,b,2)
    assert r['spearman']==pytest.approx(-.5)
    assert r['kendall']==pytest.approx(-.5)
    assert r['topKOverlap']==.5 and r['jaccard']==pytest.approx(1/3)
    assert r['changedSelected']==1
    assert ranking_comparison(dict(scores={'1':1},ranking=[1]),dict(scores={'1':1},ranking=[1]),5)['spearman'] is None


def test_inventory_detects_previously_used_partitions(tmp_path,monkeypatch):
    monkeypatch.setattr(workflow,'ROOT',tmp_path)
    p=tmp_path/'results/old/manifest.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'partitionSeed':5001}))
    report=workflow.partition_inventory(config(),tmp_path/'artifacts/new')
    assert report['conflicts']==[5001]
    p.write_text(json.dumps({'partitionSeed':42,'confirmationDesign':{'partitionSeeds':[5001,5002]}}))
    assert workflow.partition_inventory(config(),tmp_path/'artifacts/new')['conflicts']==[]


def test_reports_explicitly_mark_no_evidence_and_generate_all_figures(tmp_path):
    study=SimpleNamespace(folder=tmp_path,state={'runs':{},'progress':{'workflowStatus':'BLOCKED'}},config=config())
    result=generate(study)
    assert result['status']=='INCOMPLETE' and not result['integrity']['passed']
    assert len(list((tmp_path/'figures').glob('*.png')))==10
    assert 'Does Fuzzy Uncertainty Improve Federated Learning Client Selection?' in (tmp_path/'controlled-fuzzy-ablation-report.md').read_text()


def test_confirmation_rejects_missing_pilot_and_no_acceptance(tmp_path,monkeypatch):
    monkeypatch.setattr(workflow,'ROOT',tmp_path)
    study=workflow.ControlledStudy.__new__(workflow.ControlledStudy);study.config=config()
    study.config.update(pilotPointer='pilot.json',studyStage='confirmation')
    with pytest.raises(FileNotFoundError):study.confirmation_gate()


def test_confirmation_requires_unchanged_pilot_lock_acceptance_and_budget(tmp_path,monkeypatch):
    c=json.loads((REPOSITORY/'configurations/controlled-fuzzy-ablation-confirmation.json').read_text())
    monkeypatch.setattr(workflow,'ROOT',tmp_path)
    study=workflow.ControlledStudy.__new__(workflow.ControlledStudy);study.config=c;study.folder=tmp_path/'confirmation';study.folder.mkdir()
    study.runtime={'build':'same'}
    (study.folder/'source-identity.json').write_text('{}')
    pilot=tmp_path/'pilot';pilot.mkdir()
    pointer=tmp_path/c['pilotPointer'];pointer.parent.mkdir(parents=True);pointer.write_text(json.dumps({'folder':str(pilot)}))
    (pilot/'completion.json').write_text(json.dumps({'status':'COMPLETED'}))
    lock=dict(protocolVersion=c['protocolVersion'],integrity={'passed':True},policies=c['policies'],scientificControls=workflow.scientific_controls(c),runtime=study.runtime,
        sourceIdentityHash=workflow.digest({}),confirmationDesign=dict(alphas=c['alphas'],partitionSeeds=c['partitionSeeds'],trainingSeeds=c['trainingSeeds']),
        confirmationPartitions=c['partitionSeeds'],widthSettings=c['widthSettings'],weights=c['weights'])
    (pilot/'pilot-validation-lock.json').write_text(json.dumps(lock))
    monkeypatch.delenv('MINIFLS_ABLATION_ACCEPT_CONFIRMATION',raising=False)
    with pytest.raises(RuntimeError,match='explicit acceptance'):study.confirmation_gate()
    monkeypatch.setenv('MINIFLS_ABLATION_ACCEPT_CONFIRMATION','1')
    monkeypatch.setenv('MINIFLS_FUZZY_RUN_BUDGET','0');monkeypatch.setenv('MINIFLS_FUZZY_ROUND_BUDGET','0')
    with pytest.raises(RuntimeError,match='positive run or round'):study.confirmation_gate()
    monkeypatch.setenv('MINIFLS_FUZZY_RUN_BUDGET','1');study.confirmation_gate()
    study.runtime={'build':'changed'}
    with pytest.raises(RuntimeError,match='scientific controls/source/runtime'):study.confirmation_gate()


def test_direct_full_lock_does_not_claim_pilot_validation(tmp_path):
    c=json.loads((REPOSITORY/'configurations/controlled-fuzzy-ablation-full.json').read_text())
    study=workflow.ControlledStudy.__new__(workflow.ControlledStudy)
    study.config=c;study.folder=tmp_path;study.runtime={'build':'fixed'}
    study.full_policy_lock()
    lock=json.loads((tmp_path/'full-policy-lock.json').read_text())
    assert not lock['pilotExecutedForThisStudy'] and lock['policies']==list(workflow.POLICIES)
    c['trainingSeeds']=[42]
    with pytest.raises(RuntimeError,match='predefined full design'):study.full_policy_lock()


def test_measured_full_disk_estimate_fits_40_gib_and_keeps_reserve(tmp_path,monkeypatch):
    c=json.loads((REPOSITORY/'configurations/controlled-fuzzy-ablation-full.json').read_text())
    c['evidenceDatabases']=[]
    s=workflow.ControlledStudy.__new__(workflow.ControlledStudy);s.config=c;s.folder=tmp_path
    (tmp_path/'partition-reservation.json').write_text('{"conflicts":[]}')
    monkeypatch.delenv('MINIFLS_FUZZY_RUN_BUDGET',raising=False);monkeypatch.delenv('MINIFLS_FUZZY_ROUND_BUDGET',raising=False)
    monkeypatch.setattr(workflow.shutil,'disk_usage',lambda _:SimpleNamespace(free=40*1024**3))
    r=s.preflight()
    assert r['runs']==225 and r['maximumAdmittedResearchRuns']==225
    assert 39<r['admissionEstimatedDiskGiB']<40
    assert r['storageBounds']['protectedFreeReserveGiB']==8
    assert r['storageBounds']['checkpointAndReceiptBytes']>1.5*197519
    assert r['storageBounds']['roundSQLiteEvidenceBytes']>1.38*159164
    monkeypatch.setattr(workflow.shutil,'disk_usage',lambda _:SimpleNamespace(free=38*1024**3))
    low=s.preflight()
    assert low['freeDiskGiB']<low['admissionEstimatedDiskGiB']
