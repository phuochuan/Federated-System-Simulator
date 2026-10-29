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
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |

## Conditional run-to-run variability

These sample SDs are across repetitions of one seed inside each policy/duration group, not across training seeds and not within-run tail SD. All groups retain their observed n even when incomplete.

| Group | Metric | Mean | Sample SD | n | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| deterministic:45:L3 | accuracy | 0.14857142857142858 | 0.0 | 3 | 0.14857142857142858 | 0.14857142857142858 |
| deterministic:45:L3 | macroF1 | 0.0974176954959262 | 0.0 | 3 | 0.0974176954959262 | 0.0974176954959262 |
| deterministic:45:L3 | loss | 1.9529570661272322 | 0.0 | 3 | 1.9529570661272322 | 1.9529570661272322 |
| deterministic:45:L3 | feasibleSelectionCoverage | 0.18333333333333332 | 0.0 | 3 | 0.18333333333333332 | 0.18333333333333332 |
| deterministic:45:L3 | feasibleCompletionCoverage | 0.18333333333333332 | 0.0 | 3 | 0.18333333333333332 | 0.18333333333333332 |
| deterministic:45:L3 | feasibleOpportunityAdjustedGini | 0.8478494623655916 | 1.3597399555105182E-16 | 3 | 0.8478494623655914 | 0.8478494623655914 |
| deterministic:45:L3 | virtualSeconds | 0.3803544992584332 | 0.06256003018539236 | 3 | 0.3406650005917665 | 0.4524708005917665 |
| deterministic:45:L3 | virtualSecondsWithSelector | 0.39813629892509983 | 0.0837422651816214 | 3 | 0.3467217015917665 | 0.49476729859176644 |
| deterministic:45:L3 | wallSeconds | 0.9851870673333334 | 0.22208288801404577 | 3 | 0.8164127999999999 | 1.2367784 |
| deterministic:45:L3 | meanActualTrainingMs | 13.224184444495927 | 3.7883456418465786 | 3 | 9.997086666650526 | 17.395260000193957 |
| deterministic:45:L5 | accuracy | 0.15714285714285714 | 0.0 | 3 | 0.15714285714285714 | 0.15714285714285714 |
| deterministic:45:L5 | macroF1 | 0.09431279875052169 | 0.0 | 3 | 0.09431279875052169 | 0.09431279875052169 |
| deterministic:45:L5 | loss | 1.9531087820870539 | 2.7194799110210365E-16 | 3 | 1.9531087820870536 | 1.9531087820870536 |
| deterministic:45:L5 | feasibleSelectionCoverage | 0.13333333333333333 | 0.0 | 3 | 0.13333333333333333 | 0.13333333333333333 |
| deterministic:45:L5 | feasibleCompletionCoverage | 0.13333333333333333 | 0.0 | 3 | 0.13333333333333333 | 0.13333333333333333 |
| deterministic:45:L5 | feasibleOpportunityAdjustedGini | 0.8994623655913979 | 0.0 | 3 | 0.8994623655913979 | 0.8994623655913979 |
| deterministic:45:L5 | virtualSeconds | 0.3889757868252139 | 0.05224277025584629 | 3 | 0.3564971534918805 | 0.4492396514918805 |
| deterministic:45:L5 | virtualSecondsWithSelector | 0.3969769861585472 | 0.052184515297356175 | 3 | 0.36077725149188056 | 0.4567950514918805 |
| deterministic:45:L5 | wallSeconds | 0.9712789996666666 | 0.07391804279266262 | 3 | 0.8925348 | 1.039171098 |
| deterministic:45:L5 | meanActualTrainingMs | 11.493877777845936 | 1.5021745715303725 | 3 | 9.774160000233678 | 12.54984000006516 |
| measured:45:L3 | accuracy | 0.14857142857142858 | 0.00494871659305393 | 3 | 0.1457142857142857 | 0.15428571428571428 |
| measured:45:L3 | macroF1 | 0.09345150174171667 | 0.003785789682910735 | 3 | 0.09122537895587637 | 0.09782270471075123 |
| measured:45:L3 | loss | 1.9529242234002977 | 4.379153286762524E-5 | 3 | 1.9528782435825893 | 1.9529654366629465 |
| measured:45:L3 | feasibleSelectionCoverage | 0.12777777777777777 | 0.03469443332443554 | 3 | 0.1 | 0.16666666666666666 |
| measured:45:L3 | feasibleCompletionCoverage | 0.12222222222222223 | 0.03849001794597504 | 3 | 0.1 | 0.16666666666666666 |
| measured:45:L3 | feasibleOpportunityAdjustedGini | 0.8956317204301077 | 0.022895569388887125 | 3 | 0.8693548387096776 | 0.9112903225806454 |
| measured:45:L3 | virtualSeconds | 0.3816661570738436 | 0.04290975779671755 | 3 | 0.3440310495726291 | 0.4283933207590591 |
| measured:45:L3 | virtualSecondsWithSelector | 0.3862482230738436 | 0.044130660367531854 | 3 | 0.3474875485726291 | 0.43427681975905913 |
| measured:45:L3 | wallSeconds | 1.0097934006666667 | 0.12049023301886592 | 3 | 0.8779188 | 1.1141327 |
| measured:45:L3 | meanActualTrainingMs | 12.127460000071247 | 4.2761033076763475 | 3 | 9.584393333352637 | 17.06432666675634 |
| measured:45:L5 | accuracy | 0.1457142857142857 | 0.0 | 3 | 0.1457142857142857 | 0.1457142857142857 |
| measured:45:L5 | macroF1 | 0.09130642155852238 | 1.6996749443881478E-17 | 3 | 0.0913064215585224 | 0.0913064215585224 |
| measured:45:L5 | loss | 1.9528782435825895 | 2.7194799110210365E-16 | 3 | 1.9528782435825893 | 1.9528782435825893 |
| measured:45:L5 | feasibleSelectionCoverage | 0.10000000000000002 | 1.6996749443881478E-17 | 3 | 0.1 | 0.1 |
| measured:45:L5 | feasibleCompletionCoverage | 0.10000000000000002 | 1.6996749443881478E-17 | 3 | 0.1 | 0.1 |
| measured:45:L5 | feasibleOpportunityAdjustedGini | 0.9104166666666668 | 1.3597399555105182E-16 | 3 | 0.9104166666666667 | 0.9104166666666667 |
| measured:45:L5 | virtualSeconds | 0.41541757087703607 | 0.12090681220818249 | 3 | 0.2980563581414736 | 0.5395826528651751 |
| measured:45:L5 | virtualSecondsWithSelector | 0.4213610715437028 | 0.12220228562372336 | 3 | 0.3022424571414736 | 0.5464296558651752 |
| measured:45:L5 | wallSeconds | 1.055028299 | 0.19768039282276223 | 3 | 0.8369546990000001 | 1.222464298 |
| measured:45:L5 | meanActualTrainingMs | 14.880811111288494 | 4.371581689242187 | 3 | 9.918140000202888 | 18.161926666653017 |

Null means no observed divergence or unavailable summary statistic. Each of three repeats is compared with every other repeat within its policy/seed/duration group.

Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.

Equal-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.
