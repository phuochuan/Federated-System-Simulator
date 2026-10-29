# Seed 45: frozen-runtime F5/L5 audit

Evidence: `artifacts/seed45-audit/20261027-183349`

F5 and L5 use the same adaptive policy and normalized configuration. Historical builds were not frozen; their gitDirty snapshots cannot identify exact source/binary contents. Historical results are reported separately from fresh repeats.

All score/credit/controller replays and timing-history/feasibility checks passed. Initial tensor hash, full manifest and exogenous trace hash match across all runs. Repeat runtime and partition hashes remained unchanged.

## Historical comparison

| Metric | F5 | L5 |
| --- | ---: | ---: |
| accuracy | 0.57717595 | 0.70034939 |
| macroF1 | 0.33880536 | 0.43313176 |
| loss | 0.98839137 | 0.68205259 |
| coverage | 0.60000000 | 0.60000000 |
| feasibleSelectionGini | 0.32832859 | 0.35136909 |
| finalLambda | 0.58685015 | 0.73475100 |
| virtualSeconds | 26.23595930 | 13.70262054 |
| wallSeconds | 213.37740290 | 121.95829540 |
| meanTrainingMs | 221.19054400 | 127.27921200 |
| accepted | 340.00000000 | 332.00000000 |

Decision differences (ordered lists and sets are distinguished):

```json
{
  "left": "matrix-20261025-210944-391f30e9-F5-s45",
  "right": "matrix-20261025-233756-966e51c9-L5-s45",
  "differences": {
    "selectedIdsEqual": {
      "roundCount": 69,
      "firstRound": 2
    },
    "acceptedIdsEqual": {
      "roundCount": 64,
      "firstRound": 7
    },
    "estimatedFeasibleIdsEqual": {
      "roundCount": 0,
      "firstRound": null
    },
    "criteriaObservationsEqual": {
      "roundCount": 69,
      "firstRound": 2
    },
    "fuzzyTopsisScoresEqual": {
      "roundCount": 69,
      "firstRound": 2
    },
    "fairnessCreditsEqual": {
      "roundCount": 63,
      "firstRound": 8
    },
    "currentFairnessLambdaEqual": {
      "roundCount": 63,
      "firstRound": 8
    },
    "selectedSetEqual": {
      "roundCount": 64,
      "firstRound": 7
    },
    "acceptedSetEqual": {
      "roundCount": 64,
      "firstRound": 7
    }
  },
  "changedSlots": 246,
  "selectedSlots": 350,
  "maxEstimatedTimeDeltaSeconds": 2.0702316000009886
}
```

## Fresh repeats

Serial runs, fresh services per repeat; F5/L5 labels are aliases for the same config. No other experiments were launched by this audit. Background OS load remains uncontrolled.

| Metric | Mean | Sample SD | Min | Max | CV |
| --- | ---: | ---: | ---: | ---: | ---: |
| accuracy | 0.72396129 | 0.00590609 | 0.71673465 | 0.72986696 | 0.0082 |
| macroF1 | 0.40043848 | 0.02231955 | 0.37120678 | 0.42126165 | 0.0557 |
| loss | 0.64590227 | 0.00723821 | 0.63966773 | 0.65410006 | 0.0112 |
| coverage | 0.59750000 | 0.00500000 | 0.59000000 | 0.60000000 | 0.0084 |
| feasibleSelectionGini | 0.34818859 | 0.03764005 | 0.31271371 | 0.39739891 | 0.1081 |
| finalLambda | 0.55606951 | 0.09114138 | 0.43699322 | 0.63847886 | 0.1639 |
| virtualSeconds | 18.71333658 | 3.57224046 | 16.29481693 | 23.97394726 | 0.1909 |
| wallSeconds | 154.30894363 | 17.17390021 | 129.50557090 | 168.86733170 | 0.1113 |
| meanTrainingMs | 155.88242200 | 21.84306733 | 125.43658943 | 177.06227286 | 0.1401 |
| accepted | 335.25000000 | 2.62995564 | 333.00000000 | 339.00000000 | 0.0078 |

Four repeats of one seed estimate conditional run-to-run variability; they do not estimate across-seed uncertainty or establish an F5/L5 treatment effect. Physical training duration feeds the next-round estimatedTime criterion and virtual completion time, so deterministic ML seeds do not guarantee deterministic decisions. Consult per-round CSVs for the first order/set divergence and timing deltas.
