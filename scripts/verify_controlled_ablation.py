"""Real Java/PyTorch controlled study smoke, private ports/data/SQLite only."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

import psutil
from fuzzy_uncertainty_workflow import digest
from verify_fuzzy import free_port
from verify_fuzzy_recovery import stop_tree

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'artifacts/controlled-ablation-smoke'/uuid.uuid4().hex[:10];folder.mkdir(parents=True)
    pilot=json.loads((ROOT/'configurations/controlled-fuzzy-ablation-pilot.json').read_text())
    pilot_seed=1000000+int(folder.name[:6],16)*2
    confirmation_seed=pilot_seed+1
    design=dict(alphas=[.5],partitionSeeds=[confirmation_seed],trainingSeeds=[42])
    pilot.update(dataset='synthetic',rounds=3,alphas=[.5],partitionSeeds=[pilot_seed],otherStagePartitions=[confirmation_seed],
        trainingSeeds=[42],evidenceDatabases=[],replayStates=2,widthSensitivity=[0,.1,.3],minimumFreeDiskGB=.05,
        readinessSeconds=90,recoverySeconds=120,restartDelaySeconds=1,runBudget=0,roundBudget=0,confirmationDesign=design)
    full=copy.deepcopy(pilot);full.update(studyStage='confirmation',mode='full',partitionSeeds=[confirmation_seed],otherStagePartitions=[pilot_seed],
        pilotPointer=(folder/'pilot/active-batch.json').relative_to(ROOT).as_posix())
    for name,c in [('pilot',pilot),('confirmation',full)]:(folder/(name+'.json')).write_text(json.dumps(c))
    old=ROOT/'results/research/fuzzy-uncertainty-20261031-004757-b6b730-full-20261103/publication-manifest.json'
    old_hash=hashlib.sha256(old.read_bytes()).hexdigest()
    java_port,worker_port=free_port(),free_port()
    def phase(name,stage='pilot',mode=None,budget=0,inject=False,expect=0):
        env=dict(os.environ,MINIFLS_STUDY='controlled-fuzzy-ablation',MINIFLS_FUZZY_CONFIG=str(folder/(stage+'.json')),
            MINIFLS_FUZZY_OUTPUT=str(folder/stage),MINIFLS_FUZZY_MODE=mode or ('pilot' if stage=='pilot' else 'full'),
            MINIFLS_SERVER_PORT=str(java_port),MINIFLS_WORKER_URL=f'http://127.0.0.1:{worker_port}',
            MINIFLS_FUZZY_RUN_BUDGET=str(budget),MINIFLS_FUZZY_ROUND_BUDGET='0',
            MINIFLS_ABLATION_ACCEPT_CONFIRMATION='1',PYTHONUTF8='1',MINIFLS_LOG_LEVEL='WARN')
        flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        processes=[];logs=[];killed=False
        try:
            roles=['java'] if mode in ('preflight','report-only') else ['worker','java']
            for role in roles:
                stream=(folder/(name+'-'+role+'.log')).open('w',encoding='utf-8');logs.append(stream)
                processes.append(subprocess.Popen([sys.executable,'-u','scripts/research_watchdog.py',role],cwd=ROOT,env=env,stdout=stream,stderr=stream,**flags))
            deadline=time.monotonic()+600
            while processes[-1].poll() is None:
                if time.monotonic()>deadline:raise TimeoutError(f'{name}: {folder}')
                if inject and not killed:
                    pointer=folder/stage/'active-batch.json'
                    if pointer.exists():
                        batch=Path(json.loads(pointer.read_text())['folder']);dbpath=batch/'experiments.db'
                        if dbpath.exists():
                            with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
                                tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                                partial=db.execute("SELECT id FROM experiments WHERE status='RUNNING' AND json_extract(snapshot,'$.round')>=1 AND json_extract(snapshot,'$.round')<json_extract(config,'$.rounds')").fetchall() if 'experiments' in tables else []
                            if partial:
                                candidates=[p for p in psutil.Process(processes[-1].pid).children(recursive=True) if p.name().lower() in ('java','java.exe') and 'coordinator.jar' in ' '.join(p.cmdline())]
                                if candidates:candidates[0].kill();killed=True
                time.sleep(.02 if inject else .2)
            assert processes[-1].returncode==expect,f'{name}: exit={processes[-1].returncode}; {folder}'
            if len(processes)>1:
                processes[0].wait(timeout=45);assert processes[0].returncode==expect
            if inject:assert killed,'No partial round reached for Java crash injection'
        finally:
            for p in reversed(processes):
                if p.poll() is None:stop_tree(p)
            for f in logs:f.close()
        pointer=folder/stage/'active-batch.json'
        return Path(json.loads(pointer.read_text())['folder'])

    p=phase('preflight',mode='preflight')
    assert not (p/'experiments.db').exists() or sqlite3.connect(p/'experiments.db').execute('SELECT count(*) FROM experiments').fetchone()[0]==0
    phase('audit-budget',budget=1)
    assert json.loads((p/'status.json').read_text())['workflowStatus']=='BUDGET_REACHED'
    phase('pilot',inject=True)
    assert json.loads((p/'completion.json').read_text())['status']=='COMPLETED'
    assert json.loads((p/'integrity-report.json').read_text())['passed']
    lock=(p/'pilot-validation-lock.json').read_bytes()
    with sqlite3.connect(p/'experiments.db') as db:before=db.execute('SELECT count(*) FROM rounds').fetchone()[0]
    phase('reuse')
    with sqlite3.connect(p/'experiments.db') as db:assert before==db.execute('SELECT count(*) FROM rounds').fetchone()[0]
    assert (p/'pilot-validation-lock.json').read_bytes()==lock
    phase('reports',mode='report-only')
    q=phase('confirmation','confirmation',budget=100)
    assert json.loads((q/'integrity-report.json').read_text())['passed']
    from verify_controlled_batch import verify
    assert verify(p)['status']=='PASS' and verify(q)['status']=='PASS'
    with sqlite3.connect(p/'experiments.db') as db:
        checkpoint=ROOT/json.loads(db.execute('SELECT snapshot FROM experiments LIMIT 1').fetchone()[0])['checkpointPath']
    original_checkpoint=checkpoint.read_bytes()
    checkpoint.write_bytes(original_checkpoint+b'corrupt-test-only')
    try:
        try:verify(p)
        except RuntimeError as error:assert 'Checkpoint/receipt integrity mismatch' in str(error)
        else:raise AssertionError('Corrupted completed checkpoint was accepted')
    finally:checkpoint.write_bytes(original_checkpoint)
    # Fail closed on an incompatible executing source, using an isolated copied ledger.
    identity=p/'source-identity.json';original=identity.read_bytes();v=json.loads(original);v['scripts/controlled_fuzzy_ablation.py']='0'*64
    identity.write_text(json.dumps(v))
    try:phase('incompatible-source',mode='preflight',expect=20)
    finally:identity.write_bytes(original)
    total=0
    for batch in (p,q):
        with sqlite3.connect(batch/'experiments.db') as db:
            assert db.execute("SELECT count(*) FROM experiments WHERE status!='COMPLETED'").fetchone()[0]==0
            assert db.execute('SELECT count(*) FROM (SELECT experiment_id,round_id,count(*) n FROM rounds GROUP BY experiment_id,round_id HAVING n!=1)').fetchone()[0]==0
            total+=db.execute('SELECT count(*) FROM rounds').fetchone()[0]
        assert len(list((batch/'figures').glob('*.png')))==10
    assert total==38
    for batch in (p,q):
        with (batch/'calibration-diagnostics.csv').open() as stream:
            cohorts={r['stage'] for r in csv.DictReader(stream)}
        assert cohorts & {'AUDIT0','AUDIT1'} and cohorts & {'PILOT','CONFIRMATION'}
        replay_summary=json.loads((batch/'offline-summary.json').read_text())
        assert replay_summary['widthDistributions']['A1/estimatedTime']['maximum']==0
    assert hashlib.sha256(old.read_bytes()).hexdigest()==old_hash
    (folder/'summary.json').write_text(json.dumps(dict(status='PASS',pilot=str(p),confirmation=str(q),committedSyntheticRounds=total,
        checks=['preflight without training','admission budget/resume','Java crash and interrupted round recovery','completed reuse','source mismatch rejection','paired initialization/partition/traces','final-only test','five policies','offline widths','ten plots','old publication unchanged']),indent=2))
    print('Controlled ablation smoke PASS:',folder,flush=True)


if __name__=='__main__':
    from resume_frozen_e3 import prevent_idle_sleep
    with prevent_idle_sleep():main()
