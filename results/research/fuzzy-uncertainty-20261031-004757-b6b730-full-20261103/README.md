# Completed fuzzy MCDM full evaluation

Completed 3 November 2026: **167/167 runs and 11,554 committed rounds**.
E3 contains **135 held-out runs x 70 rounds = 9,450 rounds**, comparing the
locked C1/C4/C5 policies under U0 across alpha 0.1/0.5/1.0, partition seeds
3001/3002/3003 and training seeds 42-46. Earlier audit/E2/E4 account for
32 runs and 2,104 rounds. No failed or pending runs remain.

- [Consolidated research report](fuzzy-mcdm-research-summary.md)
- [E3 held-out results](e3-heldout-results.json)
- [Policy lock](policy-lock.json) and [confirmation protocol](confirmation-protocol.json)
- [Completion marker](completion.json) and [status](status.json)
- [Plot data index](plot-data-index.json)
- [File checksums](publication-manifest.json)

This is a separate completed publication; the earlier pilot snapshot and legacy
F/L/Pareto publications remain unchanged. E3 evaluates generalization under U0.
A separate held-out U0/U1/U2 robustness study has not been run.

`experiments.jsonl.gz` preserves database rows including configurations and final
snapshots. `rounds-part-*.jsonl.gz` preserves all 11,554 committed round rows,
ordered by experiment ID and round, split into at most 1,000 rows per file.
Fields containing original JSON remain JSON strings as stored in SQLite.
`e0-observations.csv.gz` decompresses to the original observations CSV referenced
by the plot index. Gzip files can be read with Python's standard `gzip` module.
The manifest records byte lengths and SHA-256; copied/compressed source files
also record their original SHA-256. Dataset manifests, paired scenario traces,
replay evidence and runtime/source/build identities are included.

SQLite databases, dataset arrays, model checkpoints, executable JAR and process
logs remain local. This publication is evidence for analysis, not a standalone
checkpoint-resume package. Original artifact references are preserved.
Final held-out metrics use final checkpoints; trajectory metrics use proxy data.
No superiority claim follows from workflow completion alone.
