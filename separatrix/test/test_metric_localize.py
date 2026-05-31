#!/usr/bin/env python3
"""Unit tests for divergence-localization (detector/metric.py).

Divergence-localization credits EVERY node where the trajectory diverges from
baseline, not just the first-bifurcation node. For one perturbation it compares
the bucketed edge multisets and, for each edge whose count differs, credits the
edge's SOURCE node with the absolute bucketed-count delta. This is the per-node
signal that localised lua's downstream bugs (Phase-4 AUC 0.93) where
first-bifurcation could not (AUC 0.50).
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector"))
import metric  # noqa: E402


def test_credits_source_node_by_bucketed_delta():
    # base: [1,2,3,2,3] -> edges (1,2):1 (2,3):2 (3,2):1   (bucketed counts)
    # pert: [1,2,4]     -> edges (1,2):1 (2,4):1
    #   (1,2): |1-1|=0 -> skip
    #   (2,3): |2-0|=2 -> node 2 += 2
    #   (3,2): |1-0|=1 -> node 3 += 1
    #   (2,4): |0-1|=1 -> node 2 += 1
    base = metric.edge_multiset([1, 2, 3, 2, 3])
    pert = metric.edge_multiset([1, 2, 4])
    assert metric.localized_divergence(base, pert) == {2: 3, 3: 1}


def test_identical_traces_have_no_divergence():
    e = metric.edge_multiset([1, 2, 3, 2, 3])
    assert metric.localized_divergence(e, e) == {}


def test_matches_sep_eval_inline_accumulation():
    # The reference implementation sep_eval.py inlined: for every differing edge,
    # edge_div[e[0]] += abs(base.get(e,0) - pe.get(e,0)). The helper must be a
    # behaviour-identical extraction so the tool and the eval cannot drift.
    base = metric.edge_multiset([5, 6, 7, 6, 7, 8])
    pert = metric.edge_multiset([5, 6, 9, 9, 9])
    expected = {}
    for e in set(base) | set(pert):
        delta = abs(base.get(e, 0) - pert.get(e, 0))
        if delta:
            expected[e[0]] = expected.get(e[0], 0) + delta
    assert metric.localized_divergence(base, pert) == expected


def test_localized_value_credits_v_to_every_divergent_node():
    # Same edge sets as test_credits_source_node_by_bucketed_delta: divergent
    # source nodes are {2, 3}. localized_value credits the scalar v (not the
    # delta) to each of those nodes -> {2: v, 3: v}.
    base = metric.edge_multiset([1, 2, 3, 2, 3])
    pert = metric.edge_multiset([1, 2, 4])
    assert metric.localized_value(base, pert, 0.4) == {2: 0.4, 3: 0.4}


def test_localized_value_node_set_matches_divergence():
    # The credited node set MUST equal localized_divergence's node set — that
    # identical attribution mechanism is the whole point (isolates value-vs-
    # trajectory *signal* from attribution *method*).
    base = metric.edge_multiset([5, 6, 7, 6, 7, 8])
    pert = metric.edge_multiset([5, 6, 9, 9, 9])
    assert set(metric.localized_value(base, pert, 1.0)) == set(metric.localized_divergence(base, pert))


def test_localized_value_zero_v_credits_zero():
    base = metric.edge_multiset([1, 2, 3, 2, 3])
    pert = metric.edge_multiset([1, 2, 4])
    assert metric.localized_value(base, pert, 0.0) == {2: 0.0, 3: 0.0}


def test_localized_value_identical_traces_credit_nothing():
    e = metric.edge_multiset([1, 2, 3, 2, 3])
    assert metric.localized_value(e, e, 0.7) == {}


def test_conditioned_divergence_is_per_visit_rate():
    # cond[n] = edge_div[n] / visits[n], over the universe.
    #   node 1: 6/3 = 2.0   node 2: 3/3 = 1.0   node 3: absent in edge_div -> 0/10 = 0.0
    edge_div = {1: 6, 2: 3}
    visits = {1: 3, 2: 3, 3: 10}
    universe = [1, 2, 3]
    assert metric.conditioned_divergence(edge_div, visits, universe) == {1: 2.0, 2: 1.0, 3: 0.0}


def test_conditioned_divergence_demotes_hot_confound():
    # The Phase-B mechanism: a HOT node with large raw divergence mass (100) but a
    # huge visit count (1000) must rank BELOW a rarely-executed bug node with modest
    # mass (10) once normalized by coverage. Raw edge_div would rank hot > bug;
    # conditioning flips it (0.1 < 0.5). This is the confound-suppression intent.
    edge_div = {"hot": 100, "bug": 10}
    visits = {"hot": 1000, "bug": 20}
    cond = metric.conditioned_divergence(edge_div, visits, ["hot", "bug"])
    assert cond == {"hot": 0.1, "bug": 0.5}
    assert cond["bug"] > cond["hot"]


def test_conditioned_divergence_restricted_to_universe():
    # edge_div may carry source nodes outside the universe (e.g. filtered out);
    # only universe nodes are scored, and each universe node divides by its visits.
    edge_div = {1: 5, 99: 8}
    visits = {1: 2, 99: 4}
    assert metric.conditioned_divergence(edge_div, visits, [1]) == {1: 2.5}


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
    print(f"metric_localize: {passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())
