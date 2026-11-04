# Full local model checkpoint backup

`artifacts/models` contains model binaries and idempotency receipts that the
earlier analysis publications did not include. Do not delete that directory
based only on the earlier result publications.

The lossless backup tool uploads bounded, independently restorable ZIP files to
a GitHub Release of this repository. It does not add tens of GiB to Git history.
Each ZIP includes `archive-file-manifest.jsonl` with original paths, sizes and
SHA-256 hashes. The release's `manifest.json` records every ZIP hash and count.
The catalog is also copied into `results/model-archives/<tag>/manifest.json`
only after all model files and remote assets have passed verification.

Run or resume the same backup from repository root:

```powershell
.\.venv\Scripts\python.exe -u scripts/archive_models_release.py --tag models-backup-20261104 --part-mib 384 --push-catalog
```

The existing Git credential helper supplies authentication in memory. No token
is written to state, logs, catalogs or source files. Local progress is saved in
`artifacts/model-release-backup/models-backup-20261104/state.json`; a SQLite
inventory records source sizes and modification times. One backup owns an OS
file lock. A crash resumes previously verified parts without repeating them.
Do not run training or modify model files during the backup: changes fail closed.

The release stays **draft** until every inventory file is archived, ZIP contents
round-trip with matching SHA-256, every uploaded part matches its remote SHA-256
(or a streamed download when GitHub omits a digest), and the complete source
inventory is rechecked. Only then is the complete catalog uploaded and the
release published. Interrupted or draft uploads are not complete backups.

Only the disposable compressed ZIP is removed locally after remote verification
and durable state save. Original model/checkpoint/receipt files are never deleted.
The tool needs space for one bounded compressed part plus inventory and reserve.
Databases, dataset arrays, coordinator JARs and other files outside
`artifacts/models` are not part of this archive. A full training-resume package
also needs those separate experiment/runtime artifacts.

`--push-catalog` commits/pushes only the completed catalog on `main`, preserving
unrelated working changes. It verifies the remote branch and saves
`git-publication.json` beside local state. It never force-pushes or switches
branches. If publication fails, resume the same command; already completed
backup parts are verified and reused. Git credentials and network must remain
available throughout the job. Keep the computer awake and do not start training
until the model snapshot completes.

Restore into a fresh directory with sufficient disk capacity:

```powershell
.\.venv\Scripts\python.exe scripts/archive_models_release.py --restore results/model-archives/models-backup-20261104/manifest.json --destination D:\restored-federated-evidence
```

Restoration downloads one part at a time, verifies the compressed hash, verifies
each restored file's original hash, rejects paths outside `artifacts/models`,
and refuses to overwrite existing files with different contents. Matching
existing files are reused. A failed/incomplete restored file has a `.restoring`
suffix until verified and atomically renamed. Restoration does not train models.

Check completion using the **published** release, its complete manifest and
`state.json` status `COMPLETED`. Source cleanup is a separate action after
backup completion; it is not performed by this tool.
