# Crisp versus fuzzy diagnostic

Conventional Crisp uses column L2 normalization, weighted extrema ideals, Euclidean distance. Existing zero-width Fuzzy uses benefit maximum/cost reciprocal normalization and sums absolute criterion distances. They need not agree. Both tie by ascending client ID; identical alternatives score 0.5.

{
  "status": "OFFLINE_REPLAY",
  "decisionSampleLimit": 100,
  "topKOverlap": {
    "C1/width=0.0": {
      "n": 100,
      "mean": 1.0,
      "sampleSD": 0.0,
      "minimum": 1.0,
      "maximum": 1.0
    },
    "C2/width=0.0": {
      "n": 100,
      "mean": 0.912,
      "sampleSD": 0.09977753031397175,
      "minimum": 0.8,
      "maximum": 1.0
    },
    "C3/width=0.0": {
      "n": 100,
      "mean": 0.912,
      "sampleSD": 0.09977753031397175,
      "minimum": 0.8,
      "maximum": 1.0
    },
    "C4/width=0.0": {
      "n": 100,
      "mean": 0.908,
      "sampleSD": 0.1079468630971982,
      "minimum": 0.6,
      "maximum": 1.0
    },
    "C1/width=0.1": {
      "n": 100,
      "mean": 1.0,
      "sampleSD": 0.0,
      "minimum": 1.0,
      "maximum": 1.0
    },
    "C2/width=0.1": {
      "n": 100,
      "mean": 0.912,
      "sampleSD": 0.09977753031397175,
      "minimum": 0.8,
      "maximum": 1.0
    },
    "C3/width=0.1": {
      "n": 100,
      "mean": 0.908,
      "sampleSD": 0.1079468630971982,
      "minimum": 0.6,
      "maximum": 1.0
    },
    "C4/width=0.1": {
      "n": 100,
      "mean": 0.908,
      "sampleSD": 0.11518978630367739,
      "minimum": 0.4,
      "maximum": 1.0
    },
    "C1/width=0.3": {
      "n": 100,
      "mean": 1.0,
      "sampleSD": 0.0,
      "minimum": 1.0,
      "maximum": 1.0
    },
    "C2/width=0.3": {
      "n": 100,
      "mean": 0.912,
      "sampleSD": 0.09977753031397175,
      "minimum": 0.8,
      "maximum": 1.0
    },
    "C3/width=0.3": {
      "n": 100,
      "mean": 0.896,
      "sampleSD": 0.11884970561702086,
      "minimum": 0.4,
      "maximum": 1.0
    },
    "C4/width=0.3": {
      "n": 100,
      "mean": 0.902,
      "sampleSD": 0.11890068854877894,
      "minimum": 0.4,
      "maximum": 1.0
    }
  },
  "interpretation": "Same immutable state. No model updates; these are not counterfactual FL outcomes. Spearman uses ID tie-broken strict ranks; tied score counts are exported."
}
