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


def test_localized_divergence_edges_keeps_full_edge():
    # The per-EDGE form of localized_divergence: same deltas, but keyed by the
    # whole edge (s,t) instead of collapsed to the source node s. Needed to
    # measure how a node's divergence is distributed across its outgoing edges.
    base = metric.edge_multiset([1, 2, 3, 2, 3])  # (1,2):1 (2,3):2 (3,2):1
    pert = metric.edge_multiset([1, 2, 4])        # (1,2):1 (2,4):1
    assert metric.localized_divergence_edges(base, pert) == {(2, 3): 2, (3, 2): 1, (2, 4): 1}


def test_localized_divergence_edges_collapses_to_node_form():
    # Summing the per-edge form by source node MUST reproduce localized_divergence
    # exactly — the two helpers cannot drift.
    base = metric.edge_multiset([5, 6, 7, 6, 7, 8])
    pert = metric.edge_multiset([5, 6, 9, 9, 9])
    per_edge = metric.localized_divergence_edges(base, pert)
    by_node = {}
    for (s, _t), m in per_edge.items():
        by_node[s] = by_node.get(s, 0) + m
    assert by_node == metric.localized_divergence(base, pert)


def test_dispersion_single_edge_node_scores_zero():
    # A hot loop whose divergence is pure count-inflation on ONE outgoing edge
    # (the back-edge) has H=0 -> suppressed entirely, regardless of mass.
    edge_div_by_edge = {("hot", "loop"): 100}
    assert metric.dispersion_weighted_divergence(edge_div_by_edge, ["hot"]) == {"hot": 0.0}


def test_dispersion_weights_by_outgoing_entropy():
    import math
    # bug node: divergence split evenly over TWO outgoing edges (a branch flip)
    #   total=10, p=.5/.5, H=ln2 -> score = 10*ln2
    # hot node: 100 mass on one edge -> H=0 -> 0
    edge_div_by_edge = {("hot", "x"): 100, ("bug", "a"): 5, ("bug", "b"): 5}
    out = metric.dispersion_weighted_divergence(edge_div_by_edge, ["hot", "bug"])
    assert out["hot"] == 0.0
    assert abs(out["bug"] - 10 * math.log(2)) < 1e-12
    assert out["bug"] > out["hot"]   # the headline intent: branch-flip beats hot loop


def test_dispersion_skewed_split_scores_below_even_split():
    # Same total mass, but an even 2-way split has higher entropy than a skewed
    # one, so the evenly-flipping branch outranks the lopsided one.
    even = metric.dispersion_weighted_divergence({("n", "a"): 5, ("n", "b"): 5}, ["n"])["n"]
    skew = metric.dispersion_weighted_divergence({("n", "a"): 9, ("n", "b"): 1}, ["n"])["n"]
    assert even > skew > 0.0


def test_dispersion_restricted_to_universe_and_absent_scores_zero():
    # Edges from non-universe sources are ignored; a universe node with no
    # divergence edges scores 0 (not KeyError).
    edge_div_by_edge = {("a", "x"): 3, ("a", "y"): 3, ("z", "w"): 9}
    out = metric.dispersion_weighted_divergence(edge_div_by_edge, ["a", "cold"])
    assert set(out) == {"a", "cold"}
    assert out["cold"] == 0.0
    assert out["a"] > 0.0


def test_excess_divergence_is_failing_mean_minus_passing_mean():
    # Per-node mean divergence-to-baseline among FAILING runs, minus the same among
    # PASSING runs, clamped at 0 (the campaign port of suite div_excess).
    #   node "bug": fail mass 20 over 2 fail runs = 10 ; pass mass 6 over 3 = 2 ; excess 8
    #   node "hot": fail 30/2 = 15 ; pass 60/3 = 20 ; 15-20 < 0 -> clamp 0
    div_fail = {"bug": 20, "hot": 30}
    div_pass = {"bug": 6, "hot": 60}
    out = metric.excess_divergence(div_fail, 2, div_pass, 3, ["bug", "hot"])
    assert out == {"bug": 8.0, "hot": 0.0}


def test_excess_divergence_absent_node_scores_zero():
    out = metric.excess_divergence({"a": 4}, 2, {}, 2, ["a", "cold"])
    assert out == {"a": 2.0, "cold": 0.0}


def test_excess_divergence_no_passing_runs_is_pure_failing_mean():
    # P=0 -> passing baseline is 0, excess collapses to the failing mean (no subtraction).
    out = metric.excess_divergence({"a": 10}, 5, {}, 0, ["a"])
    assert out == {"a": 2.0}


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
