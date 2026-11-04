# Completed controlled fuzzy uncertainty ablation

Completed 4 November 2026: **225 research runs x 70 rounds**, plus two
2-round reproducibility audits: **227 runs / 15754 committed rounds**.
All five policies A0-A4 were retained across alpha 0.1/0.5/1.0, independent client
assignment seeds 6001/6002/6003 and paired training seeds 42-46 under U0.

- [Research report](controlled-fuzzy-ablation-report.md)
- [Results and partition-aware paired differences](controlled-ablation-results.json)
- [Run results CSV](run-results.csv) and [paired differences CSV](paired-differences.csv)
- [Figures](figures/accuracy-rounds.png)
- [Protocol](protocol.json), [full policy lock](full-policy-lock.json)
- [Integrity report](integrity-report.json) and [completion marker](completion.json)
- [Publication checksums](publication-manifest.json)

This was the user-requested full predeclared study without the separate 40-run
Covertype pilot. It is not labeled pilot-validated confirmation. Final held-out
evaluation occurs only at the last round; trajectories use proxy data. The fixed
underlying test examples had been inspected in prior research. Seeds within one
partition are repeated measurements, not independent partition replications.

A1 zero-width fuzzy is the primary control for A2/A3/A4. A0 conventional Crisp
is a formulation reference. Results retain positive, negative and tied effects;
workflow completion alone does not establish superiority.

`experiments.jsonl.gz` preserves all SQLite experiment rows, including config and
snapshot JSON strings. `rounds-part-*.jsonl.gz` preserves all committed round rows,
at most 1,000 rows per part, ordered by experiment ID and round. Decompress with
Python's standard gzip module. The manifest records each exported SHA-256 and
record count. Reports, original dataset manifests, paired traces, replay inputs,
scores/widths, figures, executing source snapshot and runtime identities are included.
Source snapshots retain exact executing bytes regardless of Git newline settings.

Model binaries, dataset arrays, coordinator JAR, SQLite/WAL/SHM and process logs
remain local. This is an analysis evidence publication, not a standalone resume
package. Original local artifact references are preserved. Earlier publications
are not overwritten or pooled into this controlled study.
