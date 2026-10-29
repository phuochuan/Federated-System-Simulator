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
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 7 | 7 | 7 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |

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
| deterministic:45:L3 | virtualSeconds | 151.3131533668737 | 0.20265448671113187 | 3 | 151.086476300207 | 151.47681060020705 |
| deterministic:45:L3 | virtualSecondsWithSelector | 151.40395020020708 | 0.1447052867247456 | 3 | 151.24553020020707 | 151.52917050020707 |
| deterministic:45:L3 | wallSeconds | 71.85733806666667 | 0.4178557717710902 | 3 | 71.425116 | 72.259168 |
| deterministic:45:L3 | meanActualTrainingMs | 122.14058933331951 | 0.39747883530250006 | 3 | 121.90750428572106 | 122.59953942852007 |
| deterministic:45:L5 | accuracy | 0.699321882207153 | 0.0 | 3 | 0.699321882207153 | 0.699321882207153 |
| deterministic:45:L5 | macroF1 | 0.3917677715183416 | 0.0 | 3 | 0.3917677715183416 | 0.3917677715183416 |
| deterministic:45:L5 | loss | 0.6950917746383785 | 0.0 | 3 | 0.6950917746383785 | 0.6950917746383785 |
| deterministic:45:L5 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| deterministic:45:L5 | feasibleCompletionCoverage | 0.9666666666666667 | 0.0 | 3 | 0.9666666666666667 | 0.9666666666666667 |
| deterministic:45:L5 | feasibleOpportunityAdjustedGini | 0.5852571640644082 | 0.0 | 3 | 0.5852571640644082 | 0.5852571640644082 |
| deterministic:45:L5 | virtualSeconds | 123.81726584650636 | 0.5316683856270005 | 3 | 123.46045737983968 | 124.42832127983971 |
| deterministic:45:L5 | virtualSecondsWithSelector | 123.88378064650635 | 0.5230706870493548 | 3 | 123.54409597983968 | 124.48613157983968 |
| deterministic:45:L5 | wallSeconds | 73.8980599 | 1.4271828910212512 | 3 | 72.2754502 | 74.9587727 |
| deterministic:45:L5 | meanActualTrainingMs | 124.95448904757463 | 2.5662988746910615 | 3 | 122.26547828565734 | 127.377329142785 |
| measured:45:L3 | accuracy | 0.6875839041685312 | 0.024871503228783426 | 3 | 0.6588757701972393 | 0.7026264156139204 |
| measured:45:L3 | macroF1 | 0.3873219426929047 | 0.031720898826713084 | 3 | 0.3514608081490053 | 0.4117100400106866 |
| measured:45:L3 | loss | 0.7131699256371293 | 0.03595305469861394 | 3 | 0.6895628710473607 | 0.7545479752841716 |
| measured:45:L3 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L3 | feasibleCompletionCoverage | 0.9944444444444445 | 0.009622504486493794 | 3 | 0.9833333333333333 | 1.0 |
| measured:45:L3 | feasibleOpportunityAdjustedGini | 0.2754421675327838 | 0.01619335811823441 | 3 | 0.2572188750584576 | 0.2881812861257013 |
| measured:45:L3 | virtualSeconds | 33.4217437243857 | 25.568097468763458 | 3 | 14.706803146846623 | 62.553967047177544 |
| measured:45:L3 | virtualSecondsWithSelector | 33.78381422438571 | 26.084526478461104 | 3 | 14.768121746846628 | 63.52047904717755 |
| measured:45:L3 | wallSeconds | 572.2048161666667 | 838.1266271678177 | 3 | 75.5409576 | 1539.876722 |
| measured:45:L3 | meanActualTrainingMs | 1465.0333705714365 | 2278.81617778284 | 3 | 128.0254348572063 | 4096.267708857122 |
| measured:45:L5 | accuracy | 0.696533682145193 | 0.007600065144181135 | 3 | 0.6877904375064542 | 0.7015593267013184 |
| measured:45:L5 | macroF1 | 0.3916513082580251 | 0.009168839010680323 | 3 | 0.38553815685477905 | 0.40219384707367134 |
| measured:45:L5 | loss | 0.7001329677417605 | 0.021867017978693493 | 3 | 0.6854103857594994 | 0.7252594117047122 |
| measured:45:L5 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L5 | feasibleCompletionCoverage | 0.9944444444444445 | 0.009622504486493794 | 3 | 0.9833333333333333 | 1.0 |
| measured:45:L5 | feasibleOpportunityAdjustedGini | 0.33965646618916995 | 0.01376536409356153 | 3 | 0.32584150367258524 | 0.35337168985058925 |
| measured:45:L5 | virtualSeconds | 18.058545991024204 | 3.9417269605024225 | 3 | 13.90422720697463 | 21.746120860968066 |
| measured:45:L5 | virtualSecondsWithSelector | 18.13631685769087 | 3.970002670017312 | 3 | 13.952206806974631 | 21.850357860968067 |
| measured:45:L5 | wallSeconds | 90.22028143333334 | 16.868521287115854 | 3 | 72.8755722 | 106.5684296 |
| measured:45:L5 | meanActualTrainingMs | 151.45295533331503 | 29.448399411787396 | 3 | 123.84325199993847 | 182.44752599998588 |

Null means no observed divergence or unavailable summary statistic. Each of three repeats is compared with every other repeat within its policy/seed/duration group.

Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.

Equal-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.
