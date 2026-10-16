# MiniFLS architecture

Source requirements: [Federated System implementation plan, 16 October 2026](https://app.notion.com/p/3fbb6ecc362380b29145ed0a5324deac).

Java is the authority for experiment state, eligibility, client selection, acceptance, aggregation weights, checkpoint versions and round commits. One executor runs one experiment at a time. SQLite stores the configuration, dataset manifest (including checksums and partition histograms), initial evaluation, client histories, and latest committed snapshot. Round metrics and snapshots commit together in a database transaction.

The source Git commit and dirty-working-tree flag are recorded at initialization. Runs during development must be identified as such; a commit ID alone does not identify uncommitted source changes.

The Python worker loads one shared memory-mapped dataset. It materializes only the active partition and trains a CPU MLP, 54 → 128 → 64 → 7 (15,751 parameters). Every job loads the round's immutable base checkpoint and constructs a fresh SGD optimizer. An exclusive lock protects initialization, training, evaluation and tensor aggregation. Start uvicorn with exactly one worker; running multiple worker processes defeats this concurrency guarantee.

Java sends JSON metadata and workspace-relative artifact paths over localhost HTTP. Python confines paths to `MINIFLS_WORKSPACE`, loads tensor checkpoints with `weights_only=True`, checks model schema/finite values, and atomically writes unique immutable artifacts. A fresh operation ID per round attempt keeps interrupted artifacts separate from retried jobs. Only artifact paths in committed SQLite snapshots are authoritative; orphan artifacts may remain after a crash.

## Round contract

1. Freeze the current checkpoint/version and observe availability.
2. Select up to K clients without replacement, using only profiles and prior history.
3. Train each selected client sequentially from the frozen base.
4. SimPy runs independent virtual-device events. CPU capacity scales measured training duration; configured jitter, RAM feasibility, dropout and deadline determine outcomes.
5. Accept only completed, in-deadline updates matching experiment, round, base version, client and partition sample count.
6. Java computes FedAvg sample weights or FedLBW inverse proxy-loss weights. Python validates every accepted checkpoint again and averages tensors.
7. Evaluate on held-out test, persist round evidence and snapshot atomically, then advance.

No accepted update produces `SKIPPED`, leaves the model version unchanged, and advances the round counter. Worker/transport/validation failures produce `FAILED`; resume replays the uncommitted round from the last snapshot. On Java restart, formerly `RUNNING` experiments become `INTERRUPTED`. Configurations and committed rounds cannot be edited through the API.

## Timing and resources

Physical training is sequential. Virtual client devices are parallel: the round uses the maximum completion/cutoff time, plus measured aggregation and proxy-evaluation overhead. Wall time is recorded separately. Test evaluation is an observer operation and is excluded from virtual federated time.

CPU scaling is an initial proportional model, not a calibrated physical-device claim. `requiredRamMb` is an explicit scenario estimate, not the worker RSS. The worker reports current/peak process RSS separately. LOW/MEDIUM/HIGH CPU factors are 0.5/1/2; RAM is 512/1024/2048 MB; counts are 40/40/20 at 100 clients. Profiles are assigned independently of partition labels. Use measured benchmark results to choose realistic time and RAM assumptions before drawing resource-efficiency conclusions.

Random selection uses seeded uniform sampling. Resource-aware selection filters estimated RAM/deadline feasibility, explores a configured fraction, and ranks remaining clients by expected completion time adjusted by historical completion reliability. Cold clients use a configured per-sample prior. This is a documented heuristic, not Oort or a theoretical fairness guarantee.

FedLBW uses the separate server proxy split. This implementation clamps nonnegative proxy loss to 1e-12 before inverse-loss normalization and rejects nonfinite/negative loss. Covertype evaluation is an extension benchmark, not a reproduction of the paper's dataset experiments.
