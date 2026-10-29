# Reproducibility audit

Deterministic decision/model/learning replay passed. Measured-duration differences are reported separately; this does not establish cross-platform reproducibility.

Completed runs: 12/12. Smoke: true.

| Group | First selection/order difference | First selected-set difference | First global model difference | First learning difference | Classification |
| --- | ---: | ---: | ---: | ---: | --- |
| deterministic:45:L3 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L3 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L3 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L5 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L5 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L5 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| measured:45:L3 | 2 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 3 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |

Null means no observed divergence. Each of three repeats is compared with every other repeat within its policy/seed/duration group.

Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.

Equal-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.
