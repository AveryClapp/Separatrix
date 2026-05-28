#!/usr/bin/env python3
"""Unit tests for spectrum-based fault localization formulas (eval/sbfl.py).

Hand-computed fixtures over (ef, ep, F, P): ef/ep = #failing/#passing runs that
executed the node; F/P = total failing/passing runs. All three formulas are
higher = more suspicious so they slot into the existing higher-is-better metrics.
"""
import math, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval"))
import sbfl  # noqa: E402


def _close(a, b, eps=1e-9):
    return abs(a - b) < eps


def test_ochiai_basic():
    # ef=4, ep=2, F=5: 4 / sqrt(5 * (4+2)) = 4 / sqrt(30)
    assert _close(sbfl.ochiai(4, 2, 5, 10), 4.0 / math.sqrt(30.0))


def test_ochiai_zero_ef_is_zero():
    assert sbfl.ochiai(0, 2, 5, 10) == 0.0


def test_ochiai_zero_F_is_zero():
    assert sbfl.ochiai(0, 2, 0, 10) == 0.0


def test_tarantula_basic():
    # (4/5) / (4/5 + 2/10) = 0.8 / (0.8 + 0.2) = 0.8
    assert _close(sbfl.tarantula(4, 2, 5, 10), 0.8)


def test_tarantula_zero_F_is_zero():
    assert sbfl.tarantula(0, 2, 0, 10) == 0.0


def test_tarantula_zero_P_no_passing_is_one():
    # No passing runs -> ep-rate is 0 -> a node hit by failing runs is maximally
    # suspicious (1.0); never a division by zero.
    assert _close(sbfl.tarantula(3, 0, 5, 0), 1.0)


def test_dstar_basic():
    # star=2: ef^2 / (ep + nf), nf = F - ef = 1 -> 16 / (2 + 1)
    assert _close(sbfl.dstar(4, 2, 5, 10), 16.0 / 3.0)


def test_dstar_zero_denominator_is_finite_not_inf():
    # all-failing / no-passing (ef=F, ep=0, nf=0): denom 0 must NOT be inf
    # (inf breaks rank-sum AUC and sorts unpredictably). Finite sentinel.
    s = sbfl.dstar(5, 0, 5, 10)
    assert math.isfinite(s)
    assert s == 25.0 / sbfl.EPS


def test_dstar_all_failing_nodes_tie_and_outrank_finite():
    # Two all-failing/no-passing nodes tie (finite, equal); a finite-denominator
    # node with the same ef ranks strictly below them.
    a = sbfl.dstar(5, 0, 5, 10)
    b = sbfl.dstar(5, 0, 5, 10)
    finite = sbfl.dstar(5, 1, 5, 10)   # 25 / (1 + 0) = 25
    assert a == b
    assert a > finite
    assert math.isfinite(a) and math.isfinite(finite)


def test_score_all_over_universe():
    # universe includes a node never executed in a failing run (ef=0) -> score 0.
    universe = [10, 20, 30, 40]
    ef = {10: 5, 20: 5, 30: 5}        # 40 absent -> ef=0
    ep = {10: 0, 20: 0, 30: 1, 40: 7}
    sc = sbfl.score_all(ef, ep, F=5, P=10, universe=universe, formula="dstar")
    assert set(sc) == set(universe)
    assert sc[10] == sc[20]           # both all-failing/no-passing -> tie
    assert sc[10] > sc[30]            # finite-denominator node ranks below
    assert sc[40] == 0.0              # never in a failing run
    assert all(math.isfinite(v) for v in sc.values())


def test_score_all_unknown_formula_raises():
    try:
        sbfl.score_all({}, {}, 1, 1, [1], "nope")
    except (ValueError, KeyError):
        return
    raise AssertionError("expected an error for an unknown formula")


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
    print(f"sbfl: {passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())
