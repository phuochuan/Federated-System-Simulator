# Fuzzy MCDM research summary

Workflow status: BLOCKED. Stage: E3.

## 1. Research objectives and hypotheses

RQ1-RQ4 evaluate effectiveness and robustness without assuming Fuzzy superiority.

## 2. Existing Fuzzy TOPSIS formulation

Data-derived componentwise fuzzy ideals, vertex distances summed by criterion; see docs/fuzzy-mcdm-client-selection.md.

## 3. Uncertainty measurement

37245 observed outcomes, 633715 missing. See e0-uncertainty-measurement.json. Selection bias prevents population-wide interpretation.

## 4. Crisp vs Fuzzy comparison

See e1-crisp-fuzzy-ablation.json and ranking CSV; conventional Crisp and zero-width Fuzzy differ mathematically.

## 5. Ranking sensitivity

Bounded 100-state immutable replay sample at widths 0/.1/.3. No counterfactual FL claim.

## 6. Uncertainty robustness

See E2 JSON/CSV. Noise affects observations only; deterministic full-population scenario traces are paired.

## 7. Prediction-error calibration

{"calibrationEligible": true, "pairedProxyAccuracyDifference": {"n": 6, "mean": 0.0029832593255538775, "sampleSD": 0.022360509310363524, "minimum": -0.03803655640081238, "maximum": 0.026918178375959445}, "pairedValidationRuns": 6, "requiredPairs": 6, "matureObservationFraction": 0.8223809523809524, "interpretation": "Validation screening only, not statistical evidence of superiority. Baselines retained when sparse or worse."}

## 8. End-to-end FL results

See e3-heldout-results.json. Only completed final-round checkpoints enter held-out summaries.

## 9. Accuracy, Macro-F1, fairness and efficiency comparisons

CSV exports include proxy trajectories, final per-class recall, efficiency, opportunity Gini, staleness and stability. Per-run partition identities remain explicit.

## 10. Reproducibility and runtime provenance

runtime-identity.json, protocol.json, trace files, policy-lock.json and e0-reproducibility-audit.json identify this executing batch.

## 11. Limitations

Two-seed pilots support screening. Correlated seed repeats within partitions are not independent partitions. Sample SD and ranges are descriptive uncertainty summaries, not significance tests. Deterministic timing is a simulator model; physical runtime differs. No recovery guarantee for power loss, sleep or full disk.

## 12. Supported and unsupported research claims

No automatic superiority claim. Missing/incomplete outcomes remain explicit. Offline rank changes do not establish FL improvement.

Actual completed-run accuracy summaries:

```json
{
  "E2/C1/U0/alpha=0.5": {
    "n": 2,
    "mean": 0.7192179270937318,
    "sampleSD": 0.011829331026699976,
    "minimum": 0.7108533269078517,
    "maximum": 0.7275825272796117
  },
  "E2/C2/U0/alpha=0.5": {
    "n": 2,
    "mean": 0.7109738046883067,
    "sampleSD": 0.00021906168567968298,
    "minimum": 0.7108189046848645,
    "maximum": 0.711128704691749
  },
  "E2/C3/U0/alpha=0.5": {
    "n": 2,
    "mean": 0.7122302158273381,
    "sampleSD": 0.0015577719870550873,
    "minimum": 0.711128704691749,
    "maximum": 0.7133317269629272
  },
  "E2/C4/U0/alpha=0.5": {
    "n": 2,
    "mean": 0.7109221713538261,
    "sampleSD": 9.736074919095277e-05,
    "minimum": 0.7108533269078517,
    "maximum": 0.7109910157998004
  },
  "E2/C1/U1/alpha=0.5": {
    "n": 2,
    "mean": 0.7123334824962997,
    "sampleSD": 0.026871566776701317,
    "minimum": 0.693332415407387,
    "maximum": 0.7313345495852123
  },
  "E2/C2/U1/alpha=0.5": {
    "n": 2,
    "mean": 0.7117310935940242,
    "sampleSD": 0.004308213151699386,
    "minimum": 0.7086847268596606,
    "maximum": 0.714777460328388
  },
  "E2/C3/U1/alpha=0.5": {
    "n": 2,
    "mean": 0.7127121269491583,
    "sampleSD": 0.004089151466019781,
    "minimum": 0.7098206602182369,
    "maximum": 0.7156035936800799
  },
  "E2/C4/U1/alpha=0.5": {
    "n": 2,
    "mean": 0.7199752159994492,
    "sampleSD": 0.01518827687378769,
    "minimum": 0.7092354824274552,
    "maximum": 0.7307149495714433
  },
  "E2/C1/U2/alpha=0.5": {
    "n": 2,
    "mean": 0.6967918488175966,
    "sampleSD": 0.04086717447289987,
    "minimum": 0.6678943926198754,
    "maximum": 0.7256893050153179
  },
  "E2/C2/U2/alpha=0.5": {
    "n": 2,
    "mean": 0.7090461602010258,
    "sampleSD": 0.00041378318406158854,
    "minimum": 0.7087535713056349,
    "maximum": 0.7093387490964167
  },
  "E2/C3/U2/alpha=0.5": {
    "n": 2,
    "mean": 0.7094936490998589,
    "sampleSD": 0.000657185057038892,
    "minimum": 0.7090289490895322,
    "maximum": 0.7099583491101855
  },
  "E2/C4/U2/alpha=0.5": {
    "n": 2,
    "mean": 0.7081339712918661,
    "sampleSD": 0.001314370114077784,
    "minimum": 0.7072045712712127,
    "maximum": 0.7090633713125194
  },
  "E4/C5/U0/alpha=0.5": {
    "n": 2,
    "mean": 0.7176861381708031,
    "sampleSD": 0.008689446865292024,
    "minimum": 0.7115417713675949,
    "maximum": 0.7238305049740112
  },
  "E4/C5/U1/alpha=0.5": {
    "n": 2,
    "mean": 0.7083060824068018,
    "sampleSD": 0.022100890066344865,
    "minimum": 0.692678393170631,
    "maximum": 0.7239337716429727
  },
  "E4/C5/U2/alpha=0.5": {
    "n": 2,
    "mean": 0.7219889160441981,
    "sampleSD": 0.01715983204490429,
    "minimum": 0.7098550824412241,
    "maximum": 0.7341227496471722
  }
}
```
