# Measured storage estimate v2

The user authorized full admission with about40GiB free, asking whether the
56.3GiB estimate was excessive. Replaced the unmeasured500KB checkpoint allowance
with a measured, conservative allowance; no integrity/provenance check was removed.

Read-only measurements of the completed prior Covertype study:

- 800 checkpoint files from20 completed experiments: every sample196669 bytes.
- Maximum associated receipt850 bytes; combined bound197519 bytes.
- 11,554 SQLite round rows: mean JSON length126121, maximum159164 bytes.
- Sample dataset assignment138325810 bytes including manifest/arrays.

New planning allowances:300000 bytes per local/global checkpoint+receipt,
220000 bytes per SQLite round,160MiB per dataset assignment,256MiB for other
reports/build/log overhead, four audit rounds and the unchanged8GiB protected
free-space reserve. K5/225x70 yields **39.3GiB**, versus40.4GiB free at execution.
The checkpoint allowance retains over50% measured headroom; the row allowance
over38%. Filesystem size and future unrelated disk writes remain uncertain;
existing per-run8GiB disk checks continue to stop safely if capacity falls.

`preflight.json` records storageEstimateVersion=measured-mlp47879-v2 and all
component bounds. The model architecture/training protocol is unchanged.

Python unit suite: **55 passed**, including exact matrix/admission counts, the
40GiB pass estimate,38GiB insufficient case and retained8GiB reserve. Java
scientific code/JAR is unchanged; Gradle bootJar preflight build is up-to-date.
The actual Java IDE main executed preflight only and exited successfully:
`full:225x70; full disk estimate39.3GiB; free40.4GiB; admission225 runs`.
No training was started by this verification.

The earlier blocked batch `fuzzy-uncertainty-20261104-001556-81e087` contained
zero experiments/rounds. It and its identities/logs were preserved unchanged.
A successor `fuzzy-uncertainty-20261104-002235-69ac39` pins the revised source;
its scientific protocol bytes match the predecessor exactly. The active pointer
now selects this successor. `supersedes-unstarted-batch.json` and
`previous-active-batch.json` retain the relationship and prior ledger hash.
No existing source identity was rewritten to disguise a mismatch.

The user can keep the manual worker running and Run Controlled Fuzzy Ablation
Full again in IntelliJ. It still admits all225 research runs at70 rounds each,
plus two2-round reproducibility audits, without the separate40-run pilot.
