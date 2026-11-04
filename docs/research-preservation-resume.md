# Resumed research preservation (5 November 2026)

This is preservation only: no worker API training, scientific code changes,
result edits, original-file deletion, archive deletion or experiment reruns.
It resumes Release ID434068945 / tag `models-backup-20261104`. It never creates
a replacement release or overwrites the sealed 4 November synthesis publication.

## Initial audit

- Branch main, HEAD `301efa22c10620dfeaf3b4f4bfda8b727d764074`; existing final
  robustness implementation has uncommitted working changes, which are retained.
- Original model inventory:513,327 files /56,375,341,671 bytes. Six remote parts
  match previous recorded GitHub digests; those are **not** full-download proofs.
- Part7 is remote `starter`, with local `models-0007.zip`367,608,354 bytes,
  SHA256 `5dc8303c6352456f25b9f669b3d2c7f477c27388a45903bd254a029cc3ebb9ca`.
- Existing draft remains the destination. No verified asset is uploaded again.
- Additional workspace evidence includes databases, partition/dataset arrays,
  reports, runtime JARs, traces, logs, manifests and source/config snapshots.
- Disk17.56GiB free; available RAM about.43GiB at audit. Full archive caching
  would not fit. Future ZIP parts use a counting/hash pass followed by a bounded
  streaming upload pass (1MiB queue), with fixed timestamps and ordered names.
  Existing local ZIPs are reused and retained. No complete ZIP is kept in RAM.

Each independently restorable ZIP retains the established per-file
`archive-file-manifest.jsonl` with original paths/bytes/SHA256. New parts target
384MiB original content, with an enforced compressed limit below1.8GiB. A single
large database may exceed the original-content target; its compressed ZIP must
still pass the size guard. Source memberships are frozen before upload.

The expanded plan now contains524,035 files /67.746GiB original content and
171 ZIP parts:140 models,25 research-evidence,5 published-results,1 source/config.
208 source/config files have immutable local capsules; working changes are not
lost, and a later preservation-tool repair cannot alter the captured source.
Seven parts have been fully downloaded and verified at the initial resume
milestone. These counts are a progress snapshot, not a completion claim.

SQLite backups use SQLite's online backup API and `quick_check`, retain their
own checksum receipts, and restore to the original logical database paths.
WAL/SHM are excluded because committed data is represented by the consistent
snapshot. Snapshot files remain local; they are not cleaned up. An orphan or
changed raw SQLite/WAL identity is accepted only if an independently created
second backup is byte-identical; both copies and validation records are retained.
Different contents fail closed. No SQL writes are issued to source databases.

Credentials remain in memory through the existing Git credential helper.
`.env` files, key files, virtualenvs/build/dependency caches, PID/locks and this
preservation's own changing workspace are excluded. Common token/private-key
patterns in textual sources fail closed before upload. Personal files outside
the repository are not traversed. Never print a signed download URL or token.

## Commands (repository root)

Resume (safe to rerun):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_research_preservation.ps1 -Mode resume
```

Verify-only (re-download existing expected assets, never recreate archives):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_research_preservation.ps1 -Mode verify
```

Other modes: `audit`, `package`, `upload`, `status`. Package computes deterministic
part hashes without uploading or requiring complete local ZIP storage. A queued
source producer, one network upload, bounded socket/total deadlines and six
attempts limit resource usage and retries. Ambiguous uploads query asset listings
before retry. Only a `starter` placeholder belonging to the current exact part
can be removed automatically. Hash-mismatched uploaded evidence stops explicitly
for review, preserving local/remote copies and failed verification downloads.

Every part is fully retrieved into a temporary verification download and hashed;
server size/digest or HTTP success alone cannot create a PASS receipt. Failed
downloads remain local. Only a successful verification temporary is removed.
Full rechecks create new receipts instead of overwriting earlier proof.

Automatic idle sleep is inhibited during the command; display sleep is allowed.
Power loss, deliberate sleep, absent disk or incompatible source changes are not
repaired. Do not train or change evidence while a frozen inventory is uploading.

## Metadata and completion

Working directory:
`artifacts/model-release-backup/models-backup-20261104/preservation-v2/`.

- `preservation-audit.json`, plus dated `audits/`: initial/current inventories.
- `inventory.sqlite`: frozen membership, part plan, consistent snapshot mapping.
- `state.json`: expected parts and packaged part identities.
- `preservation-manifest.json`: groups, archive parts and SQLite snapshot receipts.
- `preservation-sha256.json` / `.txt`: part hashes and verification states.
- `verification-receipts/`: immutable downloaded-byte verification receipts.
- `upload.log`: append-only structured upload/failure log.
- `preservation-final-verification.json`: created only after all archive proofs.
- `preservation-upload-history.json`: exact original and current upload-log bytes
  through archive verification, with individual hashes and base64 encoding.
- `preservation-tool-source.py`: retained copy of the final preservation tool.
- `preservation-status.json`: explicit failure or final completion marker.

After all171 parts and six metadata assets have passed downloaded-byte SHA256 verification,
the existing draft is published and copies of final metadata are written into
the NEW `results/preservation-models-backup-20261104/` directory. The original
`results/research-synthesis-20261104/preservation-status.json` stays immutable as
a historical snapshot. Model bytes live in Release assets, not Git objects.

Until final verification and publication succeed, status is
**PRESERVATION INCOMPLETE**. A later local cleanup is a separate user task.
