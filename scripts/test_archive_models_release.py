import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('archive_models', Path(__file__).with_name('archive_models_release.py'))
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'ROOT', tmp_path)
    source = tmp_path / 'artifacts/models/example/model.pt'
    source.parent.mkdir(parents=True)
    source.write_bytes(bytes(range(256)) * 100)
    stat = source.stat()
    return source, [('artifacts/models/example/model.pt', stat.st_size, stat.st_mtime_ns)]


def test_round_trip_and_existing_evidence(tmp_path, monkeypatch):
    source, rows = fixture(tmp_path, monkeypatch)
    part = tmp_path / 'models-0001.zip'
    records = backup.build_part(rows, part)
    assert backup.reuse_part(rows, part) == records
    with zipfile.ZipFile(part) as archive:
        assert json.loads(archive.read('archive-file-manifest.jsonl')) == records[0]
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(dict(status='COMPLETED', parts=[dict(
        name=part.name, sha256=backup.sha(part), bytes=part.stat().st_size, url=part.as_uri())])))
    destination = tmp_path / 'restored'
    backup.restore(manifest, destination)
    target = destination / rows[0][0]
    assert target.read_bytes() == source.read_bytes()
    backup.restore(manifest, destination)
    target.write_bytes(b'different evidence')
    with pytest.raises(RuntimeError, match='Existing model differs'):
        backup.restore(manifest, destination)


def test_source_mutation_fails_closed(tmp_path, monkeypatch):
    source, rows = fixture(tmp_path, monkeypatch)
    part = tmp_path / 'original.zip'
    backup.build_part(rows, part)
    source.write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='Source changed'):
        backup.reuse_part(rows, part)
    with pytest.raises(RuntimeError, match='changed since inventory'):
        backup.build_part(rows, tmp_path / 'bad.zip')
    assert source.read_bytes() == b'changed'


def test_remote_digest_and_path_guards(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    github = backup.Github.__new__(backup.Github)
    github.verify(dict(size=12, state='uploaded', name='part', digest='sha256:abc'), 'abc', 12)
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        github.verify(dict(size=12, state='uploaded', name='part', digest='sha256:bad'), 'abc', 12)
    with pytest.raises(RuntimeError, match='outside models'):
        backup.verify_member_name('artifacts/models/../../outside')
