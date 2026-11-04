# Controlled fuzzy uncertainty ablation

Evidence status: COMPLETED. Completed research runs: 225/225.

Execution design: full predeclared ablation without the separate Covertype pilot, at user request. All five policies/parameters were fixed before execution; this is not pilot-validated confirmation. See full-policy-lock.json.

A1-A4 share the unchanged production fuzzy scoring engine. Only TFN widths vary. A0 is a formulation reference. Criteria/feasibility are identical on fixed replay states; end-to-end histories may diverge as a treatment effect.

## Does Fuzzy Uncertainty Improve Federated Learning Client Selection?

A2 had lower mean final accuracy than A1 (difference -0.002564; mixed or tied partition effects). A3 had lower mean final accuracy than A1 (difference -0.001283; mixed or tied partition effects). A4 had lower mean final accuracy than A1 (difference -0.007334; same direction across recorded partitions). These are observed paired effects under this protocol, not a claim of statistical superiority or universal benefit. See Macro-F1, stability, efficiency and partition uncertainty before drawing a research conclusion.

## Paired evidence (treatment minus control)

| Contrast | Accuracy mean | Positive / negative / tied | Independent partitions |
| --- | --- | --- | --- |
| A2-A1 | -0.0025637347989803205 | 14 / 26 / 5 | 3 |
| A3-A1 | -0.0012830148266715542 | 17 / 25 / 3 | 3 |
| A4-A1 | -0.0073337808299340805 | 22 / 23 / 0 | 3 |
| A3-A2 | 0.001280719972308766 | 21 / 21 / 3 | 3 |
| A4-A3 | -0.0060507660032625265 | 16 / 29 / 0 | 3 |
| A1-A0 | 0.0012030773997005115 | 26 / 19 / 0 | 3 |

Primary: A2-A1, A3-A1, A4-A1. Secondary: A3-A2, A4-A3. A1-A0 is a formulation diagnostic, not an uncertainty effect.

## Statistical and causal limits

Seeds within a partition and alpha variants sharing its seed are clustered. Partition means, exploratory t intervals (only with >=3 partitions) and standardized partition effects are in JSON. Two/three independent assignments give weak uncertainty estimates; no p-values or superiority claims are generated. The fixed underlying test split has been inspected in prior research. Unseen client assignments do not imply a new untouched test dataset.

Reliability target: accepted given selected and executed, including simulation dropout/deadline failures. Missing/unselected outcomes are not negatives. Calibrated widths use past selected-only residuals and cannot justify population calibration or nominal interval coverage. Virtual time and physical CPU/wall time remain separate.

## Outputs and diagnostics

See run-results.csv, trajectories.csv, paired-differences.csv, per-class-recall.csv, calibration-diagnostics.csv, offline-comparisons.csv, offline-widths.csv and width-sensitivity.csv. Minority recall is the mean recall of the two least frequent training classes. Maximum accuracy drop is the largest drawdown from any earlier proxy accuracy; tail SD uses the last ten proxy rounds. Offline rank correlations use average score ranks and Kendall tau-b with tie handling; undefined correlations are null. Top-K uses production ID tie breaks.

Selection-frequency distributions, feasible coverage, opportunity-adjusted Gini, staleness, accepted/selected ratio, deadline misses and physical/virtual efficiency are retained in JSON/CSV. Completion rate and accepted/selected ratio coincide under the audited selected/executed target.

## Failure and integrity report

{
  "passed": true,
  "anomalies": [],
  "completedResearchRuns": 225,
  "expectedResearchRuns": 225,
  "checks": [
    "unique contiguous round commits",
    "final-only held-out evaluation",
    "proxy-only trajectories/pilot",
    "paired initial tensor/partition/scenario hashes"
  ]
}

## Provenance

protocol.json, source-identity.json, build-identity.json, runtime-identity.json, partition-reservation.json, reproducibility-audit.json, completed-artifact-identities/ and the policy/confirmation lock retain executing identities. This directory is separate from all previous results.
