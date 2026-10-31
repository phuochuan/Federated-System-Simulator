# Covertype fuzzy uncertainty pilot results

This snapshot publishes the completed pilot: **32 experiments,
2104 committed rounds** (2 two-round audit runs, 24 E2 runs and six E4
runs of 70 rounds). All learning metrics from this pilot use the **proxy** split.

The subsequent full-mode attempt is **BLOCKED at E3**:
Insufficient disk for budgeted confirmation: require about 19.9 GiB free; lower admission budget or add capacity

**No E3 held-out confirmation run has started.** `completion.json` records pilot
completion only. `e3-heldout-results.json` is a workflow report containing the
available pilot records and incomplete confirmation status, not held-out results.

- [Research summary](fuzzy-mcdm-research-summary.md)
- [E2 results](e2-robustness-results.csv)
- [E4 calibration](e4-calibration-results.md)
- [Immutable policy lock](policy-lock.json): C1, C4, C5
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
