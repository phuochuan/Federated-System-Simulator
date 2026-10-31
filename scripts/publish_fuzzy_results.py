"""Publish a frozen fuzzy-workflow report snapshot without changing local evidence.

Large CSVs and streamed SQLite exports use gzip. Model binaries and database
files remain local. Existing publications are never replaced.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    pointer = ROOT / "artifacts/research/fuzzy-uncertainty/active-batch.json"
    batch = Path(json.loads(pointer.read_text(encoding="utf-8"))["folder"]).resolve()
    if not batch.is_relative_to((ROOT / "artifacts/research").resolve()):
        raise ValueError("Batch must stay within workspace research artifacts")
    destination = ROOT / "results/research" / batch.name
    if destination.exists():
        raise FileExistsError(f"Publication already exists: {destination}")
    status = json.loads((batch / "status.json").read_text(encoding="utf-8"))
    state = json.loads((batch / "batch-manifest.json").read_text(encoding="utf-8"))
    if any(r["status"] == "RUNNING" for r in state["runs"].values()):
        raise RuntimeError("Stop active training before taking a report publication snapshot")
    sources = [p for p in batch.iterdir() if p.is_file() and p.suffix in (".json", ".csv", ".md")]
    for name in ("traces", "replay-cache", "dataset-identities", "completed-artifact-identities", "initial-model-identities"):
        sources.extend((batch / name).rglob("*.json"))
    source_hashes = {p: sha256(p) for p in sorted(sources)}
    destination.mkdir(parents=True)
    records = []
    for path, original_hash in source_hashes.items():
        relative = path.relative_to(batch)
        compress = path.stat().st_size > 5*1024**2
        target = destination / (str(relative) + ".gz" if compress else str(relative))
        target.parent.mkdir(parents=True, exist_ok=True)
        if compress:
            with path.open("rb") as source, target.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as out:
                    shutil.copyfileobj(source, out)
            with gzip.open(target, "rb") as restored:
                if hashlib.file_digest(restored, "sha256").hexdigest() != original_hash:
                    raise RuntimeError(f"Compressed evidence verification failed: {relative}")
        else:
            shutil.copyfile(path, target)
            if sha256(target) != original_hash:
                raise RuntimeError(f"Copied evidence verification failed: {relative}")
        records.append(dict(path=target.relative_to(destination).as_posix(), bytes=target.stat().st_size,
            sha256=sha256(target), sourcePath=path.relative_to(ROOT).as_posix(), sourceSHA256=original_hash,
            compression="gzip" if compress else None))
    print(f"Verified {len(records)} report/provenance files", flush=True)
    with sqlite3.connect((batch / "experiments.db").as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        if db.execute("SELECT count(*) FROM experiments WHERE status='RUNNING'").fetchone()[0]:
            raise RuntimeError("An experiment became active during publication")
        experiment_count = db.execute("SELECT count(*) FROM experiments").fetchone()[0]
        round_count = db.execute("SELECT count(*) FROM rounds").fetchone()[0]
        exports = [
            ("experiments.jsonl.gz", "SELECT id,status,config,snapshot,error FROM experiments ORDER BY id",
             lambda row: dict(experimentId=row[0], status=row[1], config=json.loads(row[2]),
                              snapshot=json.loads(row[3]) if row[3] else None, error=row[4])),
            ("rounds.jsonl.gz", "SELECT experiment_id,round_id,metrics FROM rounds ORDER BY experiment_id,round_id",
             lambda row: dict(experimentId=row[0], roundId=row[1], metrics=json.loads(row[2])))
        ]
        for name, query, convert in exports:
            target = destination / name
            count = 0
            with target.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as stream:
                for row in db.execute(query):
                    stream.write((json.dumps(convert(row), separators=(",", ":"), allow_nan=False) + "\n").encode())
                    count += 1
            with gzip.open(target, "rt", encoding="utf-8") as stream:
                verified = sum(1 for line in stream if json.loads(line))
            if count != verified:
                raise RuntimeError(f"Stream export count mismatch: {name}")
            records.append(dict(path=name, bytes=target.stat().st_size, sha256=sha256(target), records=count,
                                compression="gzip", sourcePath=(batch / "experiments.db").relative_to(ROOT).as_posix()))
            print(f"Verified {name}: {count} records, {target.stat().st_size/1024**2:.1f} MiB", flush=True)
    for path, original_hash in source_hashes.items():
        if sha256(path) != original_hash:
            raise RuntimeError(f"Source changed while publishing: {path}")
    if any(r["bytes"] >= 100*1024**2 for r in records):
        raise RuntimeError("A publication file exceeds GitHub's normal Git size limit")
    stage_counts = {}
    for run in state["runs"].values():
        key = f'{run["stage"]}/{run["status"]}'
        stage_counts[key] = stage_counts.get(key, 0) + 1
    lock = json.loads((batch / "policy-lock.json").read_text(encoding="utf-8"))
    publication = dict(schemaVersion=1, sourceBatch=batch.relative_to(ROOT).as_posix(),
        publicationType="PILOT_RESULTS_WITH_CONFIRMATION_STATUS", workflowStatus=status["workflowStatus"],
        stage=status["stage"], lastError=status.get("lastError"), experiments=experiment_count,
        committedRounds=round_count, stageCounts=stage_counts, lockedPolicies=lock["policies"],
        excluded=["Model checkpoint binaries", "Java JAR", "SQLite database/WAL/SHM", "Dataset arrays", "Process logs/locks"], files=records)
    write_json(destination / "publication-manifest.json", publication)
    readme = f"""# Covertype fuzzy uncertainty pilot results

This snapshot publishes the completed pilot: **{experiment_count} experiments,
{round_count} committed rounds** (2 two-round audit runs, 24 E2 runs and six E4
runs of 70 rounds). All learning metrics from this pilot use the **proxy** split.

The subsequent full-mode attempt is **{status['workflowStatus']} at {status['stage']}**:
{status.get('lastError')}

**No E3 held-out confirmation run has started.** `completion.json` records pilot
completion only. `e3-heldout-results.json` is a workflow report containing the
available pilot records and incomplete confirmation status, not held-out results.

- [Research summary](fuzzy-mcdm-research-summary.md)
- [E2 results](e2-robustness-results.csv)
- [E4 calibration](e4-calibration-results.md)
- [Immutable policy lock](policy-lock.json): {', '.join(lock['policies'])}
- [Current execution status](status.json)
- [Publication checksums](publication-manifest.json)

`rounds.jsonl.gz` contains all committed per-round evidence; `experiments.jsonl.gz`
contains configurations and final snapshots. `e0-observations.csv.gz` preserves
the full observations CSV, including the historical evidence used by E0.
Gzip files can be decompressed with standard gzip tools or Python's `gzip` module.
The publication manifest records compressed checksums and original file hashes;
compressed CSV verification checks the decompressed bytes against the source.
Dataset identities, paired traces, replay coefficients and runtime/build/source
identities are included. Referenced dataset arrays, model binaries and the local
SQLite database are retained locally and are not part of this report publication.

The C5 validation screen passed; it is not statistical evidence of superiority.
The policy lock was chosen using validation only. Existing F/L/E/Pareto
publications are unchanged.
"""
    (destination / "README.md").write_text(readme, encoding="utf-8")
    print(f"Publication ready: {destination}", flush=True)


if __name__ == "__main__":
    main()
