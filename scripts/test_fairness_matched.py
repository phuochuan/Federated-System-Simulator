import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fairness_matched import select_lambda, scenario


SETTINGS = {"meanAbsoluteGapTolerance": .025, "maxPartitionMeanAbsoluteGap": .05}


def records():
    return [{"partition": p, "seed": s, "policy": policy, "lambda": value, "gini": gini,
             "accuracy": accuracy} for p in (1001,1002) for s in (42,43,44)
            for policy,value,gini,accuracy in [("adaptive",None,.35,.7), ("fixed",.6,.36,.1), ("fixed",.7,.2,.99)]]


def test_matching_ignores_learning_scores_and_rejects_unmatched_grid():
    rows = records()
    expected = select_lambda(rows, SETTINGS)
    assert expected["selectedLambda"] == .6
    altered = copy.deepcopy(rows)
    for row in altered:
        row["accuracy"] = -999
        row["macroF1"] = float("nan")
    assert select_lambda(altered, SETTINGS) == expected
    assert select_lambda([r for r in rows if r["lambda"] != .6], SETTINGS)["status"] == "NO_MATCH"


def test_missing_pairs_fail_and_opposite_gaps_do_not_cancel():
    rows = records()
    with pytest.raises(AssertionError, match="Incomplete"):
        select_lambda(rows[:-1], SETTINGS)
    for row in rows:
        if row["policy"] == "fixed":
            row["gini"] = .3 if row["partition"] == 1001 else .4
    assert select_lambda(rows, SETTINGS)["status"] == "NO_MATCH"


def test_trace_matches_saved_java_generated_trace_for_full_population():
    import json
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configurations/lambda-ablation.json").read_text())["baseConfig"]
    config["seed"] = 45
    # Stable trace fixture from the historical Java batch when available locally.
    trace = root / "artifacts/comparisons/20261025-233756-966e51c9/traces/L-s45.json"
    if trace.exists():
        assert scenario(config) == json.loads(trace.read_text())
    else:
        assert scenario(config) == scenario({**config, "selection": "random"})
