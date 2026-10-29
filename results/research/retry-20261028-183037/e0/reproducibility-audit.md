# Reproducibility audit

Deterministic decision/model/learning replay passed. Measured-duration differences are reported separately; this does not establish cross-platform reproducibility.

Completed runs: 12/12. Smoke: false.

| Group | First selection/order difference | First selected-set difference | First global model difference | First learning difference | Classification |
| --- | ---: | ---: | ---: | ---: | --- |
| deterministic:45:L3 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L3 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L3 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L5 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L5 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| deterministic:45:L5 | null | null | null | null | EXACT_DECISION_MODEL_METRIC_REPLAY |
| measured:45:L3 | 2 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 7 | 7 | 7 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 7 | 7 | 7 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 11 | 11 | 11 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |

## Conditional run-to-run variability

These sample SDs are across repetitions of one seed inside each policy/duration group, not across training seeds and not within-run tail SD. All groups retain their observed n even when incomplete.

| Group | Metric | Mean | Sample SD | n | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| deterministic:45:L3 | accuracy | 0.7087535713056349 | 0.0 | 3 | 0.7087535713056349 | 0.7087535713056349 |
| deterministic:45:L3 | macroF1 | 0.3741351440236236 | 0.0 | 3 | 0.3741351440236236 | 0.3741351440236236 |
| deterministic:45:L3 | loss | 0.6791139405498626 | 1.3597399555105182E-16 | 3 | 0.6791139405498627 | 0.6791139405498627 |
| deterministic:45:L3 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| deterministic:45:L3 | feasibleCompletionCoverage | 0.9833333333333333 | 0.0 | 3 | 0.9833333333333333 | 0.9833333333333333 |
| deterministic:45:L3 | feasibleOpportunityAdjustedGini | 0.381082820759157 | 0.0 | 3 | 0.381082820759157 | 0.381082820759157 |
| deterministic:45:L3 | virtualSeconds | 152.85837170020704 | 1.2187948123006302 | 3 | 151.614041500207 | 154.04991590020708 |
| deterministic:45:L3 | virtualSecondsWithSelector | 153.0732611335404 | 1.4473248911514898 | 3 | 151.6763709002071 | 154.56623290020704 |
| deterministic:45:L3 | wallSeconds | 93.74562386666666 | 17.540524954561256 | 3 | 76.4157193 | 111.4894429 |
| deterministic:45:L3 | meanActualTrainingMs | 160.22354552381003 | 29.038502843546432 | 3 | 130.71017742857228 | 188.76266314285982 |
| deterministic:45:L5 | accuracy | 0.699321882207153 | 0.0 | 3 | 0.699321882207153 | 0.699321882207153 |
| deterministic:45:L5 | macroF1 | 0.3917677715183416 | 0.0 | 3 | 0.3917677715183416 | 0.3917677715183416 |
| deterministic:45:L5 | loss | 0.6950917746383785 | 0.0 | 3 | 0.6950917746383785 | 0.6950917746383785 |
| deterministic:45:L5 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| deterministic:45:L5 | feasibleCompletionCoverage | 0.9666666666666667 | 0.0 | 3 | 0.9666666666666667 | 0.9666666666666667 |
| deterministic:45:L5 | feasibleOpportunityAdjustedGini | 0.5852571640644082 | 0.0 | 3 | 0.5852571640644082 | 0.5852571640644082 |
| deterministic:45:L5 | virtualSeconds | 123.73507917950634 | 0.33031519664761144 | 3 | 123.3590056798397 | 123.97820377983967 |
| deterministic:45:L5 | virtualSecondsWithSelector | 123.80578517983967 | 0.3206172919475451 | 3 | 123.44392197983966 | 124.05444207983966 |
| deterministic:45:L5 | wallSeconds | 78.21585720099999 | 6.076865940619505 | 3 | 72.1931118 | 84.345435 |
| deterministic:45:L5 | meanActualTrainingMs | 133.2426609523836 | 12.252493913128513 | 3 | 121.14538828570988 | 145.6446902857137 |
| measured:45:L3 | accuracy | 0.679402889171916 | 0.042836825719632904 | 3 | 0.6308560806856907 | 0.7118859935974665 |
| measured:45:L3 | macroF1 | 0.37839270085173826 | 0.017574692501757177 | 3 | 0.3634214134330544 | 0.3977427969842512 |
| measured:45:L3 | loss | 0.7336151356604236 | 0.07673864069153241 | 3 | 0.6871867029356106 | 0.8221908043569256 |
| measured:45:L3 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L3 | feasibleCompletionCoverage | 0.9833333333333334 | 0.016666666666666663 | 3 | 0.9666666666666667 | 1.0 |
| measured:45:L3 | feasibleOpportunityAdjustedGini | 0.3681011591560004 | 0.030128200656303533 | 3 | 0.35003825290350876 | 0.4028815353290799 |
| measured:45:L3 | virtualSeconds | 13.653628733643695 | 1.3257590165322584 | 3 | 12.862330360430294 | 15.184188548154175 |
| measured:45:L3 | virtualSecondsWithSelector | 13.704376900310365 | 1.3398758032747298 | 3 | 12.90374876043029 | 15.251213148154184 |
| measured:45:L3 | wallSeconds | 70.970542865 | 6.366879295252767 | 3 | 66.9668504 | 78.312331695 |
| measured:45:L3 | meanActualTrainingMs | 119.65213257142706 | 9.798910934767406 | 3 | 113.84453142856728 | 130.96559914285925 |
| measured:45:L5 | accuracy | 0.6667010888896537 | 0.0315154454222635 | 3 | 0.6395993253244294 | 0.7012839489174211 |
| measured:45:L5 | macroF1 | 0.3755667124802422 | 0.02695083779967403 | 3 | 0.3576593407775661 | 0.40656222645746365 |
| measured:45:L5 | loss | 0.7446912222950407 | 0.06026320570128765 | 3 | 0.6862154474751165 | 0.8065954804982644 |
| measured:45:L5 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L5 | feasibleCompletionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L5 | feasibleOpportunityAdjustedGini | 0.33527398683417314 | 0.007975185672763702 | 3 | 0.32683134715764545 | 0.34268042252343767 |
| measured:45:L5 | virtualSeconds | 13.167345082023795 | 0.679733935019801 | 3 | 12.416408584080838 | 13.740573297774137 |
| measured:45:L5 | virtualSecondsWithSelector | 13.217402248357132 | 0.6821713043911287 | 3 | 12.464552084080836 | 13.794501596774142 |
| measured:45:L5 | wallSeconds | 69.18733753333333 | 2.6579546430792047 | 3 | 66.3717166 | 71.6529438 |
| measured:45:L5 | meanActualTrainingMs | 116.85819866666255 | 3.7962642160643405 | 3 | 112.66239628572033 | 120.0552148571361 |

Null means no observed divergence or unavailable summary statistic. Each of three repeats is compared with every other repeat within its policy/seed/duration group.

Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.

Equal-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.
