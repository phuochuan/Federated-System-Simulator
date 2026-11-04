import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('synthesis', Path(__file__).with_name('synthesize_research_results.py'))
synthesis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synthesis)


def test_scope_does_not_double_count_pilot():
    runs = synthesis.read_runs()
    assert len(runs) == 450
    assert sum(r['stage'] == 'E3' for r in runs) == 135
    assert sum(r['stage'] == 'E4' for r in runs) == 6
    assert len({r['experiment'] for r in runs}) == 450


def test_seed_repeats_are_not_independent_clusters():
    rows = [dict(partition=1, difference=1), dict(partition=1, difference=3),
            dict(partition=2, difference=4), dict(partition=3, difference=-3)]
    result = synthesis.cluster_summary(rows)
    assert result['independentPartitions'] == 3
    assert result['descriptiveSeedPairs'] == 4
    assert result['mean'] == 1
    assert result['partitionEffects'][1] == 2
    assert result['leaveOnePartitionOut'][1] == .5


def test_actual_controlled_effects_match_independent_reference():
    result, _ = synthesis.comparisons(synthesis.read_runs())
    expected = {'A2': -.0025637347989803205, 'A3': -.0012830148266715542, 'A4': -.0073337808299340805}
    for policy, value in expected.items():
        item = result[f'controlled-width-ablation/{policy}-A1/accuracy/all']
        assert item['mean'] == pytest.approx(value, abs=1e-12)
        assert item['independentPartitions'] == 3
        assert item['descriptiveSeedPairs'] == 45
    assert result['controlled-width-ablation/A3-A1/accuracy/alpha=0.1']['mean'] == pytest.approx(.0106205857615768, abs=1e-9)
