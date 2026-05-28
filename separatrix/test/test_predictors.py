#!/usr/bin/env python3
"""Unit tests for Phase-4 predictors (eval/predictors.py).

A predictor maps the shared campaign observations to a per-node score. All
predictors must score over the SAME node universe so the rankings are
comparable. An observation is (bifurcation_node, trajectory_d, value_d).
"""
import os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval"))
import predictors as pr  # noqa: E402


# bif node, trajectory divergence d, value-space distance v
OBS = [
    {"node": 10, "d": 5, "v": 2},
    {"node": 10, "d": 3, "v": 0},
    {"node": 20, "d": 4, "v": 7},
    {"node": None, "d": 9, "v": 9},   # unattributed -> ignored
]
UNIVERSE = [10, 20, 30]   # 30 executed but never a bifurcation point


def test_trajectory_sums_d_per_node_over_universe():
    s = pr.trajectory(OBS, UNIVERSE)
    assert s == {10: 8, 20: 4, 30: 0}


def test_value_sums_v_per_node_over_universe():
    s = pr.value(OBS, UNIVERSE)
    assert s == {10: 2, 20: 7, 30: 0}


def test_coverage_is_visit_frequency_over_universe():
    visits = {10: 100, 20: 5}   # 30 missing -> 0
    s = pr.coverage(visits, UNIVERSE)
    assert s == {10: 100, 20: 5, 30: 0}


def test_random_scores_cover_universe_and_are_deterministic():
    a = pr.random_scores(UNIVERSE, random.Random(42))
    b = pr.random_scores(UNIVERSE, random.Random(42))
    assert set(a) == set(UNIVERSE)
    assert a == b                       # seeded -> reproducible
    assert len(set(a.values())) > 1     # not all identical


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1
        except AssertionError:
            print(f"  [FAIL] {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR ] {fn.__name__}: {e}")
    print(f"predictors: {passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())
