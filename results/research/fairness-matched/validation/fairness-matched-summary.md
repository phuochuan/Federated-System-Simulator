# Fairness-matched lambda experiments — validation

Complete: false; smoke: false.

INCOMPLETE: java.lang.IllegalStateException: Experiment research-80e687cf9e00d2b736bba0e7c74a9065710b8ce5 ended with FAILED: Worker unavailable. Completed runs are retained; no final comparison or policy lock is justified.

Fairness status: **INCOMPLETE**. Do not label this comparison fairness-matched. Inspect every coverage/Gini/staleness gap in JSON; held-out policy must not be retuned.

Ratios except maximum accuracy drop in percentage points and times in seconds. Tail SD is within-run; summary sample SD is between training/scenario seeds inside each partition. Partitions are not treated as extra independent training seeds.

Population selection/completion coverage: all 100 logical clients. RAM denominator: static feasible RAM population (normally 60). Feasible coverage/Gini/staleness: clients with >=1 valid estimated-feasible opportunity, whose count and membership are policy-specific and exported. Completion Ginis are explicitly separated into population, RAM-feasible and feasible completion/opportunity versions.

Phase A reports proxy validation outcomes. Phase B reports test ONLY at the final checkpoint; tail stability, drift/drop and time-to-target use the independently held-out proxy trajectory, as labelled in every record. Final accuracy always uses the final checkpoint, including low accuracy/drift runs.

## Per-partition mean ± sample SD across training/scenario seeds

| Partition:policy | Metric | Mean | Sample SD | n | Min / worst case | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1001:M1 | accuracy | 0.710784 | 0.023026 | 2 | 0.694503 | 0.727066 |
| 1001:M1 | macroF1 | 0.435069 | 0.044116 | 2 | 0.403874 | 0.466264 |
| 1001:M1 | loss | 0.666740 | 0.046673 | 2 | 0.633737 | 0.699743 |
| 1001:M1 | worstClassRecall | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M1 | recall0 | 0.627738 | 0.116961 | 2 | 0.545034 | 0.710442 |
| 1001:M1 | recall1 | 0.862690 | 0.067491 | 2 | 0.814966 | 0.910413 |
| 1001:M1 | recall2 | 0.456935 | 0.232538 | 2 | 0.292506 | 0.621365 |
| 1001:M1 | recall3 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M1 | recall4 | 0.023158 | 0.032750 | 2 | 0.000000 | 0.046316 |
| 1001:M1 | recall5 | 0.592742 | 0.106718 | 2 | 0.517281 | 0.668203 |
| 1001:M1 | recall6 | 0.426413 | 0.046176 | 2 | 0.393762 | 0.459064 |
| 1001:M1 | accuracyTailMean | 0.684390 | 0.006397 | 2 | 0.679866 | 0.688913 |
| 1001:M1 | accuracyTailSd | 0.049883 | 0.001636 | 2 | 0.048726 | 0.051040 |
| 1001:M1 | macroF1TailSd | 0.027726 | 0.003466 | 2 | 0.025275 | 0.030177 |
| 1001:M1 | maxAccuracyDropPp | 19.439950 | 1.604018 | 2 | 18.305738 | 20.574163 |
| 1001:M1 | populationSelectionCoverage | 0.600000 | 0.000000 | 2 | 0.600000 | 0.600000 |
| 1001:M1 | populationCompletionCoverage | 0.575000 | 0.007071 | 2 | 0.570000 | 0.580000 |
| 1001:M1 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 2 | 1.000000 | 1.000000 |
| 1001:M1 | feasibleCompletionCoverage | 0.958333 | 0.011785 | 2 | 0.950000 | 0.966667 |
| 1001:M1 | feasibleOpportunityAdjustedGini | 0.537359 | 0.031209 | 2 | 0.515291 | 0.559427 |
| 1001:M1 | feasibleCompletionOpportunityAdjustedGini | 0.551848 | 0.017408 | 2 | 0.539538 | 0.564157 |
| 1001:M1 | selectionGini | 0.723514 | 0.019355 | 2 | 0.709829 | 0.737200 |
| 1001:M1 | completionGini | 0.732165 | 0.010696 | 2 | 0.724601 | 0.739728 |
| 1001:M1 | ramFeasibleCompletionGini | 0.553608 | 0.017827 | 2 | 0.541002 | 0.566213 |
| 1001:M1 | maxFeasibleSelectionStaleness | 49.500000 | 3.535534 | 2 | 47.000000 | 52.000000 |
| 1001:M1 | meanFeasibleSelectionStaleness | 15.633333 | 2.074180 | 2 | 14.166667 | 17.100000 |
| 1001:M1 | populationNeverSelected | 40.000000 | 0.000000 | 2 | 40.000000 | 40.000000 |
| 1001:M1 | feasibleNeverSelected | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M1 | acceptedSelectedRatio | 0.938571 | 0.010102 | 2 | 0.931429 | 0.945714 |
| 1001:M1 | virtualSeconds | 136.784191 | 7.910169 | 2 | 131.190857 | 142.377526 |
| 1001:M1 | virtualSecondsWithSelector | 136.823908 | 7.904752 | 2 | 131.234405 | 142.413412 |
| 1001:M1 | wallSeconds | 66.826246 | 1.399568 | 2 | 65.836602 | 67.815890 |
| 1001:M1 | selectorSeconds | 0.035837 | 0.004266 | 2 | 0.032820 | 0.038854 |
| 1001:M1 | fairnessUpdateSeconds | 0.003880 | 0.001152 | 2 | 0.003066 | 0.004695 |
| 1001:M1 | slotsChangedVsTopsis | 197.000000 | 8.485281 | 2 | 191.000000 | 203.000000 |
| 1001:M1 | slotsChangedVsTopsisRatio | 0.562857 | 0.024244 | 2 | 0.545714 | 0.580000 |
| 1001:M1 | meanAppliedLambda | 0.600000 | 0.000000 | 2 | 0.600000 | 0.600000 |
| 1001:M2 | accuracy | 0.714881 | 0.001947 | 2 | 0.713504 | 0.716258 |
| 1001:M2 | macroF1 | 0.402661 | 0.000801 | 2 | 0.402095 | 0.403227 |
| 1001:M2 | loss | 0.656175 | 0.000036 | 2 | 0.656150 | 0.656200 |
| 1001:M2 | worstClassRecall | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M2 | recall0 | 0.704824 | 0.043193 | 2 | 0.674282 | 0.735366 |
| 1001:M2 | recall1 | 0.834945 | 0.026357 | 2 | 0.816308 | 0.853583 |
| 1001:M2 | recall2 | 0.413311 | 0.011864 | 2 | 0.404922 | 0.421700 |
| 1001:M2 | recall3 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M2 | recall4 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M2 | recall5 | 0.596774 | 0.053766 | 2 | 0.558756 | 0.634793 |
| 1001:M2 | recall6 | 0.212963 | 0.002068 | 2 | 0.211501 | 0.214425 |
| 1001:M2 | accuracyTailMean | 0.697654 | 0.010284 | 2 | 0.690382 | 0.704926 |
| 1001:M2 | accuracyTailSd | 0.031462 | 0.006202 | 2 | 0.027077 | 0.035848 |
| 1001:M2 | macroF1TailSd | 0.024990 | 0.009136 | 2 | 0.018530 | 0.031451 |
| 1001:M2 | maxAccuracyDropPp | 16.070015 | 1.662435 | 2 | 14.894496 | 17.245534 |
| 1001:M2 | populationSelectionCoverage | 0.600000 | 0.000000 | 2 | 0.600000 | 0.600000 |
| 1001:M2 | populationCompletionCoverage | 0.585000 | 0.021213 | 2 | 0.570000 | 0.600000 |
| 1001:M2 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 2 | 1.000000 | 1.000000 |
| 1001:M2 | feasibleCompletionCoverage | 0.975000 | 0.035355 | 2 | 0.950000 | 1.000000 |
| 1001:M2 | feasibleOpportunityAdjustedGini | 0.548008 | 0.033594 | 2 | 0.524254 | 0.571762 |
| 1001:M2 | feasibleCompletionOpportunityAdjustedGini | 0.555199 | 0.018269 | 2 | 0.542281 | 0.568117 |
| 1001:M2 | selectionGini | 0.728800 | 0.022708 | 2 | 0.712743 | 0.744857 |
| 1001:M2 | completionGini | 0.732959 | 0.013526 | 2 | 0.723394 | 0.742523 |
| 1001:M2 | ramFeasibleCompletionGini | 0.554931 | 0.022543 | 2 | 0.538991 | 0.570871 |
| 1001:M2 | maxFeasibleSelectionStaleness | 53.000000 | 1.414214 | 2 | 52.000000 | 54.000000 |
| 1001:M2 | meanFeasibleSelectionStaleness | 17.450000 | 0.471405 | 2 | 17.116667 | 17.783333 |
| 1001:M2 | populationNeverSelected | 40.000000 | 0.000000 | 2 | 40.000000 | 40.000000 |
| 1001:M2 | feasibleNeverSelected | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M2 | acceptedSelectedRatio | 0.937143 | 0.004041 | 2 | 0.934286 | 0.940000 |
| 1001:M2 | virtualSeconds | 133.695262 | 4.221816 | 2 | 130.709987 | 136.680537 |
| 1001:M2 | virtualSecondsWithSelector | 133.733427 | 4.222902 | 2 | 130.747385 | 136.719470 |
| 1001:M2 | wallSeconds | 65.559812 | 0.290444 | 2 | 65.354437 | 65.765186 |
| 1001:M2 | selectorSeconds | 0.034843 | 0.001126 | 2 | 0.034047 | 0.035639 |
| 1001:M2 | fairnessUpdateSeconds | 0.003322 | 0.000040 | 2 | 0.003294 | 0.003350 |
| 1001:M2 | slotsChangedVsTopsis | 198.000000 | 9.899495 | 2 | 191.000000 | 205.000000 |
| 1001:M2 | slotsChangedVsTopsisRatio | 0.565714 | 0.028284 | 2 | 0.545714 | 0.585714 |
| 1001:M2 | meanAppliedLambda | 0.625000 | 0.000000 | 2 | 0.625000 | 0.625000 |
| 1001:M3 | accuracy | 0.720078 | 0.013582 | 2 | 0.710475 | 0.729682 |
| 1001:M3 | macroF1 | 0.456324 | 0.008466 | 2 | 0.450337 | 0.462310 |
| 1001:M3 | loss | 0.650379 | 0.007739 | 2 | 0.644907 | 0.655851 |
| 1001:M3 | worstClassRecall | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M3 | recall0 | 0.642655 | 0.102942 | 2 | 0.569864 | 0.715446 |
| 1001:M3 | recall1 | 0.837769 | 0.067391 | 2 | 0.790116 | 0.885422 |
| 1001:M3 | recall2 | 0.691834 | 0.219883 | 2 | 0.536353 | 0.847315 |
| 1001:M3 | recall3 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M3 | recall4 | 0.001053 | 0.001489 | 2 | 0.000000 | 0.002105 |
| 1001:M3 | recall5 | 0.457373 | 0.215065 | 2 | 0.305300 | 0.609447 |
| 1001:M3 | recall6 | 0.595029 | 0.050311 | 2 | 0.559454 | 0.630604 |
| 1001:M3 | accuracyTailMean | 0.690090 | 0.014921 | 2 | 0.679539 | 0.700640 |
| 1001:M3 | accuracyTailSd | 0.049459 | 0.010247 | 2 | 0.042213 | 0.056705 |
| 1001:M3 | macroF1TailSd | 0.035843 | 0.013819 | 2 | 0.026071 | 0.045615 |
| 1001:M3 | maxAccuracyDropPp | 15.804964 | 1.360616 | 2 | 14.842863 | 16.767065 |
| 1001:M3 | populationSelectionCoverage | 0.600000 | 0.000000 | 2 | 0.600000 | 0.600000 |
| 1001:M3 | populationCompletionCoverage | 0.575000 | 0.007071 | 2 | 0.570000 | 0.580000 |
| 1001:M3 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 2 | 1.000000 | 1.000000 |
| 1001:M3 | feasibleCompletionCoverage | 0.958333 | 0.011785 | 2 | 0.950000 | 0.966667 |
| 1001:M3 | feasibleOpportunityAdjustedGini | 0.517559 | 0.017013 | 2 | 0.505529 | 0.529589 |
| 1001:M3 | feasibleCompletionOpportunityAdjustedGini | 0.526706 | 0.014824 | 2 | 0.516224 | 0.537188 |
| 1001:M3 | selectionGini | 0.710029 | 0.013778 | 2 | 0.700286 | 0.719771 |
| 1001:M3 | completionGini | 0.715464 | 0.012743 | 2 | 0.706453 | 0.724474 |
| 1001:M3 | ramFeasibleCompletionGini | 0.525773 | 0.021239 | 2 | 0.510754 | 0.540791 |
| 1001:M3 | maxFeasibleSelectionStaleness | 52.500000 | 0.707107 | 2 | 52.000000 | 53.000000 |
| 1001:M3 | meanFeasibleSelectionStaleness | 16.008333 | 2.439518 | 2 | 14.283333 | 17.733333 |
| 1001:M3 | populationNeverSelected | 40.000000 | 0.000000 | 2 | 40.000000 | 40.000000 |
| 1001:M3 | feasibleNeverSelected | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M3 | acceptedSelectedRatio | 0.942857 | 0.012122 | 2 | 0.934286 | 0.951429 |
| 1001:M3 | virtualSeconds | 139.543048 | 3.042174 | 2 | 137.391906 | 141.694190 |
| 1001:M3 | virtualSecondsWithSelector | 139.581382 | 3.040294 | 2 | 137.431569 | 141.731194 |
| 1001:M3 | wallSeconds | 66.478828 | 1.423656 | 2 | 65.472152 | 67.485505 |
| 1001:M3 | selectorSeconds | 0.034906 | 0.001405 | 2 | 0.033913 | 0.035900 |
| 1001:M3 | fairnessUpdateSeconds | 0.003427 | 0.000475 | 2 | 0.003091 | 0.003764 |
| 1001:M3 | slotsChangedVsTopsis | 208.000000 | 11.313708 | 2 | 200.000000 | 216.000000 |
| 1001:M3 | slotsChangedVsTopsisRatio | 0.594286 | 0.032325 | 2 | 0.571429 | 0.617143 |
| 1001:M3 | meanAppliedLambda | 0.650000 | 0.000000 | 2 | 0.650000 | 0.650000 |
| 1001:M4 | accuracy | 0.702902 | 0.013192 | 2 | 0.693573 | 0.712230 |
| 1001:M4 | macroF1 | 0.398346 | 0.045165 | 2 | 0.366410 | 0.430283 |
| 1001:M4 | loss | 0.679409 | 0.019675 | 2 | 0.665497 | 0.693322 |
| 1001:M4 | worstClassRecall | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M4 | recall0 | 0.598707 | 0.027037 | 2 | 0.579588 | 0.617825 |
| 1001:M4 | recall1 | 0.890928 | 0.021266 | 2 | 0.875891 | 0.905965 |
| 1001:M4 | recall2 | 0.380593 | 0.038361 | 2 | 0.353468 | 0.407718 |
| 1001:M4 | recall3 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M4 | recall4 | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M4 | recall5 | 0.558180 | 0.157225 | 2 | 0.447005 | 0.669355 |
| 1001:M4 | recall6 | 0.286062 | 0.188148 | 2 | 0.153021 | 0.419103 |
| 1001:M4 | accuracyTailMean | 0.688692 | 0.003967 | 2 | 0.685887 | 0.691498 |
| 1001:M4 | accuracyTailSd | 0.038549 | 0.007319 | 2 | 0.033374 | 0.043725 |
| 1001:M4 | macroF1TailSd | 0.040413 | 0.008131 | 2 | 0.034664 | 0.046163 |
| 1001:M4 | maxAccuracyDropPp | 16.780834 | 0.175249 | 2 | 16.656914 | 16.904754 |
| 1001:M4 | populationSelectionCoverage | 0.600000 | 0.000000 | 2 | 0.600000 | 0.600000 |
| 1001:M4 | populationCompletionCoverage | 0.590000 | 0.000000 | 2 | 0.590000 | 0.590000 |
| 1001:M4 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 2 | 1.000000 | 1.000000 |
| 1001:M4 | feasibleCompletionCoverage | 0.983333 | 0.000000 | 2 | 0.983333 | 0.983333 |
| 1001:M4 | feasibleOpportunityAdjustedGini | 0.465175 | 0.018563 | 2 | 0.452048 | 0.478301 |
| 1001:M4 | feasibleCompletionOpportunityAdjustedGini | 0.473464 | 0.017165 | 2 | 0.461326 | 0.485601 |
| 1001:M4 | selectionGini | 0.678514 | 0.007758 | 2 | 0.673029 | 0.684000 |
| 1001:M4 | completionGini | 0.683207 | 0.006965 | 2 | 0.678282 | 0.688133 |
| 1001:M4 | ramFeasibleCompletionGini | 0.472012 | 0.011609 | 2 | 0.463804 | 0.480221 |
| 1001:M4 | maxFeasibleSelectionStaleness | 46.500000 | 7.778175 | 2 | 41.000000 | 52.000000 |
| 1001:M4 | meanFeasibleSelectionStaleness | 12.191667 | 4.985103 | 2 | 8.666667 | 15.716667 |
| 1001:M4 | populationNeverSelected | 40.000000 | 0.000000 | 2 | 40.000000 | 40.000000 |
| 1001:M4 | feasibleNeverSelected | 0.000000 | 0.000000 | 2 | 0.000000 | 0.000000 |
| 1001:M4 | acceptedSelectedRatio | 0.940000 | 0.012122 | 2 | 0.931429 | 0.948571 |
| 1001:M4 | virtualSeconds | 143.171587 | 1.199456 | 2 | 142.323443 | 144.019730 |
| 1001:M4 | virtualSecondsWithSelector | 143.210829 | 1.201526 | 2 | 142.361222 | 144.060436 |
| 1001:M4 | wallSeconds | 66.867153 | 1.240572 | 2 | 65.989936 | 67.744370 |
| 1001:M4 | selectorSeconds | 0.035795 | 0.002188 | 2 | 0.034248 | 0.037342 |
| 1001:M4 | fairnessUpdateSeconds | 0.003447 | 0.000119 | 2 | 0.003363 | 0.003531 |
| 1001:M4 | slotsChangedVsTopsis | 218.500000 | 2.121320 | 2 | 217.000000 | 220.000000 |
| 1001:M4 | slotsChangedVsTopsisRatio | 0.624286 | 0.006061 | 2 | 0.620000 | 0.628571 |
| 1001:M4 | meanAppliedLambda | 0.675000 | 0.000000 | 2 | 0.675000 | 0.675000 |
| 1001:M5 | accuracy | 0.720503 | 0.007381 | 3 | 0.712024 | 0.725483 |
| 1001:M5 | macroF1 | 0.439129 | 0.032198 | 3 | 0.411185 | 0.474339 |
| 1001:M5 | loss | 0.653986 | 0.014988 | 3 | 0.639724 | 0.669608 |
| 1001:M5 | worstClassRecall | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M5 | recall0 | 0.672426 | 0.081864 | 3 | 0.612821 | 0.765767 |
| 1001:M5 | recall1 | 0.835769 | 0.061691 | 3 | 0.764984 | 0.878080 |
| 1001:M5 | recall2 | 0.678598 | 0.260992 | 3 | 0.387025 | 0.890380 |
| 1001:M5 | recall3 | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M5 | recall4 | 0.049825 | 0.086299 | 3 | 0.000000 | 0.149474 |
| 1001:M5 | recall5 | 0.391321 | 0.287618 | 3 | 0.120968 | 0.693548 |
| 1001:M5 | recall6 | 0.383691 | 0.064889 | 3 | 0.320663 | 0.450292 |
| 1001:M5 | accuracyTailMean | 0.683846 | 0.011205 | 3 | 0.672015 | 0.694296 |
| 1001:M5 | accuracyTailSd | 0.048278 | 0.015623 | 3 | 0.030588 | 0.060182 |
| 1001:M5 | macroF1TailSd | 0.040738 | 0.010967 | 3 | 0.032309 | 0.053137 |
| 1001:M5 | maxAccuracyDropPp | 16.755591 | 0.163110 | 3 | 16.567416 | 16.856563 |
| 1001:M5 | populationSelectionCoverage | 0.600000 | 0.000000 | 3 | 0.600000 | 0.600000 |
| 1001:M5 | populationCompletionCoverage | 0.600000 | 0.000000 | 3 | 0.600000 | 0.600000 |
| 1001:M5 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 3 | 1.000000 | 1.000000 |
| 1001:M5 | feasibleCompletionCoverage | 1.000000 | 0.000000 | 3 | 1.000000 | 1.000000 |
| 1001:M5 | feasibleOpportunityAdjustedGini | 0.483767 | 0.016155 | 3 | 0.471451 | 0.502058 |
| 1001:M5 | feasibleCompletionOpportunityAdjustedGini | 0.483603 | 0.016657 | 3 | 0.467514 | 0.500774 |
| 1001:M5 | selectionGini | 0.691010 | 0.011341 | 3 | 0.681086 | 0.703371 |
| 1001:M5 | completionGini | 0.690926 | 0.011905 | 3 | 0.678862 | 0.702667 |
| 1001:M5 | ramFeasibleCompletionGini | 0.484877 | 0.019842 | 3 | 0.464770 | 0.504444 |
| 1001:M5 | maxFeasibleSelectionStaleness | 50.000000 | 1.732051 | 3 | 49.000000 | 52.000000 |
| 1001:M5 | meanFeasibleSelectionStaleness | 13.577778 | 0.753940 | 3 | 12.733333 | 14.183333 |
| 1001:M5 | populationNeverSelected | 40.000000 | 0.000000 | 3 | 40.000000 | 40.000000 |
| 1001:M5 | feasibleNeverSelected | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M5 | acceptedSelectedRatio | 0.952381 | 0.008729 | 3 | 0.942857 | 0.960000 |
| 1001:M5 | virtualSeconds | 139.739435 | 2.657923 | 3 | 137.427635 | 142.643545 |
| 1001:M5 | virtualSecondsWithSelector | 139.778565 | 2.659816 | 3 | 137.466499 | 142.685422 |
| 1001:M5 | wallSeconds | 65.842172 | 0.707363 | 3 | 65.323221 | 66.647890 |
| 1001:M5 | selectorSeconds | 0.035749 | 0.002500 | 3 | 0.033318 | 0.038313 |
| 1001:M5 | fairnessUpdateSeconds | 0.003381 | 0.000163 | 3 | 0.003249 | 0.003564 |
| 1001:M5 | slotsChangedVsTopsis | 209.000000 | 7.549834 | 3 | 202.000000 | 217.000000 |
| 1001:M5 | slotsChangedVsTopsisRatio | 0.597143 | 0.021571 | 3 | 0.577143 | 0.620000 |
| 1001:M5 | meanAppliedLambda | 0.700000 | 0.000000 | 3 | 0.700000 | 0.700000 |
| 1001:M6 | accuracy | 0.705185 | 0.025298 | 3 | 0.679185 | 0.729717 |
| 1001:M6 | macroF1 | 0.430233 | 0.010739 | 3 | 0.418491 | 0.439556 |
| 1001:M6 | loss | 0.669970 | 0.033838 | 3 | 0.635628 | 0.703281 |
| 1001:M6 | worstClassRecall | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M6 | recall0 | 0.528732 | 0.125800 | 3 | 0.419656 | 0.666352 |
| 1001:M6 | recall1 | 0.893729 | 0.042956 | 3 | 0.844335 | 0.922344 |
| 1001:M6 | recall2 | 0.763050 | 0.193147 | 3 | 0.545861 | 0.915548 |
| 1001:M6 | recall3 | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M6 | recall4 | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M6 | recall5 | 0.275346 | 0.259196 | 3 | 0.055300 | 0.561060 |
| 1001:M6 | recall6 | 0.607212 | 0.127859 | 3 | 0.483431 | 0.738791 |
| 1001:M6 | accuracyTailMean | 0.700545 | 0.006933 | 3 | 0.693914 | 0.707745 |
| 1001:M6 | accuracyTailSd | 0.029831 | 0.008397 | 3 | 0.021889 | 0.038619 |
| 1001:M6 | macroF1TailSd | 0.030853 | 0.005886 | 3 | 0.024704 | 0.036436 |
| 1001:M6 | maxAccuracyDropPp | 16.236963 | 1.803133 | 3 | 15.101029 | 18.316065 |
| 1001:M6 | populationSelectionCoverage | 0.600000 | 0.000000 | 3 | 0.600000 | 0.600000 |
| 1001:M6 | populationCompletionCoverage | 0.600000 | 0.000000 | 3 | 0.600000 | 0.600000 |
| 1001:M6 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 3 | 1.000000 | 1.000000 |
| 1001:M6 | feasibleCompletionCoverage | 1.000000 | 0.000000 | 3 | 1.000000 | 1.000000 |
| 1001:M6 | feasibleOpportunityAdjustedGini | 0.473672 | 0.024899 | 3 | 0.452524 | 0.501114 |
| 1001:M6 | feasibleCompletionOpportunityAdjustedGini | 0.473757 | 0.021115 | 3 | 0.460658 | 0.498116 |
| 1001:M6 | selectionGini | 0.684686 | 0.012861 | 3 | 0.674343 | 0.699086 |
| 1001:M6 | completionGini | 0.684815 | 0.010942 | 3 | 0.677605 | 0.697405 |
| 1001:M6 | ramFeasibleCompletionGini | 0.474692 | 0.018236 | 3 | 0.462675 | 0.495675 |
| 1001:M6 | maxFeasibleSelectionStaleness | 50.333333 | 0.577350 | 3 | 50.000000 | 51.000000 |
| 1001:M6 | meanFeasibleSelectionStaleness | 13.511111 | 3.328343 | 3 | 10.100000 | 16.750000 |
| 1001:M6 | populationNeverSelected | 40.000000 | 0.000000 | 3 | 40.000000 | 40.000000 |
| 1001:M6 | feasibleNeverSelected | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M6 | acceptedSelectedRatio | 0.965714 | 0.013093 | 3 | 0.954286 | 0.980000 |
| 1001:M6 | virtualSeconds | 136.018845 | 2.613856 | 3 | 133.049689 | 137.972815 |
| 1001:M6 | virtualSecondsWithSelector | 136.055412 | 2.613680 | 3 | 133.086677 | 138.010188 |
| 1001:M6 | wallSeconds | 66.000589 | 0.799120 | 3 | 65.326814 | 66.883475 |
| 1001:M6 | selectorSeconds | 0.033260 | 0.001147 | 3 | 0.031939 | 0.033993 |
| 1001:M6 | fairnessUpdateSeconds | 0.003307 | 0.000145 | 3 | 0.003140 | 0.003402 |
| 1001:M6 | slotsChangedVsTopsis | 218.666667 | 7.094599 | 3 | 211.000000 | 225.000000 |
| 1001:M6 | slotsChangedVsTopsisRatio | 0.624762 | 0.020270 | 3 | 0.602857 | 0.642857 |
| 1001:M6 | meanAppliedLambda | 0.725000 | 0.000000 | 3 | 0.725000 | 0.725000 |
| 1001:M7 | accuracy | 0.693149 | 0.050346 | 3 | 0.635159 | 0.725689 |
| 1001:M7 | macroF1 | 0.413729 | 0.070075 | 3 | 0.341712 | 0.481686 |
| 1001:M7 | loss | 0.705464 | 0.087294 | 3 | 0.647161 | 0.805825 |
| 1001:M7 | worstClassRecall | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M7 | recall0 | 0.807874 | 0.125791 | 3 | 0.678909 | 0.930230 |
| 1001:M7 | recall1 | 0.684433 | 0.163242 | 3 | 0.507519 | 0.829227 |
| 1001:M7 | recall2 | 0.691275 | 0.225793 | 3 | 0.482103 | 0.930649 |
| 1001:M7 | recall3 | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M7 | recall4 | 0.087018 | 0.075477 | 3 | 0.000000 | 0.134737 |
| 1001:M7 | recall5 | 0.383257 | 0.332537 | 3 | 0.001152 | 0.607143 |
| 1001:M7 | recall6 | 0.267706 | 0.215786 | 3 | 0.020468 | 0.418129 |
| 1001:M7 | accuracyTailMean | 0.696791 | 0.013099 | 3 | 0.683908 | 0.710096 |
| 1001:M7 | accuracyTailSd | 0.036408 | 0.018569 | 3 | 0.021221 | 0.057109 |
| 1001:M7 | macroF1TailSd | 0.035017 | 0.019433 | 3 | 0.015798 | 0.054657 |
| 1001:M7 | maxAccuracyDropPp | 20.102578 | 4.517175 | 3 | 16.574300 | 25.193625 |
| 1001:M7 | populationSelectionCoverage | 0.600000 | 0.000000 | 3 | 0.600000 | 0.600000 |
| 1001:M7 | populationCompletionCoverage | 0.583333 | 0.005774 | 3 | 0.580000 | 0.590000 |
| 1001:M7 | feasibleSelectionCoverage | 1.000000 | 0.000000 | 3 | 1.000000 | 1.000000 |
| 1001:M7 | feasibleCompletionCoverage | 0.972222 | 0.009623 | 3 | 0.966667 | 0.983333 |
| 1001:M7 | feasibleOpportunityAdjustedGini | 0.567630 | 0.014976 | 3 | 0.551352 | 0.580823 |
| 1001:M7 | feasibleCompletionOpportunityAdjustedGini | 0.575442 | 0.018096 | 3 | 0.555546 | 0.590920 |
| 1001:M7 | selectionGini | 0.741219 | 0.008888 | 3 | 0.731143 | 0.747943 |
| 1001:M7 | completionGini | 0.745847 | 0.010833 | 3 | 0.733576 | 0.754085 |
| 1001:M7 | ramFeasibleCompletionGini | 0.576412 | 0.018055 | 3 | 0.555960 | 0.590142 |
| 1001:M7 | maxFeasibleSelectionStaleness | 47.000000 | 1.732051 | 3 | 46.000000 | 49.000000 |
| 1001:M7 | meanFeasibleSelectionStaleness | 18.138889 | 2.321777 | 3 | 15.733333 | 20.366667 |
| 1001:M7 | populationNeverSelected | 40.000000 | 0.000000 | 3 | 40.000000 | 40.000000 |
| 1001:M7 | feasibleNeverSelected | 0.000000 | 0.000000 | 3 | 0.000000 | 0.000000 |
| 1001:M7 | acceptedSelectedRatio | 0.943810 | 0.007190 | 3 | 0.937143 | 0.951429 |
| 1001:M7 | virtualSeconds | 125.489826 | 5.514951 | 3 | 121.813056 | 131.831066 |
| 1001:M7 | virtualSecondsWithSelector | 125.529818 | 5.513051 | 3 | 121.855684 | 131.869026 |
| 1001:M7 | wallSeconds | 66.613283 | 0.092251 | 3 | 66.541868 | 66.717439 |
| 1001:M7 | selectorSeconds | 0.035428 | 0.002343 | 3 | 0.033483 | 0.038030 |
| 1001:M7 | fairnessUpdateSeconds | 0.004564 | 0.000075 | 3 | 0.004478 | 0.004616 |
| 1001:M7 | slotsChangedVsTopsis | 185.000000 | 4.000000 | 3 | 181.000000 | 189.000000 |
| 1001:M7 | slotsChangedVsTopsisRatio | 0.528571 | 0.011429 | 3 | 0.517143 | 0.540000 |
| 1001:M7 | meanAppliedLambda | 0.574612 | 0.019803 | 3 | 0.552675 | 0.591168 |

## Candidate fairness gaps



| Policy | Lambda | Selection coverage max gap | Completion coverage max gap | Selection Gini mean gap | Completion Gini mean gap | Max staleness mean gap | Mean staleness mean gap | All tolerances pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |

Configured tolerances: ``. Selected policy: ; lambda: .

## Paired differences: Adaptive minus Fixed

| Partition | Seed | Fixed policy | Accuracy difference | Tail SD difference | Selection Gini difference |
| --- | --- | --- | ---: | ---: | ---: |

All paired metric differences and their sample SD within each partition are in JSON. Accuracy–Gini points below are descriptive means across balanced partition/seed cells, not a significance or superiority test.

## Observed Accuracy–Gini Pareto analysis

| Policy | Mean accuracy | Mean selection Gini | On observed mean frontier |
| --- | ---: | ---: | --- |
| M1 | 0.710784 | 0.537359 | false |
| M2 | 0.714881 | 0.548008 | false |
| M3 | 0.720078 | 0.517559 | false |
| M4 | 0.702902 | 0.465175 | true |
| M5 | 0.720503 | 0.483767 | true |
| M6 | 0.705185 | 0.473672 | true |
| M7 | 0.693149 | 0.567630 | false |

## Fairness and adaptive trajectories

Per-round Gini/staleness, population never-selected count, applied/next lambda, smoothed Gini, full credit distributions and slots changed vs raw TOPSIS on the same pre-round history are retained under `trajectories` in JSON. Matching tolerances and each candidate's exact gaps are under `fairnessMatching`.

Virtual time includes measured server overhead; virtual time with selector additionally includes measured selector/fairness overhead. Deterministic simulated duration does not make those measured overheads deterministic. No best-test-checkpoint selection, statistical equivalence, or adaptive-superiority claim is made.
