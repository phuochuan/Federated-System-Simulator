# Prediction-error calibration

Past selected-client residuals only; nearest-rank 80th percentile of last 32 absolute relative time errors and absolute reliability errors. Minimum five; prior .1; cap .45. Utility retains prior width because no validated utility prediction target exists. History-based equations are unchanged.

{
  "calibrationEligible": true,
  "pairedProxyAccuracyDifference": {
    "n": 6,
    "mean": 0.0029832593255538775,
    "sampleSD": 0.022360509310363524,
    "minimum": -0.03803655640081238,
    "maximum": 0.026918178375959445
  },
  "pairedValidationRuns": 6,
  "requiredPairs": 6,
  "matureObservationFraction": 0.8223809523809524,
  "interpretation": "Validation screening only, not statistical evidence of superiority. Baselines retained when sparse or worse."
}
