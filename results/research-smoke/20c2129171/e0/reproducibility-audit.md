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
| measured:45:L3 | 3 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | null | null | null | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |

## Conditional run-to-run variability

These sample SDs are across repetitions of one seed inside each policy/duration group, not across training seeds and not within-run tail SD. All groups retain their observed n even when incomplete.

| Group | Metric | Mean | Sample SD | n | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| deterministic:45:L3 | accuracy | 0.12 | 0.0 | 3 | 0.12 | 0.12 |
| deterministic:45:L3 | macroF1 | 0.06391318432134759 | 0.0 | 3 | 0.06391318432134759 | 0.06391318432134759 |
| deterministic:45:L3 | loss | 1.9535341099330357 | 0.0 | 3 | 1.9535341099330357 | 1.9535341099330357 |
| deterministic:45:L3 | feasibleSelectionCoverage | 0.21666666666666667 | 0.0 | 3 | 0.21666666666666667 | 0.21666666666666667 |
| deterministic:45:L3 | feasibleCompletionCoverage | 0.21666666666666667 | 0.0 | 3 | 0.21666666666666667 | 0.21666666666666667 |
| deterministic:45:L3 | feasibleOpportunityAdjustedGini | 0.8146464646464646 | 0.0 | 3 | 0.8146464646464646 | 0.8146464646464646 |
| deterministic:45:L3 | virtualSeconds | 0.25212548437108967 | 0.01119439130204644 | 3 | 0.23959365103775634 | 0.2611353510377563 |
| deterministic:45:L3 | virtualSecondsWithSelector | 0.2667183843710897 | 0.02519989814291582 | 3 | 0.24349965103775636 | 0.2935166510377563 |
| deterministic:45:L3 | wallSeconds | 0.5332459333333334 | 0.05676961710125702 | 3 | 0.4867934 | 0.5965273 |
| deterministic:45:L3 | meanActualTrainingMs | 10.25899111110549 | 0.9064711997833763 | 3 | 9.488613333269313 | 11.257840000022648 |
| deterministic:45:L5 | accuracy | 0.12 | 0.0 | 3 | 0.12 | 0.12 |
| deterministic:45:L5 | macroF1 | 0.06389975548854053 | 0.0 | 3 | 0.06389975548854053 | 0.06389975548854053 |
| deterministic:45:L5 | loss | 1.9536959402901786 | 0.0 | 3 | 1.9536959402901786 | 1.9536959402901786 |
| deterministic:45:L5 | feasibleSelectionCoverage | 0.13333333333333333 | 0.0 | 3 | 0.13333333333333333 | 0.13333333333333333 |
| deterministic:45:L5 | feasibleCompletionCoverage | 0.13333333333333333 | 0.0 | 3 | 0.13333333333333333 | 0.13333333333333333 |
| deterministic:45:L5 | feasibleOpportunityAdjustedGini | 0.8923423423423423 | 0.0 | 3 | 0.8923423423423423 | 0.8923423423423423 |
| deterministic:45:L5 | virtualSeconds | 0.24010820805503882 | 0.005343046140857633 | 3 | 0.23393864138837211 | 0.24321484138837218 |
| deterministic:45:L5 | virtualSecondsWithSelector | 0.24608724138837215 | 0.007395296134706165 | 3 | 0.23791884138837216 | 0.25232744138837215 |
| deterministic:45:L5 | wallSeconds | 0.4924021333333333 | 0.021616873209910226 | 3 | 0.4684278 | 0.510407 |
| deterministic:45:L5 | meanActualTrainingMs | 9.418466666546818 | 0.2905849867023291 | 3 | 9.087153333287764 | 9.630093333180412 |
| measured:45:L3 | accuracy | 0.11523809523809524 | 0.0016495721976846488 | 3 | 0.11428571428571428 | 0.11714285714285715 |
| measured:45:L3 | macroF1 | 0.06616234827836742 | 0.0018987728401768363 | 3 | 0.06396987367898783 | 0.06726997183730742 |
| measured:45:L3 | loss | 1.9533841378348213 | 2.54295984220761E-4 | 3 | 1.9530995396205357 | 1.9535890415736608 |
| measured:45:L3 | feasibleSelectionCoverage | 0.12777777777777777 | 0.00962250448649376 | 3 | 0.11666666666666667 | 0.13333333333333333 |
| measured:45:L3 | feasibleCompletionCoverage | 0.12777777777777777 | 0.00962250448649376 | 3 | 0.11666666666666667 | 0.13333333333333333 |
| measured:45:L3 | feasibleOpportunityAdjustedGini | 0.8949911816578483 | 0.0025210589946496574 | 3 | 0.8925925925925925 | 0.8976190476190475 |
| measured:45:L3 | virtualSeconds | 0.23248568648369017 | 0.029468945102950103 | 3 | 0.21166472809424253 | 0.2662046296837781 |
| measured:45:L3 | virtualSecondsWithSelector | 0.23594435315035686 | 0.029315883808706197 | 3 | 0.21536772809424254 | 0.2695108296837781 |
| measured:45:L3 | wallSeconds | 0.49164499999999994 | 0.025810391285875568 | 3 | 0.4685946 | 0.5195313 |
| measured:45:L3 | meanActualTrainingMs | 9.179522222176375 | 0.03556524918948382 | 3 | 9.147339999920709 | 9.21770666664088 |
| measured:45:L5 | accuracy | 0.11904761904761903 | 0.008247860988423221 | 3 | 0.11428571428571428 | 0.12857142857142856 |
| measured:45:L5 | macroF1 | 0.06545515685217286 | 0.0025725859195836046 | 3 | 0.06396987367898783 | 0.06842572319854294 |
| measured:45:L5 | loss | 1.9536199079241072 | 5.346208721738052E-5 | 3 | 1.9535890415736608 | 1.953681640625 |
| measured:45:L5 | feasibleSelectionCoverage | 0.11666666666666665 | 1.6996749443881478E-17 | 3 | 0.11666666666666667 | 0.11666666666666667 |
| measured:45:L5 | feasibleCompletionCoverage | 0.11666666666666665 | 1.6996749443881478E-17 | 3 | 0.11666666666666667 | 0.11666666666666667 |
| measured:45:L5 | feasibleOpportunityAdjustedGini | 0.897795414462081 | 3.054763329046056E-4 | 3 | 0.8976190476190475 | 0.8981481481481481 |
| measured:45:L5 | virtualSeconds | 0.22091530426672587 | 0.0069418102843374655 | 3 | 0.21331555821087617 | 0.22692235307801756 |
| measured:45:L5 | virtualSecondsWithSelector | 0.22455810426672593 | 0.007125845915630227 | 3 | 0.21675335821087618 | 0.2307170530780176 |
| measured:45:L5 | wallSeconds | 0.4890646 | 0.02441960033108648 | 3 | 0.46864150000000004 | 0.5161133 |
| measured:45:L5 | meanActualTrainingMs | 9.48506222218081 | 0.6431253212511061 | 3 | 9.091046666677963 | 10.227206666604616 |

Null means no observed divergence or unavailable summary statistic. Each of three repeats is compared with every other repeat within its policy/seed/duration group.

Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.

Equal-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.
