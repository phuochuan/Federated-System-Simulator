"""Publish result evidence and final checkpoints; restore archives without retraining."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts"
DEST = ROOT / "results"
PART_BYTES = 48 * 1024 * 1024
GROUPS = ("research", "comparisons", "seed45-audit", "fairness-matched", "results",
          "benchmarks", "validation", "research-smoke", "pareto-smoke", "fuzzy-smoke",
          "lambda-smoke", "e2e", "matrix-smoke", "worker-retry-smoke", "logging-smoke", "logs")
REPORT_EXTENSIONS = {".json", ".csv", ".txt", ".md", ".png", ".svg", ".properties"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def restore():
    manifest = json.loads((DEST / "archive-manifest.json").read_text(encoding="utf-8"))
    for archive in manifest["archives"]:
        print("Restoring", archive["name"], flush=True)
        with tempfile.TemporaryFile() as joined:
            for part in archive["parts"]:
                path = DEST / part["path"]
                if digest(path) != part["sha256"]:
                    raise ValueError(f"Checksum mismatch: {path}")
                with path.open("rb") as source:
                    shutil.copyfileobj(source, joined)
            joined.seek(0)
            with zipfile.ZipFile(joined) as bundle:
                if bundle.testzip() is not None:
                    raise ValueError(f"Corrupt archive: {archive['name']}")
                for member in bundle.infolist():
                    target = (ROOT / member.filename).resolve()
                    if not target.is_relative_to(SOURCE.resolve()):
                        raise ValueError(f"Archive path outside artifacts: {member.filename}")
                    if target.exists():
                        with bundle.open(member) as stream:
                            h = hashlib.file_digest(stream, "sha256").hexdigest()
                        if digest(target) != h:
                            raise FileExistsError(f"Existing evidence differs: {target}; restore into a clean clone")
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as stream, target.open("wb") as out:
                        shutil.copyfileobj(stream, out)
    print("Verified and restored all archived evidence.")


def package():
    if (DEST / "archive-manifest.json").exists():
        raise FileExistsError("Results package already exists; use a fresh output for a new publication")
    (DEST / "raw").mkdir(parents=True, exist_ok=True)
    manifest = {"schemaVersion": 1, "scope": "All available report/round evidence, consistent SQLite backups and final completed-run checkpoints",
                "excluded": ["Dataset arrays (artifacts/partitions)", "Intermediate model checkpoints and worker operation caches (artifacts/models)",
                             "Ephemeral SQLite WAL/SHM files and process PID files"], "archives": []}
    checkpoints = set()
    missing = []
    with tempfile.TemporaryDirectory(prefix="minifls-results-", dir=SOURCE) as temporary:
        work = Path(temporary)
        groups = [(name, sorted(p for p in (SOURCE / name).rglob("*") if p.is_file()
                               and not p.name.endswith((".db-wal", ".db-shm", ".pid"))))
                  for name in GROUPS if (SOURCE / name).exists()]
        groups.append(("root-databases", sorted(SOURCE.glob("*.db"))))
        for name, paths in groups:
            if not paths:
                continue
            for path in paths:
                if path.suffix == ".db":
                    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                        if source.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='experiments'").fetchone()[0]:
                            for (checkpoint,) in source.execute("SELECT json_extract(snapshot,'$.checkpointPath') FROM experiments WHERE status='COMPLETED'"):
                                if checkpoint:
                                    candidate = (ROOT / checkpoint).resolve()
                                    if candidate.is_relative_to((SOURCE / "models").resolve()):
                                        checkpoints.add(candidate)
            print(f"Packaging {name}: {len(paths)} files", flush=True)
            archive_path = work / f"{name}.zip"
            existing = sorted((DEST / "raw").glob(f"{name}.zip*"))
            if existing:
                with archive_path.open("wb") as out:
                    for part in existing:
                        with part.open("rb") as stream:
                            shutil.copyfileobj(stream, out)
                records = []
                with zipfile.ZipFile(archive_path) as archive:
                    expected = {path.relative_to(ROOT).as_posix() for path in paths}
                    if set(archive.namelist()) != expected:
                        raise ValueError(f"Existing archive contents differ: {name}")
                    for member in archive.infolist():
                        with archive.open(member) as stream:
                            h = hashlib.file_digest(stream, "sha256").hexdigest()
                        records.append({"path": member.filename, "bytes": member.file_size,
                                        "sha256": h, "sqliteBackup": member.filename.endswith('.db')})
                publish_archive(name, archive_path, records, manifest)
                print(f"  Reused verified archive {name}", flush=True)
                continue
            records = []
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for index, path in enumerate(paths):
                    relative = path.relative_to(ROOT)
                    archived = path
                    if path.suffix == ".db":
                        archived = work / f"snapshot-{index}.db"
                        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                            with closing(sqlite3.connect(archived)) as target:
                                source.backup(target)
                    archive.write(archived, relative.as_posix())
                    records.append({"path": relative.as_posix(), "bytes": archived.stat().st_size,
                                    "sha256": digest(archived), "sqliteBackup": path.suffix == ".db"})
                    if (path.suffix in REPORT_EXTENSIONS and not {"runs", "traces"}.intersection(relative.parts)
                            and ("recovery" not in relative.parts or path.name in {"verification.json", "candidate-identity.json"})):
                        readable = DEST / path.relative_to(SOURCE)
                        readable.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, readable)
            publish_archive(name, archive_path, records, manifest)
        print(f"Packaging final checkpoints: {len(checkpoints)} referenced", flush=True)
        archive_path = work / "final-checkpoints.zip"
        records = []
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(checkpoints):
                if not path.exists():
                    missing.append(path.relative_to(ROOT).as_posix())
                    continue
                relative = path.relative_to(ROOT).as_posix()
                archive.write(path, relative)
                records.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest(path)})
        publish_archive("final-checkpoints", archive_path, records, manifest)
    manifest["missingHistoricalCheckpointPaths"] = missing
    (DEST / "archive-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Published {len(manifest['archives'])} archives; {len(missing)} unavailable historical checkpoints", flush=True)


def publish_archive(name, archive_path, records, manifest):
    parts = []
    size = archive_path.stat().st_size
    with zipfile.ZipFile(archive_path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Archive verification failed: {bad}")
    with archive_path.open("rb") as stream:
        number = 1
        while block := stream.read(PART_BYTES):
            suffix = "" if size <= PART_BYTES else f".{number:03d}"
            part = DEST / "raw" / f"{name}.zip{suffix}"
            part.write_bytes(block)
            parts.append({"path": part.relative_to(DEST).as_posix(), "bytes": len(block), "sha256": hashlib.sha256(block).hexdigest()})
            number += 1
    manifest["archives"].append({"name": name, "zipSha256": digest(archive_path), "parts": parts, "files": records})
    print(f"  Verified {name}: {size / 1024**2:.1f} MiB in {len(parts)} part(s)", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true", help="Verify archives and restore artifacts into a clean clone")
    args = parser.parse_args()
    restore() if args.restore else package()
