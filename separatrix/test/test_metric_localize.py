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
