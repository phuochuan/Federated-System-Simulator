"""Read-only verification of the compact research synthesis (standard library)."""
import csv
import gzip
import hashlib
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'results/research-synthesis-20261104'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify():
    manifest = json.loads((FOLDER / 'publication-manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        path = (FOLDER / item['path']).resolve()
        if not path.is_relative_to(FOLDER.resolve()) or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise RuntimeError('Synthesis file mismatch: ' + item['path'])
    for item in manifest['inputManifests']:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != item['sha256']:
            raise RuntimeError('Original publication manifest changed')
    for item in manifest['analysisSources']:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest() != item['sha256LF']:
            raise RuntimeError('Analysis source changed')
    audit = json.loads((FOLDER / 'evidence-audit.json').read_text())
    if not audit['passed'] or audit['rounds']['streamedCommittedRounds'] != 27308 or audit['pareto']['researchRounds'] != 4200:
        raise RuntimeError('Unexpected evidence audit')
    with (FOLDER / 'run-metrics.csv').open(encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 450 or len({r['experiment'] for r in rows}) != 450:
        raise RuntimeError('Duplicate or missing research runs')
    counts = {}
    with gzip.open(FOLDER / 'round-metrics.csv.gz', 'rt', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            eid = row['experiment']
            counts[eid] = counts.get(eid, 0) + 1
            if int(row['round']) != counts[eid]:
                raise RuntimeError('Round gap or duplicate')
            if row['evaluationSplit'] == 'test' and (row['round'] != '70' or row['stage'] not in ('FULL', 'E3')):
                raise RuntimeError('Non-final or non-confirmation test metric')
    if sum(counts.values()) != 27308:
        raise RuntimeError('Compact round export count mismatch')
    return dict(status='PASS', verifiedSynthesisFiles=len(manifest['files']),
                researchRuns=450, committedRoundsIncludingFourAudits=31508,
                modelBackupComplete=False, originalFilesDeleted=False)


def seal():
    path = FOLDER / 'publication-manifest.json'
    if path.exists():
        raise FileExistsError('Preserve the existing sealed publication')
    audit = json.loads((FOLDER / 'evidence-audit.json').read_text())
    if not audit['passed'] or not (FOLDER / 'agent-legacy-context.vi.md').is_file():
        raise RuntimeError('Cannot seal incomplete synthesis')
    files = [dict(path=p.relative_to(FOLDER).as_posix(), bytes=p.stat().st_size, sha256=digest(p))
             for p in sorted(FOLDER.rglob('*')) if p.is_file()]
    inputs = [ROOT / 'results/archive-manifest.json']
    inputs += sorted((ROOT / 'results/research').glob('*/publication-manifest.json'))
    sources = ['scripts/synthesize_research_results.py', 'scripts/plot_research_synthesis.py',
               'scripts/verify_research_synthesis.py', 'scripts/test_research_synthesis.py']
    manifest = dict(schemaVersion=1, publicationType='compact-post-hoc-research-synthesis',
                    researchRuns=450, researchRounds=31500, separateAuditRuns=4, separateAuditRounds=8,
                    fullModelBackup=False, originalFilesDeleted=False,
                    inputManifests=[dict(path=p.relative_to(ROOT).as_posix(), sha256=digest(p)) for p in inputs],
                    analysisSources=[dict(path=p, sha256LF=hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()) for p in sources],
                    files=files)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal', action='store_true', help='Create a NEW publication manifest, refusing replacement')
    args = parser.parse_args()
    if args.seal:
        seal()
    print(json.dumps(verify(), indent=2))
