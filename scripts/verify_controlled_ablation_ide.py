"""Actual IDE Java main + independent manual Uvicorn; isolated synthetic full study."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid
import psutil
from fuzzy_uncertainty_workflow import ROOT, atomic
from resume_frozen_e3 import prevent_idle_sleep
from verify_fuzzy import free_port, get
from verify_fuzzy_recovery import stop_tree, wait_health
from verify_controlled_batch import verify


def main():
    folder=ROOT/'artifacts/controlled-ablation-ide-smoke'/uuid.uuid4().hex[:10];folder.mkdir(parents=True)
    config=json.loads((ROOT/'configurations/controlled-fuzzy-ablation-full.json').read_text())
    seed=2000000+int(folder.name[:6],16)
    config.update(dataset='synthetic',rounds=3,alphas=[.5],partitionSeeds=[seed],trainingSeeds=[42],
        confirmationDesign=dict(alphas=[.5],partitionSeeds=[seed],trainingSeeds=[42]),
        evidenceDatabases=[],replayStates=2,widthSensitivity=[0,.1,.3],minimumFreeDiskGB=.05,readinessSeconds=90,
        recoverySeconds=120,restartDelaySeconds=1)
    path=folder/'config.json';atomic(path,config)
    worker_port,java_port=free_port(),free_port();worker_base=f'http://127.0.0.1:{worker_port}';base=f'http://127.0.0.1:{java_port}'
    jar=ROOT/'ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar'
    env=dict(os.environ,PYTHONUTF8='1',MINIFLS_LOG_LEVEL='WARN')
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    worker=launcher=None;owned=[]
    def command(budget=0,url=worker_base,mode='run'):
        return ['java','-Xmx128m','-Dloader.main=com.huanphan.ferderatedsystem.ControlledAblationIdeLauncher','-cp',str(jar),
            'org.springframework.boot.loader.launch.PropertiesLauncher',f'--workspace={ROOT}',f'--config={path}',
            f'--output-root={folder/"research"}',f'--server-port={java_port}',f'--worker-url={url}',
            f'--mode={mode}','--stage=full',f'--run-budget={budget}','--round-budget=0']
    with (folder/'worker.log').open('w',encoding='utf-8') as wlog:
        try:
            worker=subprocess.Popen([sys.executable,'-m','uvicorn','minifls.api:app','--host','127.0.0.1','--port',str(worker_port)],cwd=ROOT,env=env,stdout=wlog,stderr=wlog,**flags)
            wait_health(worker_base,worker)
            with (folder/'hard-stop.log').open('w',encoding='utf-8') as log:
                launcher=subprocess.Popen(command(url=f'http://127.0.0.1:{free_port()}'),cwd=ROOT,env=env,stdout=log,stderr=log,**flags)
                deadline=time.monotonic()+150
                while True:
                    assert launcher.poll() is None,'IDE launcher exited before readiness probe'
                    try:get(base,'/experiments');break
                    except OSError:
                        assert time.monotonic()<deadline,'No API readiness during ownership probe'
                        time.sleep(.1)
                owned=psutil.Process(launcher.pid).children(recursive=True)
                launcher.kill();launcher.wait(timeout=15);launcher=None
                deadline=time.monotonic()+20
                while any(p.is_running() for p in owned):
                    assert time.monotonic()<deadline,'Hard IDE stop left a coordinator/controller alive'
                    time.sleep(.1)
            assert worker.poll() is None and get(worker_base,'/health')['status']=='ok'
            def phase(name,budget=0,mode='run'):
                nonlocal launcher
                with (folder/(name+'.log')).open('w',encoding='utf-8') as log:
                    launcher=subprocess.Popen(command(budget=budget,mode=mode),cwd=ROOT,env=env,stdout=log,stderr=log,**flags)
                    code=launcher.wait(timeout=300);launcher=None
                    assert code==0,f'{name}: IDE exit {code}; see {folder}'
                assert worker.poll() is None and get(worker_base,'/health')['status']=='ok','Manual worker was stopped'
            phase('budget',1)
            batch=Path(json.loads((folder/'research/active-batch.json').read_text())['folder'])
            assert json.loads((batch/'status.json').read_text())['workflowStatus']=='BUDGET_REACHED'
            phase('full')
            assert verify(batch)['status']=='PASS'
            manifest=json.loads((batch/'batch-manifest.json').read_text())
            assert {r['stage'] for r in manifest['runs'].values()}=={'AUDIT0','AUDIT1','FULL'}
            assert not (batch/'pilot-validation-lock.json').exists()
            assert not json.loads((batch/'full-policy-lock.json').read_text())['pilotExecutedForThisStudy']
            with sqlite3.connect(batch/'experiments.db') as db:count=db.execute('SELECT count(*) FROM rounds').fetchone()[0]
            assert count==19
            phase('reuse');phase('reports',mode='report-only')
            with sqlite3.connect(batch/'experiments.db') as db:assert count==db.execute('SELECT count(*) FROM rounds').fetchone()[0]
            atomic(folder/'summary.json',dict(status='PASS',batch=str(batch),syntheticRounds=count,
                checks=['real Java IDE main','manual Uvicorn remains alive','hard IDE stop child cleanup','full without pilot','unlimited resume','completed reuse','final-only test','checksum verification','reports without training']))
            print('Controlled full IDE smoke PASS:',folder,flush=True)
        finally:
            stop_tree(launcher);stop_tree(worker)
            for p in owned:
                try:
                    if p.is_running():p.kill()
                except psutil.NoSuchProcess:pass


if __name__=='__main__':
    with prevent_idle_sleep():main()
