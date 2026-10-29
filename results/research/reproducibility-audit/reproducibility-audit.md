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
| measured:45:L3 | 3 | 3 | 3 | 3 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L3 | 2 | 2 | 2 | 2 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 7 | 7 | 7 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 7 | 7 | 7 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |
| measured:45:L5 | 2 | 7 | 7 | 7 | TIMING_DIFFERENCE_WITH_CONDITIONAL_TRAINING_REPLAY |

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
| deterministic:45:L3 | virtualSeconds | 151.3841115335404 | 0.0812548161000456 | 3 | 151.29188280020708 | 151.44515040020707 |
| deterministic:45:L3 | virtualSecondsWithSelector | 151.47383030020708 | 0.12736760570131794 | 3 | 151.3463156002071 | 151.60105030020708 |
| deterministic:45:L3 | wallSeconds | 72.50093353333334 | 1.7325510612197812 | 3 | 70.8121934 | 74.27420120000001 |
| deterministic:45:L3 | meanActualTrainingMs | 126.0980298094858 | 2.6997486654975145 | 3 | 123.82840628567075 | 129.08358457137052 |
| deterministic:45:L5 | accuracy | 0.699321882207153 | 0.0 | 3 | 0.699321882207153 | 0.699321882207153 |
| deterministic:45:L5 | macroF1 | 0.3917677715183416 | 0.0 | 3 | 0.3917677715183416 | 0.3917677715183416 |
| deterministic:45:L5 | loss | 0.6950917746383785 | 0.0 | 3 | 0.6950917746383785 | 0.6950917746383785 |
| deterministic:45:L5 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| deterministic:45:L5 | feasibleCompletionCoverage | 0.9666666666666667 | 0.0 | 3 | 0.9666666666666667 | 0.9666666666666667 |
| deterministic:45:L5 | feasibleOpportunityAdjustedGini | 0.5852571640644082 | 0.0 | 3 | 0.5852571640644082 | 0.5852571640644082 |
| deterministic:45:L5 | virtualSeconds | 123.34312721317302 | 0.051362673030252555 | 3 | 123.2878380798397 | 123.3893582798397 |
| deterministic:45:L5 | virtualSecondsWithSelector | 123.41389364650632 | 0.05659315354657004 | 3 | 123.34872947983963 | 123.45071937983967 |
| deterministic:45:L5 | wallSeconds | 71.44258326666666 | 0.4472552063662338 | 3 | 71.1441738 | 71.9568237 |
| deterministic:45:L5 | meanActualTrainingMs | 124.04050171429412 | 0.6777615536052464 | 3 | 123.58881400002636 | 124.819829428582 |
| measured:45:L3 | accuracy | 0.6834876596330591 | 0.061653065017189895 | 3 | 0.6131974802932774 | 0.7284086606313036 |
| measured:45:L3 | macroF1 | 0.4001118536156478 | 0.029794830247453642 | 3 | 0.3755695429182982 | 0.43326333819306434 |
| measured:45:L3 | loss | 0.7321266977147948 | 0.12997364087002627 | 3 | 0.6395631351387565 | 0.8807175083376406 |
| measured:45:L3 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L3 | feasibleCompletionCoverage | 0.9944444444444445 | 0.009622504486493794 | 3 | 0.9833333333333333 | 1.0 |
| measured:45:L3 | feasibleOpportunityAdjustedGini | 0.34636438018335675 | 0.005158924839019714 | 3 | 0.3412948416735592 | 0.3516082710612017 |
| measured:45:L3 | virtualSeconds | 14.614753072303756 | 1.940647578801962 | 3 | 13.472272912583822 | 16.855474310666164 |
| measured:45:L3 | virtualSecondsWithSelector | 14.676420938970418 | 1.9403691428010603 | 3 | 13.553238112583818 | 16.916963710666156 |
| measured:45:L3 | wallSeconds | 73.70878483333333 | 9.443201356126217 | 3 | 67.9682576 | 84.607673 |
| measured:45:L3 | meanActualTrainingMs | 127.96696799999891 | 17.092664859320177 | 3 | 117.88020200000445 | 147.70225542859407 |
| measured:45:L5 | accuracy | 0.666310970362466 | 0.04835001609989727 | 3 | 0.6165020137000448 | 0.7130563491790299 |
| measured:45:L5 | macroF1 | 0.38240531055670157 | 0.03703867213899341 | 3 | 0.3445535911034523 | 0.418573523215691 |
| measured:45:L5 | loss | 0.7544850790224205 | 0.09444366258039227 | 3 | 0.6694249881942532 | 0.8561183486533516 |
| measured:45:L5 | feasibleSelectionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L5 | feasibleCompletionCoverage | 1.0 | 0.0 | 3 | 1.0 | 1.0 |
| measured:45:L5 | feasibleOpportunityAdjustedGini | 0.342435391885973 | 0.005333285914824222 | 3 | 0.33820706292235575 | 0.3484270380609478 |
| measured:45:L5 | virtualSeconds | 13.935605035206082 | 1.6133052392004106 | 3 | 12.907561609653177 | 15.795025882520157 |
| measured:45:L5 | virtualSecondsWithSelector | 13.984398901872751 | 1.6186274361810074 | 3 | 12.955549709653177 | 15.85014018252016 |
| measured:45:L5 | wallSeconds | 69.32051383333334 | 4.531829417574561 | 3 | 66.1502501 | 74.5111344 |
| measured:45:L5 | meanActualTrainingMs | 119.09970628573016 | 6.2311310893661735 | 3 | 114.54290142858164 | 126.20031171431037 |

Null means no observed divergence or unavailable summary statistic. Each of three repeats is compared with every other repeat within its policy/seed/duration group.

Pure simulated training duration is deterministic in deterministic mode. Server, selector, fairness, evaluation and physical wall-time overhead remain measured and need not be equal.

Equal-input local update checks separate training nondeterminism from selection changes caused by measured durations. Saved-state replay checks credit/controller/history consistency; passing it does not prove absence of all simulator bugs. All metadata and round evidence are in reproducibility-audit.json and the run exports.
