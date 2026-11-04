"""Read-only persisted-evidence verification; no training or worker required."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from fuzzy_uncertainty_workflow import ROOT, digest, contains
from resume_frozen_e3 import verify_frozen_files


def file_hash(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def verify(folder):
    folder=Path(folder).resolve()
    verify_frozen_files(folder)
    state=json.loads((folder/'batch-manifest.json').read_text())
    result=json.loads((folder/'integrity-report.json').read_text())
    if not result['passed']:raise RuntimeError('Study is incomplete or integrity report failed')
    runtime=json.loads((folder/'runtime-identity.json').read_text())
    with sqlite3.connect((folder/'experiments.db').as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN')
        for run in state['runs'].values():
            c=run['config'];eid=c['experimentId']
            row=db.execute('SELECT status,config,snapshot FROM experiments WHERE id=?',(eid,)).fetchone()
            if not row or row[0]!='COMPLETED' or not contains(json.loads(row[1]),c):raise RuntimeError('Missing/incompatible completed run: '+eid)
            if c['provenance']['runtimeIdentity']!=runtime:raise RuntimeError('Runtime mismatch: '+eid)
            snapshot=json.loads(row[2]);n,lo,hi=db.execute('SELECT count(*),min(round_id),max(round_id) FROM rounds WHERE experiment_id=?',(eid,)).fetchone()
            if n!=c['rounds'] or lo!=1 or hi!=n or snapshot['round']!=n:raise RuntimeError('Round continuity mismatch: '+eid)
            identity=json.loads((folder/'completed-artifact-identities'/(eid+'.json')).read_text())
            checkpoint=(ROOT/snapshot['checkpointPath']).resolve()
            if not checkpoint.is_relative_to(ROOT):raise RuntimeError('Checkpoint escapes workspace')
            receipt=checkpoint.with_suffix('.response.json')
            if identity['configHash']!=digest(c) or file_hash(checkpoint)!=identity['checkpointSHA256'] or file_hash(receipt)!=identity['receiptSHA256']:
                raise RuntimeError('Checkpoint/receipt integrity mismatch: '+eid)
            for round_id,encoded in db.execute('SELECT round_id,metrics FROM rounds WHERE experiment_id=? ORDER BY round_id',(eid,)):
                m=json.loads(encoded)
                expected='test' if run['stage'] in ('CONFIRMATION','FULL') and round_id==n else 'proxy'
                if m['evaluationSplit']!=expected or m['trajectoryEvaluationSplit']!='proxy':raise RuntimeError('Evaluation split violation: '+eid)
    marker=json.loads((folder/'offline-replay-identity.json').read_text())
    for name,expected in marker['files'].items():
        if file_hash(folder/name)!=expected:raise RuntimeError('Offline evidence checksum mismatch: '+name)
    return dict(status='PASS',completedResearchRuns=result['completedResearchRuns'],expectedResearchRuns=result['expectedResearchRuns'],checkedRuns=len(state['runs']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    print(json.dumps(verify(parser.parse_args().folder),indent=2))
