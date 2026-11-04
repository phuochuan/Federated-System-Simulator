"""Resume the established Release without changing or deleting research evidence.

Future ZIP parts use two-pass bounded streaming, not local archive deletion or
large RAM buffers. Existing ZIP files are reused. Remote verification ALWAYS
downloads bytes; a server-side digest alone is not a verification receipt.
"""
import argparse
import base64
from collections import Counter
from contextlib import contextmanager
import ctypes
import datetime
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import queue
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from archive_models_release import ROOT, API, Github, UploadBody, atomic, sha, reuse_part

TAG = 'models-backup-20261104'
LEGACY = ROOT / 'artifacts/model-release-backup' / TAG
WORK = LEGACY / 'preservation-v2'
OUTPUT = ROOT / 'results' / ('preservation-' + TAG)
EXCLUDE_DIRS = {'.git', '.venv', '.idea', '__pycache__', '.pytest_cache', '.gradle', 'build', 'node_modules', 'out'}
SECRET = re.compile(rb'(?:github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{25,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def event(kind, **data):
    WORK.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(at=now(), event=kind, **data))
    print(text, flush=True)
    with (WORK / 'upload.log').open('a', encoding='utf-8') as stream:
        stream.write(text + '\n')
        stream.flush()
        if kind in ('VERIFIED', 'BLOCKED', 'COMPLETED', 'AUDIT'):
            os.fsync(stream.fileno())


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlparse(req.full_url).hostname != urllib.parse.urlparse(newurl).hostname:
            redirected.remove_header('Authorization')
        return redirected


def download_verify(gh, asset, part):
    """Retain failed downloads. Remove ONLY a successful verification temporary."""
    if asset['name'] != part['name'] or asset['state'] != 'uploaded' or asset['size'] != part['bytes']:
        raise RuntimeError('Remote name/state/size mismatch: ' + part['name'])
    folder = WORK / 'verification-downloads'
    folder.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoCredentialRedirect())
    for attempt in range(1, 7):
        path = folder / (part['name'] + '.' + str(time.time_ns()) + '.download.tmp')
        if shutil.disk_usage(folder).free < part['bytes'] + 1024 ** 3:
            raise RuntimeError('Insufficient disk for verification download')
        h, count, started, heartbeat = hashlib.sha256(), 0, time.monotonic(), time.monotonic()
        try:
            headers = dict(gh.headers, Accept='application/octet-stream')
            req = urllib.request.Request(asset['url'] + '?verify=' + str(time.time_ns()), headers=headers)
            with opener.open(req, timeout=60) as inp, path.open('xb') as out:
                if 'json' in inp.headers.get('Content-Type', ''):
                    raise RuntimeError('Asset API returned metadata instead of binary: ' + part['name'])
                while block := inp.read(1024 * 1024):
                    out.write(block)
                    h.update(block)
                    count += len(block)
                    if time.monotonic() - started > 1200:
                        raise TimeoutError('Download total deadline')
                    if time.monotonic() - heartbeat > 30:
                        event('DOWNLOAD', name=part['name'], receivedBytes=count, expectedBytes=part['bytes'])
                        heartbeat = time.monotonic()
                out.flush()
                os.fsync(out.fileno())
            actual = sha(path)
            if actual != h.hexdigest():
                raise RuntimeError('Verification download changed on disk: ' + part['name'])
            if actual != part['sha256'] or count != part['bytes']:
                failure = dict(status='FAIL', name=part['name'], localSha256=part['sha256'],
                               retrievedSha256=actual, remoteSize=asset['size'], retrievedBytes=count,
                               retainedDownload=str(path.relative_to(ROOT)), at=now())
                atomic(WORK / 'failed-verification.json', failure)
                raise RuntimeError('Retrieved archive checksum mismatch: ' + part['name'])
            receipt = dict(status='PASS', name=part['name'], bytes=count, sha256=actual,
                           assetId=asset['id'], verifiedAt=now(), method='FULL_REMOTE_DOWNLOAD_SHA256')
            receipt_path = WORK / 'verification-receipts' / (part['name'] + '.' + str(asset['id']) + '.json')
            if receipt_path.exists():
                atomic(WORK / 'verification-runs' / (part['name'] + '.' + str(time.time_ns()) + '.json'), receipt)
            else:
                atomic(receipt_path, receipt)
            if path.resolve().parent != folder.resolve():
                raise RuntimeError('Unsafe verification temporary location')
            path.unlink()  # User explicitly permits successful verification downloads to be removed.
            event('VERIFIED', **receipt)
            return receipt
        except (OSError, http.client.HTTPException) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 502, 503, 504):
                raise RuntimeError('Download HTTP ' + str(error.code) + ': ' + part['name']) from None
            # A failed temporary remains intact, including partial downloads.
            if attempt == 6:
                raise RuntimeError('Verification transport budget exhausted: ' + part['name']) from None
            event('DOWNLOAD_RETRY', name=part['name'], attempt=attempt, reason=type(error).__name__)
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError('Verification retry budget exhausted')


class Sink:
    def __init__(self, target=None, cancel=None):
        self.target, self.cancel = target, cancel
        self.count, self.h = 0, hashlib.sha256()

    def write(self, data):
        self.count += len(data)
        self.h.update(data)
        if self.target:
            for offset in range(0, len(data), 65536):
                while True:
                    if self.cancel.is_set():
                        raise InterruptedError('Upload consumer stopped')
                    try:
                        self.target.put(data[offset:offset+65536], timeout=.5)
                        break
                    except queue.Full:
                        continue
        return len(data)

    def tell(self):
        return self.count

    def seek(self, *args):
        raise io.UnsupportedOperation('Streaming ZIP')

    def flush(self):
        pass


def zip_stream(rows, sink):
    records = []
    with zipfile.ZipFile(sink, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, physical, size, mtime in rows:
            path = (ROOT / physical).resolve()
            if not path.is_relative_to(ROOT) or Path(name).is_absolute() or '..' in Path(name).parts:
                raise RuntimeError('Unsafe preservation member')
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                raise RuntimeError('Evidence changed since inventory: ' + name)
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            h = hashlib.sha256()
            read_bytes = 0
            with path.open('rb') as inp, archive.open(info, 'w', force_zip64=True) as out:
                while block := inp.read(1024 * 1024):
                    if path.suffix.lower() in {'.json', '.jsonl', '.txt', '.log', '.properties', '.yaml', '.yml', '.py', '.ps1', '.java', '.md', '.xml'} and SECRET.search(block):
                        raise RuntimeError('Potential secret detected; file not uploaded: ' + name)
                    h.update(block)
                    read_bytes += len(block)
                    out.write(block)
            after = path.stat()
            if read_bytes != size or (after.st_size, after.st_mtime_ns) != (size, mtime):
                raise RuntimeError('Evidence mutated during packaging: ' + name)
            records.append(dict(path=name, bytes=size, sha256=h.hexdigest()))
        info = zipfile.ZipInfo('archive-file-manifest.jsonl', (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, ''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in records))
    return dict(bytes=sink.count, sha256=sink.h.hexdigest(), files=len(records))


class ZipBody:
    def __init__(self, rows, expected):
        self.queue = queue.Queue(maxsize=16)
        self.cancel = threading.Event()
        self.pending = b''
        self.failure, self.result = None, None
        self.expected = expected
        def produce():
            try:
                self.result = zip_stream(rows, Sink(self.queue, self.cancel))
            except BaseException as error:
                self.failure = error
            finally:
                while not self.cancel.is_set():
                    try:
                        self.queue.put(None, timeout=.5)
                        break
                    except queue.Full:
                        pass
        self.thread = threading.Thread(target=produce, daemon=True)
        self.thread.start()

    def read(self, size=8192):
        if not self.pending:
            block = self.queue.get(timeout=120)
            if block is None:
                if self.failure:
                    raise RuntimeError('Streaming ZIP source failed: ' + str(self.failure))
                if (self.result['bytes'], self.result['sha256']) != (self.expected['bytes'], self.expected['sha256']):
                    raise RuntimeError('Streaming ZIP differs from package pass')
                return b''
            self.pending = block
        data, self.pending = self.pending[:size], self.pending[size:]
        return data

    def close(self):
        self.cancel.set()
        self.thread.join(timeout=120)
        if self.thread.is_alive():
            raise RuntimeError('Cannot stop ZIP producer; refusing another upload')


def state_read():
    return json.loads((WORK / 'state.json').read_text())


def audit(gh):
    legacy = json.loads((LEGACY / 'state.json').read_text())
    release = gh.call(API + '/releases/' + str(legacy['releaseId']))
    if release['tag_name'] != TAG:
        raise RuntimeError('Existing release does not belong to this batch')
    assets = gh.assets(release)
    report = dict(at=now(), sourceGitHead=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  gitStatus=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines(),
                  release={k: release[k] for k in ('id', 'tag_name', 'name', 'draft', 'target_commitish')},
                  originalModelCommit=legacy['sourceCommit'], modelFiles=legacy['files'], modelBytes=legacy['originalBytes'],
                  previousParts=len(legacy['parts']), previousVerification='SERVER_DIGEST_ONLY; full download required by new protocol',
                  remoteAssets=[{k: a.get(k) for k in ('id', 'name', 'state', 'size', 'digest')} for a in assets],
                  localArchives=[dict(name=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in LEGACY.glob('*.zip')],
                  exclusions=['Git credentials, .env secrets, unrelated personal files', 'virtualenv/dependency/build caches',
                              'SQLite WAL/SHM replaced by retained consistent SQLite backups', 'PID/lock files', 'preservation working directory'],
                  design='Resume existing ZIP names; future ZIPs use bounded two-pass streaming; no local archive deletion',
                  status='PRESERVATION INCOMPLETE')
    atomic(WORK / 'audits' / (str(time.time_ns()) + '.json'), report)
    if not (WORK / 'preservation-audit.json').exists():
        atomic(WORK / 'preservation-audit.json', report)
    event('AUDIT', previousParts=report['previousParts'], remoteAssets=len(assets), localArchives=len(report['localArchives']))
    return report, release


def source_paths():
    for top in ('artifacts', 'results', 'models', 'checkpoints', 'logs', 'data', 'ml-python/data'):
        base = ROOT / top
        if not base.exists():
            continue
        for folder, dirs, names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not (Path(folder) / d).is_symlink()]
            here = Path(folder)
            if here == ROOT / 'artifacts':
                dirs[:] = [d for d in dirs if d not in ('models', 'model-release-backup')]
            if here == ROOT / 'results':
                dirs[:] = [d for d in dirs if d != OUTPUT.name]
            for name in sorted(names):
                p = here / name
                if p.is_symlink() or name.endswith(('.db-wal', '.db-shm', '.pid', '.lock', '.download.tmp')) or name.startswith('.env'):
                    continue
                yield p
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    for name in paths:
        if not name or name.startswith(('results/', 'artifacts/')):
            continue
        p = ROOT / name
        if p.is_file() and not p.is_symlink() and not p.name.startswith('.env') and p.suffix.lower() not in ('.pem', '.key'):
            yield p
    for p in LEGACY.iterdir():
        if p.is_file() and (p.suffix in ('.json', '.log') or '.log.' in p.name):
            yield p


def sqlite_identity(path):
    stat = path.stat()
    wal = path.with_name(path.name + '-wal')
    w = wal.stat() if wal.exists() else None
    return dict(bytes=stat.st_size, mtime=stat.st_mtime_ns,
                walBytes=w.st_size if w else None, walMtime=w.st_mtime_ns if w else None)


def sqlite_copy(source_path, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise RuntimeError('Refuse overwriting a retained SQLite snapshot')
    source = sqlite3.connect(source_path.resolve().as_uri() + '?mode=ro', uri=True)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest, pages=1024, sleep=.1)
        if dest.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise RuntimeError('SQLite snapshot quick_check failed')
    finally:
        dest.close()
        source.close()


def sqlite_snapshot(path, logical):
    previous = WORK / 'sqlite-snapshots' / logical
    # SQLite sidecar names can exceed Windows MAX_PATH even when Python opens
    # the base path. Keep old snapshots; use short stable names for new ones.
    key = hashlib.sha256(logical.encode()).hexdigest()[:24]
    snapshot = previous if previous.exists() else WORK / 'sqlite-snapshots' / (key + '.sqlite')
    receipt_path = snapshot.with_name(snapshot.name + '.receipt.json')
    identity = sqlite_identity(path)
    existed = snapshot.exists()
    if snapshot.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if sha(snapshot) != receipt['sha256']:
            raise RuntimeError('Retained SQLite snapshot checksum changed: ' + logical)
        if receipt['sourceIdentity'] == identity:
            return snapshot
    if shutil.disk_usage(WORK).free < path.stat().st_size + 2 * 1024 ** 3:
        raise RuntimeError('Insufficient disk for retained SQLite snapshot')
    if not snapshot.exists():
        sqlite_copy(path, snapshot)
    # Closing the last SQLite connection can checkpoint WAL without changing
    # logical rows. An orphan/raw-identity transition is accepted ONLY after a
    # second independent SQLite backup is byte-identical. Retain both copies.
    if existed or sqlite_identity(path) != identity:
        candidate = WORK / 'sqlite-revalidation' / (key + '-' + str(time.time_ns()) + '.sqlite')
        sqlite_copy(path, candidate)
        if sha(candidate) != sha(snapshot):
            raise RuntimeError('SQLite snapshot differs from fresh source backup: ' + logical)
        event('SQLITE_REVALIDATED', source=logical, sha256=sha(snapshot))
    record = dict(sourcePath=logical, sourceIdentity=sqlite_identity(path), sha256=sha(snapshot),
                  snapshotBytes=snapshot.stat().st_size, quickCheck='ok', at=now())
    if receipt_path.exists():
        atomic(snapshot.with_name(snapshot.name + '.' + str(time.time_ns()) + '.receipt.json'), record)
    else:
        atomic(receipt_path, record)
    event('SQLITE_SNAPSHOT', source=logical, bytes=snapshot.stat().st_size)
    return snapshot


def prepare(report):
    if (WORK / 'state.json').exists():
        return
    dbpath = WORK / 'inventory.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, physical TEXT, bytes INTEGER, mtime INTEGER, grp TEXT, part TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS parts(name TEXT PRIMARY KEY, grp TEXT, idx INTEGER, files INTEGER, originalBytes INTEGER, createdAt TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)')
        if db.execute('SELECT count(*) FROM files').fetchone()[0]:
            saved = db.execute('SELECT value FROM metadata WHERE key="preparedState"').fetchone()
            if saved:
                atomic(WORK / 'state.json', json.loads(saved[0]))
                return
            if not db.execute('SELECT value FROM metadata WHERE key="modelInventoryComplete"').fetchone():
                raise RuntimeError('Interrupted inventory exists without commit metadata; inspect it, do not silently rebuild')
        legacy = json.loads((LEGACY / 'state.json').read_text())
        if not db.execute('SELECT value FROM metadata WHERE key="modelInventoryComplete"').fetchone():
            old = sqlite3.connect((LEGACY / 'inventory.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
            count = 0
            for path, size, mtime, part in old.execute('SELECT path,bytes,mtime_ns,part FROM files ORDER BY path'):
                stat = (ROOT / path).stat()
                if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                    raise RuntimeError('Legacy model inventory changed: ' + path)
                db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)', (path, path, size, mtime, 'models', f'models-{part:04d}.zip' if part else None))
                count += 1
                if count % 25000 == 0:
                    event('INVENTORY', modelsChecked=count)
            old.close()
            actual = sum(len(names) for _, _, names in os.walk(ROOT / 'artifacts/models'))
            if count != actual:
                raise RuntimeError('Model inventory membership changed; preserve new/missing files explicitly')
            for part in legacy['parts']:
                db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?)', (part['name'], 'models', part['number'], part['files'], part['originalBytes'], legacy['startedAt']))
            db.execute('INSERT INTO metadata VALUES(?,?)', ('modelInventoryComplete', str(count)))
            db.commit()
        else:
            event('REUSED_MODEL_INVENTORY', files=legacy['files'])
        for p in source_paths():
            logical = p.relative_to(ROOT).as_posix()
            physical = logical
            if p.suffix.lower() in ('.db', '.sqlite', '.sqlite3'):
                try:
                    snapshot = sqlite_snapshot(p, logical)
                except Exception as error:
                    raise RuntimeError('SQLite snapshot failed for ' + logical + ': ' + str(error)) from None
                physical = snapshot.relative_to(ROOT).as_posix()
            stat = (ROOT / physical).stat()
            group = 'published-results' if logical.startswith('results/') else 'source-and-config' if not logical.startswith('artifacts/') else 'research-evidence'
            db.execute('INSERT OR IGNORE INTO files VALUES(?,?,?,?,?,NULL)', (logical, physical, stat.st_size, stat.st_mtime_ns, group))
        # Frozen stable part membership; later retries never regroup files.
        for group in ('models', 'research-evidence', 'published-results', 'source-and-config'):
            index = len(legacy['parts']) if group == 'models' else 0
            rows, size = [], 0
            prefix = 'models' if group == 'models' else group
            def commit_part():
                nonlocal rows, size, index
                if not rows:
                    return
                index += 1
                name = f'{prefix}-{index:04d}.zip'
                db.executemany('UPDATE files SET part=? WHERE path=?', ((name, path) for path in rows))
                db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?)', (name, group, index, len(rows), size, now()))
                rows, size = [], 0
            for path, length in db.execute('SELECT path,bytes FROM files WHERE grp=? AND part IS NULL ORDER BY path', (group,)):
                rows.append(path)
                size += length
                if size >= 384 * 1024 ** 2:
                    commit_part()
            commit_part()
        summary = db.execute('SELECT grp,count(*),sum(bytes) FROM files GROUP BY grp').fetchall()
        expected = db.execute('SELECT count(*) FROM parts').fetchone()[0]
        if db.execute('SELECT count(*) FROM files WHERE part IS NULL').fetchone()[0]:
            raise RuntimeError('Unassigned evidence files in preservation plan')
        state = dict(schemaVersion=2, batch=TAG, releaseId=report['release']['id'], sourceGitHead=report['sourceGitHead'],
                     originalModelCommit=report['originalModelCommit'], status='PREPARED', preparedAt=now(),
                     expectedParts=expected, groups=[dict(group=g, files=n, bytes=b) for g, n, b in summary], parts={})
        # Preserve prior receipts as expectations, NOT strict download verification.
        for part in legacy['parts']:
            state['parts'][part['name']] = {k: part[k] for k in ('name', 'bytes', 'sha256', 'files', 'assetId')}
        db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('preparedState', json.dumps(state)))
        db.commit()
    atomic(WORK / 'state.json', state)
    event('PREPARED', expectedParts=expected, groups=state['groups'])


def rows_for(db, name):
    return db.execute('SELECT path,physical,bytes,mtime FROM files WHERE part=? ORDER BY path', (name,)).fetchall()


def freeze_sources():
    """Retain the source point-in-time even if preservation tooling is repaired."""
    receipt_path = WORK / 'source-snapshot-receipt.json'
    old = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    expected = {r['path']: r['sha256'] for r in old['files']} if old else {}
    records = []
    with sqlite3.connect(WORK / 'inventory.sqlite') as db:
        for logical, physical, size, mtime in db.execute('SELECT path,physical,bytes,mtime FROM files WHERE grp="source-and-config"').fetchall():
            original = ROOT / physical
            stat = original.stat()
            if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                raise RuntimeError('Source capsule metadata differs: ' + logical)
            target = WORK / 'source-snapshots' / (hashlib.sha256(logical.encode()).hexdigest()[:24] + original.suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            if original.resolve() != target.resolve() and not target.exists():
                shutil.copy2(original, target)
            value = sha(target)
            if value != sha(original) or (expected and expected.get(logical) != value):
                raise RuntimeError('Source capsule SHA256 differs: ' + logical)
            db.execute('UPDATE files SET physical=? WHERE path=?', (target.relative_to(ROOT).as_posix(), logical))
            records.append(dict(path=logical, bytes=size, sha256=value, originalMtime=mtime))
        db.commit()
    if not old:
        atomic(receipt_path, dict(at=now(), sourceGitHead=state_read()['sourceGitHead'], files=records))


def upload_part(gh, release, part, rows, local=None):
    for attempt in range(1, 7):
        matches = [a for a in gh.assets(release) if a['name'] == part['name']]
        if len(matches) > 1:
            raise RuntimeError('Duplicate remote asset names: ' + part['name'])
        if matches and matches[0]['state'] == 'uploaded':
            asset = matches[0]
            if asset['size'] != part['bytes'] or (asset.get('digest') and asset['digest'] != 'sha256:' + part['sha256']):
                # Verify actual retrieved bytes before considering any replacement.
                download_verify(gh, asset, part)
            return asset
        if matches:
            if matches[0]['state'] != 'starter':
                raise RuntimeError('Unrecognized remote asset state')
            req = urllib.request.Request(matches[0]['url'], headers=gh.headers, method='DELETE')
            with urllib.request.urlopen(req, timeout=60):
                pass  # Only the uncommitted placeholder for this exact part.
            event('REPLACED_INCOMPLETE_ASSET', name=part['name'], assetId=matches[0]['id'])
        url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(part['name'])
        headers = dict(gh.headers, **{'Content-Type': 'application/octet-stream', 'Content-Length': str(part['bytes'])})
        producer = None
        try:
            if local:
                with local.open('rb') as stream:
                    body = UploadBody(stream, part['bytes'], part['name'], total_seconds=1200)
                    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method='POST'), timeout=60) as response:
                        return json.load(response)
            producer = ZipBody(rows, part)
            body = UploadBody(producer, part['bytes'], part['name'], total_seconds=1200)
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method='POST'), timeout=60) as response:
                asset = json.load(response)
            if producer.failure or producer.result is None or producer.result['sha256'] != part['sha256']:
                raise RuntimeError('Streaming producer hash not committed')
            return asset
        except urllib.error.HTTPError as error:
            if error.code not in (429, 422, 502, 503, 504):
                raise RuntimeError('Upload HTTP ' + str(error.code) + ': ' + part['name']) from None
            event('UPLOAD_RETRY', name=part['name'], attempt=attempt, httpStatus=error.code)
        except (OSError, http.client.HTTPException, queue.Empty) as error:
            event('UPLOAD_RETRY', name=part['name'], attempt=attempt, reason=type(error).__name__)
        finally:
            if producer:
                producer.close()
        if attempt < 6:
            time.sleep(min(60, 2 ** attempt))
    raise RuntimeError('Upload retry budget exhausted: ' + part['name'])


def save_manifests(state):
    records = []
    with sqlite3.connect(WORK / 'inventory.sqlite') as db:
        for name, group, index, files, original, created in db.execute('SELECT * FROM parts ORDER BY grp,idx'):
            p = state['parts'].get(name, {})
            receipt = WORK / 'verification-receipts' / (name + '.' + str(p.get('assetId')) + '.json')
            verification = json.loads(receipt.read_text()) if receipt.exists() else None
            valid = verification and verification.get('status') == 'PASS' and verification.get('sha256') == p.get('sha256') and verification.get('bytes') == p.get('bytes') and verification.get('assetId') == p.get('assetId') and verification.get('method') == 'FULL_REMOTE_DOWNLOAD_SHA256'
            records.append(dict(filename=name, byteSize=p.get('bytes'), sha256=p.get('sha256'), sourceArtifactGroup=group,
                                archivePartIndex=index, files=files, originalBytes=original, createdAt=created,
                                verificationStatus='PASS' if valid else 'PENDING', remoteVerification=verification,
                                assetId=p.get('assetId'), downloadUrl=f'https://github.com/phuochuan/Federated-System-Simulator/releases/download/{TAG}/{name}'))
    manifest = {k: v for k, v in state.items() if k not in ('parts', 'status')}
    manifest['status'] = 'ARCHIVES_VERIFIED' if all(r['verificationStatus'] == 'PASS' for r in records) else 'INCOMPLETE'
    manifest.update(archives=records, verificationMethod='FULL_REMOTE_DOWNLOAD_SHA256',
                    sourceSnapshot=json.loads((WORK / 'source-snapshot-receipt.json').read_text()) if (WORK / 'source-snapshot-receipt.json').exists() else None,
                    sqliteSnapshots=[json.loads(p.read_text()) for p in sorted((WORK / 'sqlite-snapshots').rglob('*.receipt.json'))],
                    exclusions=json.loads((WORK / 'preservation-audit.json').read_text())['exclusions'])
    atomic(WORK / 'preservation-manifest.json', manifest)
    atomic(WORK / 'preservation-sha256.json', dict(batch=TAG, archives=records))
    text = '\n'.join(f'{r["sha256"] or "PENDING"}  {r["filename"]}' for r in records) + '\n'
    (WORK / 'preservation-sha256.txt').write_text(text, encoding='utf-8')
    return manifest


def run(mode):
    gh = Github()
    report, release = audit(gh)
    if mode == 'audit':
        print(json.dumps(report, indent=2))
        return
    if mode == 'verify':
        if not (WORK / 'state.json').exists():
            raise RuntimeError('No prepared preservation plan; verify does not package anything')
        state = state_read()
        assets = {a['name']: a for a in gh.assets(release)}
        with sqlite3.connect((WORK / 'inventory.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
            for (name,) in db.execute('SELECT name FROM parts ORDER BY grp,idx'):
                part = state['parts'].get(name)
                if not part or name not in assets:
                    raise RuntimeError('Missing expected remote part: ' + name)
                download_verify(gh, assets[name], part)
        result = dict(status='PASS', mode='VERIFY_ONLY', expectedParts=state['expectedParts'],
                      verifiedParts=state['expectedParts'], verifiedAt=now(), method='FULL_REMOTE_DOWNLOAD_SHA256')
        atomic(WORK / 'verification-runs' / ('full-' + str(time.time_ns()) + '.json'), result)
        atomic(WORK / 'preservation-status.json', dict(result, status='PRESERVATION COMPLETE — VERIFIED' if state['status'] == 'COMPLETED' else 'PRESERVATION INCOMPLETE'))
        event('VERIFY_ONLY_PASS', expectedParts=state['expectedParts'])
        return
    prepare(report)
    freeze_sources()
    state = state_read()
    if not release['draft'] and state.get('status') != 'COMPLETED':
        raise RuntimeError('Refuse changing an already published incomplete release')
    state['status'] = 'VERIFYING' if mode == 'verify' else 'RUNNING'
    atomic(WORK / 'state.json', state)
    save_manifests(state)
    atomic(WORK / 'preservation-status.json', dict(status='PRESERVATION INCOMPLETE', phase=state['status'], expectedParts=state['expectedParts'], at=now()))
    assets = {a['name']: a for a in gh.assets(release)}
    with sqlite3.connect(WORK / 'inventory.sqlite') as db:
        for name, group, index, files, original, created in db.execute('SELECT * FROM parts ORDER BY CASE grp WHEN "models" THEN 0 ELSE 1 END,grp,idx').fetchall():
            state['currentPart'] = name
            atomic(WORK / 'state.json', state)
            part = state['parts'].get(name)
            local = LEGACY / name
            if not part:
                if mode == 'verify':
                    raise RuntimeError('Missing expected packaged part: ' + name)
                rows = rows_for(db, name)
                event('PACKAGE', name=name, files=files, originalBytes=original)
                if local.exists():
                    reuse_part([(r[0], r[2], r[3]) for r in rows], local)
                    part = dict(name=name, bytes=local.stat().st_size, sha256=sha(local), files=len(rows))
                else:
                    part = dict(name=name, **zip_stream(rows, Sink()))
                if part['bytes'] >= 1800 * 1024 ** 2:
                    raise RuntimeError('Part too close to GitHub asset size limit; preserve inventory and review: ' + name)
                state['parts'][name] = part
                atomic(WORK / 'state.json', state)
            if mode == 'package':
                continue
            asset = assets.get(name)
            receipt_file = WORK / 'verification-receipts' / (name + '.' + str(part.get('assetId')) + '.json')
            receipt = json.loads(receipt_file.read_text()) if receipt_file.exists() else None
            if mode != 'verify' and receipt and receipt.get('method') == 'FULL_REMOTE_DOWNLOAD_SHA256' and receipt.get('status') == 'PASS' and asset and asset['state'] == 'uploaded' and receipt['assetId'] == asset['id'] and receipt['sha256'] == part['sha256'] and asset['size'] == part['bytes'] and asset.get('digest') in (None, 'sha256:' + part['sha256']):
                event('REUSED_VERIFIED', name=name)
                continue
            if mode == 'verify':
                if not asset:
                    raise RuntimeError('Missing remote archive: ' + name)
            else:
                asset = upload_part(gh, release, part, rows_for(db, name), local if local.exists() else None)
            part['assetId'] = asset['id']
            atomic(WORK / 'state.json', state)
            download_verify(gh, asset, part)
            save_manifests(state)
        # Every source is rechecked before completing; raw files are never removed.
        for name, physical, size, mtime in db.execute('SELECT path,physical,bytes,mtime FROM files'):
            stat = (ROOT / physical).stat()
            if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                raise RuntimeError('Source changed before final verification: ' + name)
    state.pop('currentPart', None)
    manifest = save_manifests(state)
    if mode == 'package':
        event('PACKAGED', expectedParts=state['expectedParts'])
        return
    assets = gh.assets(release)
    names = Counter(a['name'] for a in assets)
    asset_index = {a['name']: a for a in assets}
    expected = {r['filename'] for r in manifest['archives']}
    if any(names[name] != 1 for name in expected) or any(r['verificationStatus'] != 'PASS' for r in manifest['archives']):
        raise RuntimeError('Full manifest verification failed')
    if len(expected) != state['expectedParts']:
        raise RuntimeError('Expected part count mismatch')
    for record in manifest['archives']:
        asset = asset_index[record['filename']]
        if asset['state'] != 'uploaded' or asset['id'] != record['assetId'] or asset['size'] != record['byteSize'] or asset.get('digest') not in (None, 'sha256:' + record['sha256']):
            raise RuntimeError('Remote identity changed after retrieval: ' + record['filename'])
    for local in LEGACY.glob('*.zip'):
        record = state['parts'].get(local.name)
        if local.name not in expected or not record or sha(local) != record['sha256']:
            raise RuntimeError('Local archive lacks verified counterpart: ' + local.name)
    if any(a['name'].endswith('.zip') and a['name'] not in expected for a in assets):
        raise RuntimeError('Unaccounted remote archive; do not silently omit it')
    state['status'] = 'ARCHIVES_VERIFIED'
    state.setdefault('completedAt', now())
    atomic(WORK / 'state.json', state)
    manifest = save_manifests(state)
    final = dict(status='PASS', sourceGitHead=state['sourceGitHead'], release=release['html_url'], batch=TAG,
                 expectedParts=len(expected), uploadedParts=len(expected), verifiedParts=len(expected), failedParts=0,
                 totalBytes=sum(r['byteSize'] for r in manifest['archives']), verifiedAt=state['completedAt'],
                 manifestSha256=sha(WORK / 'preservation-manifest.json'), method='FULL_REMOTE_DOWNLOAD_SHA256')
    atomic(WORK / 'preservation-final-verification.json', final)
    history = WORK / 'preservation-upload-history.json'
    if not history.exists():
        logs = [p for p in LEGACY.iterdir() if p.is_file() and (p.suffix == '.log' or '.log.' in p.name)]
        logs.extend(p for p in WORK.iterdir() if p.is_file() and (p.suffix == '.log' or '.log.' in p.name))
        entries = []
        for p in logs:
            data = p.read_bytes()
            if SECRET.search(data):
                raise RuntimeError('Potential secret in upload history; do not upload')
            entries.append(dict(path=p.relative_to(ROOT).as_posix(), bytes=len(data),
                                sha256=hashlib.sha256(data).hexdigest(), base64=base64.b64encode(data).decode('ascii')))
        atomic(history, dict(at=now(), scope='Upload logs through complete archive verification', files=entries))
    tool_copy = WORK / 'preservation-tool-source.py'
    if not tool_copy.exists():
        shutil.copy2(Path(__file__), tool_copy)
    # Metadata is itself uploaded and retrieved before publication. Retain all local metadata.
    metadata_names = ('preservation-manifest.json', 'preservation-sha256.json', 'preservation-sha256.txt',
                      'preservation-final-verification.json', 'preservation-upload-history.json', 'preservation-tool-source.py')
    for name in metadata_names:
        path = WORK / name
        asset = gh.upload(release, path)
        download_verify(gh, asset, dict(name=name, bytes=path.stat().st_size, sha256=sha(path)))
    if release['draft']:
        gh.call(API + '/releases/' + str(release['id']), 'PATCH', dict(draft=False,
                name='Research Preservation — 2026-11-04', target_commitish=state['sourceGitHead'],
                body=f'PRESERVATION COMPLETE — VERIFIED. {len(expected)} ZIP parts, full remote download SHA-256. Original models source {state["originalModelCommit"]}; expanded preservation source {state["sourceGitHead"]}. See preservation-manifest.json. No local evidence deleted.'))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in metadata_names:
        destination = OUTPUT / name
        if destination.exists() and sha(destination) != sha(WORK / name):
            raise RuntimeError('Existing preservation publication differs; do not overwrite')
        if not destination.exists():
            shutil.copy2(WORK / name, destination)
    state['status'] = 'COMPLETED'
    atomic(WORK / 'state.json', state)
    atomic(WORK / 'preservation-status.json', dict(final, status='PRESERVATION COMPLETE — VERIFIED'))
    event('COMPLETED', **final)


@contextmanager
def lock():
    import msvcrt
    with (LEGACY / 'backup.lock').open('r+b') as stream:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['audit', 'package', 'upload', 'verify', 'resume', 'status'])
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.mode == 'status':
        state = state_read() if (WORK / 'state.json').exists() else json.loads((WORK / 'preservation-status.json').read_text()) if (WORK / 'preservation-status.json').exists() else {'status': 'NOT_PREPARED'}
        state.pop('parts', None)
        print(json.dumps(state, indent=2))
    else:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            with lock():
                previous = WORK / 'preservation-status.json'
                if previous.exists():
                    atomic(WORK / 'status-history' / (str(time.time_ns()) + '.json'), json.loads(previous.read_text()))
                atomic(previous, dict(status='PRESERVATION INCOMPLETE', phase='STARTING_' + args.mode.upper(), at=now()))
                run(args.mode)
        except Exception as error:
            atomic(WORK / 'preservation-status.json', dict(status='PRESERVATION INCOMPLETE', error=str(error), at=now()))
            event('BLOCKED', reason=str(error))
            raise SystemExit(20)
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
