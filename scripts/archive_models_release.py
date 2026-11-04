"""Lossless, resumable models backup to GitHub Release; never deletes source files.

Uses only Python's standard library. Credentials remain in memory and come from
the existing Git credential helper. Large binary parts are release assets, not
Git objects. The Git-tracked catalog is written only after complete verification.
"""
import argparse
import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'phuochuan/Federated-System-Simulator'
API = 'https://api.github.com/repos/' + REPO


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as out:
        json.dump(value, out, indent=2)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class UploadBody:
    """Bound total upload time as well as individual socket operations."""
    def __init__(self, stream, size, name, total_seconds=900):
        self.stream, self.size, self.name = stream, size, name
        self.started = self.last_log = time.monotonic()
        self.deadline = self.started + total_seconds
        self.sent = 0

    def read(self, size=-1):
        now = time.monotonic()
        if now >= self.deadline:
            raise TimeoutError('Total upload deadline exceeded')
        block = self.stream.read(size)
        self.sent += len(block)
        if now - self.last_log >= 30 or not block:
            print(f'[TRANSFER] {self.name} suppliedMiB={self.sent/1024**2:.1f}/{self.size/1024**2:.1f} '
                  f'elapsedSeconds={now-self.started:.0f}', flush=True)
            self.last_log = now
        return block


class Github:
    def __init__(self):
        result = subprocess.run(['git', 'credential', 'fill'], cwd=ROOT,
                                input='protocol=https\nhost=github.com\n\n',
                                text=True, capture_output=True, check=True)
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if not values.get('password'):
            raise RuntimeError('GitHub credential helper has no API credential')
        self.headers = {'Authorization': 'Bearer ' + values['password'],
                        'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28',
                        'User-Agent': 'MiniFLS-lossless-backup'}

    def call(self, url, method='GET', value=None):
        headers = dict(self.headers)
        payload = None
        if value is not None:
            payload = json.dumps(value).encode()
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code not in (429, 502, 503, 504) or attempt == 5:
                    raise RuntimeError('GitHub API failed HTTP ' + str(error.code)) from None
            except (TimeoutError, OSError):
                if attempt == 5:
                    raise RuntimeError('GitHub API transport retry budget exhausted') from None
            time.sleep(min(60, 2 ** (attempt + 1)))

    def assets(self, release):
        result = []
        page = 1
        while True:
            rows = self.call(API + f'/releases/{release["id"]}/assets?per_page=100&page={page}')
            result.extend(rows)
            if len(rows) < 100:
                return result
            page += 1

    def verify(self, asset, expected, size):
        if asset['size'] != size or asset['state'] != 'uploaded':
            raise RuntimeError('Remote asset incomplete: ' + asset['name'])
        if asset.get('digest'):
            if asset['digest'] != 'sha256:' + expected:
                raise RuntimeError('Remote SHA-256 mismatch: ' + asset['name'])
            return
        # Older GitHub responses may omit digest; verify by streaming download.
        headers = dict(self.headers, Accept='application/octet-stream')
        request = urllib.request.Request(asset['url'], headers=headers)
        with urllib.request.urlopen(request, timeout=300) as response:
            actual = hashlib.file_digest(response, 'sha256').hexdigest()
        if actual != expected:
            raise RuntimeError('Downloaded SHA-256 mismatch: ' + asset['name'])

    def upload(self, release, path):
        expected, size = sha(path), path.stat().st_size
        for attempt in range(6):
            existing = next((a for a in self.assets(release) if a['name'] == path.name), None)
            if existing:
                # GitHub can leave a starter after a failed upload. Its size may
                # already report Content-Length, not actual committed bytes.
                # Remove only that uncommitted upload placeholder in this release.
                if existing['state'] == 'starter':
                    request = urllib.request.Request(existing['url'], headers=self.headers, method='DELETE')
                    with urllib.request.urlopen(request, timeout=120):
                        pass
                    existing = None
            if existing:
                self.verify(existing, expected, size)
                return existing
            url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(path.name)
            headers = dict(self.headers)
            headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(size)})
            try:
                with path.open('rb') as stream:
                    body = UploadBody(stream, size, path.name)
                    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
                    with urllib.request.urlopen(request, timeout=60) as response:
                        asset = json.load(response)
                self.verify(asset, expected, size)
                return asset
            except urllib.error.HTTPError as error:
                if error.code not in (429, 502, 503, 504, 422) or attempt == 5:
                    raise RuntimeError('Asset upload failed HTTP ' + str(error.code)) from None
            except (TimeoutError, OSError, http.client.HTTPException):
                if attempt == 5:
                    raise RuntimeError('Asset upload transport retry budget exhausted') from None
                print(f'[RETRY] asset={path.name} attempt={attempt+1}/6 reason=transport-or-deadline', flush=True)
            time.sleep(min(60, 2 ** (attempt + 1)))
        raise RuntimeError('Asset upload retry budget exhausted')


def inventory(db, source):
    if db.execute('SELECT count(*) FROM files').fetchone()[0]:
        return
    count = 0
    for folder, dirs, names in os.walk(source, followlinks=False):
        if any((Path(folder) / name).is_symlink() for name in dirs):
            raise RuntimeError('Refuse symbolic model directory')
        for name in sorted(names):
            path = Path(folder) / name
            if path.is_symlink():
                raise RuntimeError('Refuse symbolic model file')
            stat = path.stat()
            db.execute('INSERT INTO files(path,bytes,mtime_ns) VALUES(?,?,?)',
                       (path.relative_to(ROOT).as_posix(), stat.st_size, stat.st_mtime_ns))
            count += 1
        if count and count % 10000 < len(names):
            print('[INVENTORY] files=' + str(count), flush=True)
    db.commit()


def verify_member_name(name):
    target = (ROOT / name).resolve()
    if not target.is_relative_to((ROOT / 'artifacts/models').resolve()):
        raise RuntimeError('Archive path outside models: ' + name)
    return target


def build_part(rows, path):
    records = []
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, size, mtime in rows:
            source = verify_member_name(name)
            before = source.stat()
            if (before.st_size, before.st_mtime_ns) != (size, mtime):
                raise RuntimeError('Model changed since inventory: ' + name)
            h = hashlib.sha256()
            with source.open('rb') as inp, archive.open(name, 'w', force_zip64=True) as out:
                while block := inp.read(1024 * 1024):
                    h.update(block)
                    out.write(block)
            after = source.stat()
            if (after.st_size, after.st_mtime_ns) != (size, mtime):
                raise RuntimeError('Model mutated during backup: ' + name)
            records.append(dict(path=name, bytes=size, sha256=h.hexdigest()))
        manifest_info = zipfile.ZipInfo('archive-file-manifest.jsonl', (1980, 1, 1, 0, 0, 0))
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(manifest_info,
                         ''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in records))
    # Compression round trip and per-file hashes, independently of source hashing.
    with zipfile.ZipFile(path) as archive:
        for record in records:
            with archive.open(record['path']) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                    raise RuntimeError('Archive round-trip hash mismatch')
    with path.open('r+b') as stream:
        os.fsync(stream.fileno())
    return records


def reuse_part(rows, path):
    """Recover an upload interrupted before the durable per-part receipt."""
    expected = {name: (size, mtime) for name, size, mtime in rows}
    with zipfile.ZipFile(path) as archive:
        records = [json.loads(line) for line in archive.read('archive-file-manifest.jsonl').splitlines()]
        names = [r['path'] for r in records]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise RuntimeError('Existing temporary archive has different source membership')
        if set(archive.namelist()) != set(names) | {'archive-file-manifest.jsonl'}:
            raise RuntimeError('Unexpected temporary archive member')
        for record in records:
            source = verify_member_name(record['path'])
            stat = source.stat()
            if (stat.st_size, stat.st_mtime_ns) != expected[record['path']]:
                raise RuntimeError('Source changed while recovering archive')
            with archive.open(record['path']) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != record['sha256'] or actual != sha(source) or record['bytes'] != stat.st_size:
                raise RuntimeError('Temporary archive differs from original source')
    return records


def backup_locked(tag, part_mib):
    source = ROOT / 'artifacts/models'
    work = ROOT / 'artifacts/model-release-backup' / tag
    work.mkdir(parents=True, exist_ok=True)
    statepath = work / 'state.json'
    gh = Github()
    if statepath.exists():
        state = json.loads(statepath.read_text())
        if state['tag'] != tag or state['partMiB'] != part_mib:
            raise RuntimeError('Backup config changed')
        release = gh.call(API + '/releases/' + str(state['releaseId']))
        if state['status'] == 'COMPLETED':
            assets = {a['id']: a for a in gh.assets(release)}
            for part in state['parts']:
                gh.verify(assets[part['assetId']], part['sha256'], part['bytes'])
            print('[COMPLETED] Existing remote backup verified; no repackaging', flush=True)
            return
    else:
        commit = subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=ROOT, text=True).strip()
        release = gh.call(API + '/releases', 'POST', dict(
            tag_name=tag, target_commitish=commit, name='Lossless local model checkpoint archive ' + tag,
            draft=True, body='Upload in progress. Not a verified complete backup until manifest.json and completion marker are published.'))
        state = dict(schemaVersion=1, tag=tag, releaseId=release['id'], sourceCommit=commit,
                     startedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     partMiB=part_mib, status='INVENTORY', parts=[])
        atomic(statepath, state)
    with sqlite3.connect(work / 'inventory.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,bytes INTEGER,mtime_ns INTEGER,part INTEGER)')
        inventory(db, source)
        total, raw = db.execute('SELECT count(*),sum(bytes) FROM files').fetchone()
        if not total:
            raise RuntimeError('Empty model source')
        state.update(files=total, originalBytes=raw, status='UPLOADING')
        atomic(statepath, state)
        # After a crash reconcile durable uploaded parts before admitting new work.
        for part in state['parts']:
            db.executemany('UPDATE files SET part=? WHERE path=?',
                           ((part['number'], name) for name in part['paths']))
        db.commit()
        while True:
            rows, size = [], 0
            for row in db.execute('SELECT path,bytes,mtime_ns FROM files WHERE part IS NULL ORDER BY path'):
                rows.append(row)
                size += row[1]
                if size >= part_mib * 1024 ** 2:
                    break
            if not rows:
                break
            if shutil.disk_usage(work).free < size + 2 * 1024 ** 3:
                raise RuntimeError('Insufficient disk for bounded backup part; originals preserved')
            number = len(state['parts']) + 1
            path = work / f'models-{number:04d}.zip'
            print(f'[PACK] part={number} files={len(rows)} originalMiB={size/1024**2:.1f}', flush=True)
            if path.exists():
                try:
                    records = reuse_part(rows, path)
                except zipfile.BadZipFile:
                    # A half-written, never-uploaded compression temporary is disposable.
                    path.unlink()
                    records = build_part(rows, path)
            else:
                records = build_part(rows, path)
            print(f'[UPLOAD] part={number} compressedMiB={path.stat().st_size/1024**2:.1f}', flush=True)
            asset = gh.upload(release, path)
            part = dict(number=number, name=path.name, bytes=path.stat().st_size,
                        originalBytes=size, sha256=sha(path), files=len(records), assetId=asset['id'],
                        url=asset['browser_download_url'], paths=[r['path'] for r in records])
            state['parts'].append(part)
            state['verifiedFiles'] = sum(p['files'] for p in state['parts'])
            state['uploadedBytes'] = sum(p['bytes'] for p in state['parts'])
            atomic(statepath, state)
            db.executemany('UPDATE files SET part=? WHERE path=?', ((number, r['path']) for r in records))
            db.commit()
            # Only the exact disposable compressed file is removed, after remote verification.
            if path.resolve().parent != work.resolve():
                raise RuntimeError('Unexpected temporary archive location')
            path.unlink()
            print(f'[VERIFIED] part={number} files={state["verifiedFiles"]}/{total} uploadedGiB={state["uploadedBytes"]/1024**3:.2f}', flush=True)
        print('[VERIFY] Rechecking whole source inventory and remote assets', flush=True)
        seen = 0
        for folder, dirs, names in os.walk(source):
            for name in names:
                p = Path(folder) / name
                stored = db.execute('SELECT bytes,mtime_ns,part FROM files WHERE path=?',
                                    (p.relative_to(ROOT).as_posix(),)).fetchone()
                stat = p.stat()
                if not stored or stored[2] is None or stored[:2] != (stat.st_size, stat.st_mtime_ns):
                    raise RuntimeError('Source inventory changed; backup not complete')
                seen += 1
        if seen != total:
            raise RuntimeError('Source file count changed')
        assets = {a['id']: a for a in gh.assets(release)}
        for part in state['parts']:
            gh.verify(assets[part['assetId']], part['sha256'], part['bytes'])
        catalog = {k: v for k, v in state.items() if k not in ('status', 'parts')}
        catalog.update(status='COMPLETED', completedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       sourceRoot='artifacts/models', releaseUrl=f'https://github.com/{REPO}/releases/tag/{tag}',
                       scope='Every file present in artifacts/models inventory; other databases/datasets are not included',
                       parts=[{k: v for k, v in p.items() if k != 'paths'} for p in state['parts']])
        manifest = work / 'manifest.json'
        atomic(manifest, catalog)
        gh.upload(release, manifest)
        body = (f'Complete lossless backup: {total:,} files; {raw/1024**3:.3f} GiB original; '
                f'{state["uploadedBytes"]/1024**3:.3f} GiB compressed. '
                'Each ZIP has a per-file SHA-256 manifest. manifest.json records part hashes. '
                'Original files were not deleted. Databases/datasets outside artifacts/models are not included.')
        gh.call(API + '/releases/' + str(release['id']), 'PATCH', dict(draft=False, body=body))
        destination = ROOT / 'results/model-archives' / tag / 'manifest.json'
        if destination.exists() and destination.read_bytes() != manifest.read_bytes():
            raise RuntimeError('Existing published model manifest differs')
        atomic(destination, catalog)
        state.update(status='COMPLETED', completedAt=catalog['completedAt'])
        atomic(statepath, state)
        print('[COMPLETED] ' + catalog['releaseUrl'], flush=True)


def backup(tag, part_mib):
    import msvcrt
    work = ROOT / 'artifacts/model-release-backup' / tag
    work.mkdir(parents=True, exist_ok=True)
    with (work / 'backup.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            backup_locked(tag, part_mib)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def restore(manifest, destination):
    catalog = json.loads(manifest.read_text())
    if catalog['status'] != 'COMPLETED':
        raise RuntimeError('Refuse incomplete backup')
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    cache = destination / '.model-archive-download'
    cache.mkdir(exist_ok=True)
    for part in catalog['parts']:
        path = cache / part['name']
        if not path.exists() or sha(path) != part['sha256']:
            with urllib.request.urlopen(part['url'], timeout=300) as inp, path.open('wb') as out:
                shutil.copyfileobj(inp, out, 1024 * 1024)
        if path.stat().st_size != part['bytes'] or sha(path) != part['sha256']:
            raise RuntimeError('Downloaded archive hash mismatch')
        with zipfile.ZipFile(path) as archive:
            records = [json.loads(line) for line in archive.read('archive-file-manifest.jsonl').splitlines()]
            for row in records:
                relative = Path(row['path'])
                target = (destination / relative).resolve()
                allowed = (destination / 'artifacts/models').resolve()
                if not target.is_relative_to(allowed):
                    raise RuntimeError('Unsafe archive path')
                if target.exists():
                    if sha(target) != row['sha256']:
                        raise RuntimeError('Existing model differs: ' + str(target))
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + '.restoring')
                with archive.open(row['path']) as inp, temporary.open('wb') as out:
                    shutil.copyfileobj(inp, out, 1024 * 1024)
                    out.flush()
                    os.fsync(out.fileno())
                if temporary.stat().st_size != row['bytes'] or sha(temporary) != row['sha256']:
                    raise RuntimeError('Restored member hash mismatch')
                os.replace(temporary, target)
        path.unlink()
        print('[RESTORED] ' + part['name'], flush=True)


def push_catalog(tag):
    """Publish only the completed catalog, preserving unrelated working changes."""
    path = f'results/model-archives/{tag}/manifest.json'
    catalog = json.loads((ROOT / path).read_text())
    if catalog['status'] != 'COMPLETED':
        raise RuntimeError('Cannot push incomplete backup catalog')
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    if branch != 'main':
        raise RuntimeError('Catalog auto-push requires main; no branches switched')
    subprocess.run(['git', 'add', '--', path], cwd=ROOT, check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', path], cwd=ROOT).returncode
    if changed == 1:
        subprocess.run(['git', 'commit', '--only', '-m', 'Publish verified full model checkpoint archive catalog',
                        '--', path], cwd=ROOT, check=True)
    elif changed != 0:
        raise RuntimeError('Cannot inspect staged catalog')
    subprocess.run(['git', 'push', 'origin', 'main'], cwd=ROOT, check=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/main'], cwd=ROOT, text=True).split()[0]
    if head != remote:
        raise RuntimeError('Remote main changed during push; inspect catalog commit')
    atomic(ROOT / 'artifacts/model-release-backup' / tag / 'git-publication.json',
           dict(status='COMPLETED', commit=head, catalog=path, releaseUrl=catalog['releaseUrl']))
    print('[GIT-PUBLISHED] ' + head, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='models-backup-20261104')
    parser.add_argument('--part-mib', type=int, default=384)
    parser.add_argument('--restore', type=Path)
    parser.add_argument('--destination', type=Path, default=ROOT)
    parser.add_argument('--push-catalog', action='store_true', help='After verified completion, commit/push only the catalog')
    args = parser.parse_args()
    if args.restore:
        restore(args.restore, args.destination)
    else:
        if not 16 <= args.part_mib <= 1024 or not args.tag.replace('-', '').isalnum():
            parser.error('Use a simple tag and part size 16..1024 MiB')
        import ctypes
        # Prevent automatic idle sleep while the backup is doing disk/network IO.
        # Display sleep is still allowed; explicit user sleep/power loss is not handled.
        if not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
            raise RuntimeError('Cannot inhibit automatic idle sleep for backup')
        try:
            backup(args.tag, args.part_mib)
            if args.push_catalog:
                push_catalog(args.tag)
        except Exception as error:
            atomic(ROOT / 'artifacts/model-release-backup' / args.tag / 'blocker.json',
                   dict(status='BLOCKED', error=str(error),
                        at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
            print('[BLOCKED] ' + str(error), file=sys.stderr, flush=True)
            raise
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
