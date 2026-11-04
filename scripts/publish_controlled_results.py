"""Publish completed controlled-study evidence without altering its local batch.

Stream SQLite rows into small gzip parts. Keep datasets/checkpoints/SQLite local;
copy the executing source bytes as well as human-readable reports and figures.
"""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from fuzzy_uncertainty_workflow import ROOT, atomic
from resume_frozen_e3 import verify_frozen_files


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def publish(batch,destination):
    batch,destination=Path(batch).resolve(),Path(destination).resolve()
    if not batch.is_relative_to(ROOT/'artifacts/research') or not destination.is_relative_to(ROOT/'results/research'):
        raise ValueError('Use workspace research artifacts/results directories')
    if destination.exists():raise FileExistsError('Publication already exists; preserve the original snapshot')
    completion=json.loads((batch/'completion.json').read_text())
    integrity=json.loads((batch/'integrity-report.json').read_text())
    state=json.loads((batch/'batch-manifest.json').read_text())
    if completion.get('status')!='COMPLETED' or not integrity['passed'] or any(r['status']!='COMPLETED' for r in state['runs'].values()):
        raise RuntimeError('Publish only completed, verified batches')
    verify_frozen_files(batch)
    sources=[p for p in batch.iterdir() if p.is_file() and p.suffix in ('.json','.csv','.md','.jsonl')]
    for directory in ('traces','dataset-identities','completed-artifact-identities','initial-model-identities','partitions'):
        sources.extend((batch/directory).rglob('*.json'))
    sources.extend(p for p in (batch/'figures').rglob('*') if p.is_file() and p.suffix in ('.png','.svg'))
    sources=sorted(set(sources));original_hashes={p:sha256(p) for p in sources}
    destination.mkdir(parents=True)
    records=[]

    def record(target,source=None,**fields):
        if target.stat().st_size>=95*1024**2:raise RuntimeError('Export part too large for normal Git: '+str(target))
        item=dict(path=target.relative_to(destination).as_posix(),bytes=target.stat().st_size,sha256=sha256(target),**fields)
        if source is not None:item.update(sourcePath=source.relative_to(ROOT).as_posix(),sourceSHA256=sha256(source))
        records.append(item)

    for source in sources:
        relative=source.relative_to(batch)
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if source.stat().st_size>40*1024**2:
            target=target.with_name(target.name+'.gz')
            with source.open('rb') as inp,target.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as out:
                shutil.copyfileobj(inp,out,1024*1024)
            with gzip.open(target,'rb') as inp:
                if hashlib.file_digest(inp,'sha256').hexdigest()!=original_hashes[source]:raise RuntimeError('Gzip byte mismatch')
            record(target,source,compression='gzip')
        else:
            shutil.copy2(source,target)
            if sha256(target)!=original_hashes[source]:raise RuntimeError('Copied evidence mismatch')
            record(target,source)

    # Results paths disable Git newline conversion, preserving exact executing bytes.
    ledger=json.loads((batch/'source-identity.json').read_text())
    for relative,expected in ledger.items():
        source=(ROOT/relative).resolve()
        if not source.is_relative_to(ROOT) or sha256(source)!=expected:raise RuntimeError('Executing source changed: '+relative)
        target=destination/'source-snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);record(target,source)

    dbpath=batch/'experiments.db'
    with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;db.execute('BEGIN')
        experiment_count=db.execute('SELECT count(*) FROM experiments').fetchone()[0]
        round_count=db.execute('SELECT count(*) FROM rounds').fetchone()[0]
        if db.execute("SELECT count(*) FROM experiments WHERE status!='COMPLETED'").fetchone()[0]:raise RuntimeError('Noncompleted database rows')
        if experiment_count!=len(state['runs']):raise RuntimeError('Manifest/database count mismatch')
        if round_count!=sum(r['config']['rounds'] for r in state['runs'].values()):raise RuntimeError('Committed-round count mismatch')

        def export(name,rows):
            target=destination/name;count=0
            with target.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as out:
                for row in rows:
                    out.write((json.dumps(dict(row),separators=(',',':'),allow_nan=False)+'\n').encode());count+=1
            with gzip.open(target,'rt',encoding='utf-8') as inp:
                restored=sum(1 for line in inp if json.loads(line))
            if restored!=count:raise RuntimeError('JSONL verification count mismatch')
            record(target,records=count,compression='gzip',sourcePath=dbpath.relative_to(ROOT).as_posix())
            print(f'Verified {name}: {count} records, {target.stat().st_size/1024**2:.1f} MiB',flush=True)
        export('experiments.jsonl.gz',db.execute('SELECT * FROM experiments ORDER BY id'))
        cursor=db.execute('SELECT * FROM rounds ORDER BY experiment_id,round_id');part=0
        while rows:=cursor.fetchmany(1000):
            part+=1;export(f'rounds-part-{part:03d}.jsonl.gz',rows)

    for source,expected in original_hashes.items():
        if sha256(source)!=expected:raise RuntimeError('Source changed during publication: '+str(source))
    research_count=integrity['completedResearchRuns']
    text=f'''# Completed controlled fuzzy uncertainty ablation

Completed 4 November 2026: **{research_count} research runs x 70 rounds**, plus two
2-round reproducibility audits: **{experiment_count} runs / {round_count} committed rounds**.
All five policies A0-A4 were retained across alpha 0.1/0.5/1.0, independent client
assignment seeds 6001/6002/6003 and paired training seeds 42-46 under U0.

- [Research report](controlled-fuzzy-ablation-report.md)
- [Results and partition-aware paired differences](controlled-ablation-results.json)
- [Run results CSV](run-results.csv) and [paired differences CSV](paired-differences.csv)
- [Figures](figures/accuracy-rounds.png)
- [Protocol](protocol.json), [full policy lock](full-policy-lock.json)
- [Integrity report](integrity-report.json) and [completion marker](completion.json)
- [Publication checksums](publication-manifest.json)

This was the user-requested full predeclared study without the separate 40-run
Covertype pilot. It is not labeled pilot-validated confirmation. Final held-out
evaluation occurs only at the last round; trajectories use proxy data. The fixed
underlying test examples had been inspected in prior research. Seeds within one
partition are repeated measurements, not independent partition replications.

A1 zero-width fuzzy is the primary control for A2/A3/A4. A0 conventional Crisp
is a formulation reference. Results retain positive, negative and tied effects;
workflow completion alone does not establish superiority.

`experiments.jsonl.gz` preserves all SQLite experiment rows, including config and
snapshot JSON strings. `rounds-part-*.jsonl.gz` preserves all committed round rows,
at most 1,000 rows per part, ordered by experiment ID and round. Decompress with
Python's standard gzip module. The manifest records each exported SHA-256 and
record count. Reports, original dataset manifests, paired traces, replay inputs,
scores/widths, figures, executing source snapshot and runtime identities are included.
Source snapshots retain exact executing bytes regardless of Git newline settings.

Model binaries, dataset arrays, coordinator JAR, SQLite/WAL/SHM and process logs
remain local. This is an analysis evidence publication, not a standalone resume
package. Original local artifact references are preserved. Earlier publications
are not overwritten or pooled into this controlled study.
'''
    readme=destination/'README.md';atomic(readme,text);record(readme)
    atomic(destination/'publication-manifest.json',dict(schemaVersion=1,publishedAt=datetime.datetime.now().astimezone().isoformat(),
        sourceBatch=batch.relative_to(ROOT).as_posix(),publicationType='COMPLETED_CONTROLLED_FUZZY_ABLATION_FULL',
        experiments=experiment_count,committedRounds=round_count,researchRuns=research_count,
        integrity=integrity,excluded=['SQLite/database files','model binaries','dataset arrays','coordinator JAR','process logs/locks'],files=records))
    print(f'Publication verified: {len(records)} files; {sum(r["bytes"] for r in records)/1024**2:.1f} MiB; {destination}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--batch',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    batch=args.batch or Path(json.loads((ROOT/'artifacts/research/controlled-fuzzy-ablation/full/active-batch.json').read_text())['folder'])
    publish(batch,args.output or ROOT/'results/research'/batch.name.replace('fuzzy-uncertainty-','controlled-fuzzy-ablation-',1))
