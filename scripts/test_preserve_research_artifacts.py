import hashlib
import io
import json
import sqlite3
from pathlib import Path
import zipfile

import pytest

import preserve_research_artifacts as p


def rows(tmp_path, monkeypatch):
    monkeypatch.setattr(p, 'ROOT', tmp_path)
    path = tmp_path / 'artifacts/models/model.pt'
    path.parent.mkdir(parents=True)
    path.write_bytes(bytes(range(256))*400)
    stat = path.stat()
    return [('artifacts/models/model.pt', 'artifacts/models/model.pt', stat.st_size, stat.st_mtime_ns)]


def test_two_pass_zip_matches_and_restores(tmp_path, monkeypatch):
    source = rows(tmp_path, monkeypatch)
    expected = p.zip_stream(source, p.Sink())
    producer = p.ZipBody(source, expected)
    try:
        data = b''.join(iter(lambda: producer.read(8192), b''))
    finally:
        producer.close()
    assert len(data) == expected['bytes']
    assert hashlib.sha256(data).hexdigest() == expected['sha256']
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read(source[0][0]) == (tmp_path / source[0][0]).read_bytes()
        assert len(archive.read('archive-file-manifest.jsonl').splitlines()) == 1


def test_changed_source_and_secrets_fail(tmp_path, monkeypatch):
    source = rows(tmp_path, monkeypatch)
    (tmp_path / source[0][0]).write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='changed since inventory'):
        p.zip_stream(source, p.Sink())
    path = tmp_path / 'secret.log'
    path.write_text('ghp_' + 'a'*35)
    stat = path.stat()
    with pytest.raises(RuntimeError, match='Potential secret'):
        p.zip_stream([('secret.log', 'secret.log', stat.st_size, stat.st_mtime_ns)], p.Sink())


def test_remote_bytes_required_and_failed_download_retained(tmp_path, monkeypatch):
    monkeypatch.setattr(p, 'WORK', tmp_path / 'work')
    monkeypatch.setattr(p, 'ROOT', tmp_path)
    content = b'actual remote content'
    class Response(io.BytesIO):
        headers = {'Content-Type': 'application/octet-stream'}
    class Opener:
        def open(self, request, timeout):
            return Response(content)
    monkeypatch.setattr(p.urllib.request, 'build_opener', lambda *args: Opener())
    gh = type('GH', (), {'headers': {}})()
    asset = dict(name='part.zip', size=len(content), state='uploaded', id=1, url='https://example.com/asset', digest='sha256:irrelevant')
    part = dict(name='part.zip', bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    result = p.download_verify(gh, asset, part)
    assert result['method'] == 'FULL_REMOTE_DOWNLOAD_SHA256'
    assert not list((p.WORK/'verification-downloads').iterdir())
    receipt = (p.WORK/'verification-receipts/part.zip.1.json').read_bytes()
    p.download_verify(gh, asset, part)
    assert (p.WORK/'verification-receipts/part.zip.1.json').read_bytes() == receipt
    with pytest.raises(RuntimeError, match='checksum mismatch'):
        p.download_verify(gh, asset, dict(part, sha256='0'*64))
    assert list((p.WORK/'verification-downloads').iterdir())
    assert json.loads((p.WORK/'failed-verification.json').read_text())['status'] == 'FAIL'


def test_sqlite_orphan_revalidation_and_original_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(p, 'ROOT', tmp_path)
    monkeypatch.setattr(p, 'WORK', tmp_path/'work')
    source = tmp_path/'source.db'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE evidence(value TEXT)')
        db.execute('INSERT INTO evidence VALUES("original")')
    snapshot = p.WORK/'sqlite-snapshots/source.db'
    p.sqlite_copy(source,snapshot)
    before = p.sha(snapshot)
    assert p.sqlite_snapshot(source,'source.db') == snapshot
    assert p.sha(snapshot) == before
    assert list((p.WORK/'sqlite-revalidation').rglob('*.sqlite'))
    with sqlite3.connect(source) as db:
        db.execute('INSERT INTO evidence VALUES("new")')
    with pytest.raises(RuntimeError,match='differs from fresh source'):
        p.sqlite_snapshot(source,'source.db')
    assert p.sha(snapshot) == before


def test_frozen_source_survives_preservation_tool_repair(tmp_path, monkeypatch):
    monkeypatch.setattr(p, 'ROOT', tmp_path)
    monkeypatch.setattr(p, 'WORK', tmp_path/'work')
    monkeypatch.setattr(p, 'state_read', lambda: {'sourceGitHead':'test'})
    p.WORK.mkdir()
    source=tmp_path/'tool.py'
    source.write_bytes(b'original source')
    stat=source.stat()
    with sqlite3.connect(p.WORK/'inventory.sqlite') as db:
        db.execute('CREATE TABLE files(path TEXT,physical TEXT,bytes INTEGER,mtime INTEGER,grp TEXT)')
        db.execute('INSERT INTO files VALUES(?,?,?,?,?)',('tool.py','tool.py',stat.st_size,stat.st_mtime_ns,'source-and-config'))
    p.freeze_sources()
    source.write_bytes(b'repaired preservation tooling')
    p.freeze_sources()
    with sqlite3.connect(p.WORK/'inventory.sqlite') as db:
        physical=db.execute('SELECT physical FROM files').fetchone()[0]
    assert (tmp_path/physical).read_bytes()==b'original source'
