#!/usr/bin/env python3
"""Unit tests for Phase-4 evaluation metrics (eval/eval_metrics.py).

Hand-computed fixtures for ROC-AUC, precision@k, and average precision. Runs
under pytest or standalone (`python3 test_eval_metrics.py`), matching the repo's
verify_*.py convention.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval"))
import eval_metrics as em  # noqa: E402

EPS = 1e-9


def approx(a, b):
    return abs(a - b) < EPS


# ---- ROC-AUC (rank-based / Mann-Whitney, ties = 0.5) ----

def test_auc_perfect_ranking():
    assert approx(em.roc_auc([0.9, 0.8, 0.7, 0.6], [1, 1, 0, 0]), 1.0)


def test_auc_worst_ranking():
    assert approx(em.roc_auc([0.9, 0.8, 0.7, 0.6], [0, 0, 1, 1]), 0.0)


def test_auc_all_tied_is_half():
    assert approx(em.roc_auc([5, 5, 5, 5], [1, 0, 1, 0]), 0.5)


def test_auc_intermediate():
    # positives have scores 3 and 1; negatives 2 and 0.
    # concordant pos>neg pairs: (3>2),(3>0),(1>0) = 3 of 4 -> 0.75
    assert approx(em.roc_auc([3, 2, 1, 0], [1, 0, 1, 0]), 0.75)


def test_auc_tie_between_pos_and_neg_counts_half():
    # pos=2; negs={2,1}. vs 2 -> tie(0.5), vs 1 -> 1.  (0.5+1)/2 = 0.75
    assert approx(em.roc_auc([2, 2, 1], [1, 0, 0]), 0.75)


# ---- precision@k (sort by -score, ties broken by original index) ----

def test_precision_at_k_top_all_positive():
    assert approx(em.precision_at_k([0.9, 0.8, 0.7, 0.6], [1, 1, 0, 0], 2), 1.0)


def test_precision_at_k_full_list():
    assert approx(em.precision_at_k([0.9, 0.8, 0.7, 0.6], [1, 1, 0, 0], 4), 0.5)


def test_precision_at_k_caps_at_list_length():
    # k larger than n -> denominator is n
    assert approx(em.precision_at_k([0.9, 0.8], [1, 0], 10), 0.5)


# ---- average precision ----

def test_average_precision_perfect():
    assert approx(em.average_precision([0.9, 0.8, 0.7, 0.6], [1, 1, 0, 0]), 1.0)


def test_average_precision_interleaved():
    # positives at ranks 1 and 3: (p@1 + p@3)/2 = (1 + 2/3)/2 = 0.8333...
    assert approx(em.average_precision([4, 3, 2, 1], [1, 0, 1, 0]), (1.0 + 2.0 / 3.0) / 2.0)


def test_average_precision_no_positives_is_zero():
    assert approx(em.average_precision([1, 2, 3], [0, 0, 0]), 0.0)


# ---- value-space output distance (normalized edit distance in [0,1]) ----

def test_value_distance_identical_is_zero():
    assert approx(em.value_distance("S0 42", "S0 42"), 0.0)


def test_value_distance_both_empty_is_zero():
    assert approx(em.value_distance("", ""), 0.0)


def test_value_distance_disjoint_is_one():
    assert approx(em.value_distance("abc", ""), 1.0)


def test_value_distance_single_edit_normalized():
    # one substitution over length 3
    assert approx(em.value_distance("abc", "abd"), 1.0 / 3.0)


# ---- bootstrap CI on AUC (stratified, percentile interval) ----

def test_bootstrap_ci_perfect_ranking_is_degenerate():
    # all positives outrank all negatives, so EVERY stratified resample has
    # AUC=1.0 -> the CI collapses to (1.0, 1.0).
    lo, hi = em.bootstrap_auc_ci([4, 3, 2, 1], [1, 1, 0, 0], n_boot=500, seed=0)
    assert approx(lo, 1.0) and approx(hi, 1.0)


def test_bootstrap_ci_all_tied_is_half():
    lo, hi = em.bootstrap_auc_ci([5, 5, 5, 5], [1, 1, 0, 0], n_boot=500, seed=0)
    assert approx(lo, 0.5) and approx(hi, 0.5)


def test_bootstrap_ci_lo_le_hi_and_in_unit_interval():
    lo, hi = em.bootstrap_auc_ci([5, 4, 3, 2, 1, 0], [1, 0, 1, 0, 1, 0], n_boot=500, seed=1)
    assert 0.0 <= lo <= hi <= 1.0


def test_bootstrap_ci_no_positives_is_half():
    lo, hi = em.bootstrap_auc_ci([3, 2, 1], [0, 0, 0], n_boot=200, seed=0)
    assert approx(lo, 0.5) and approx(hi, 0.5)


def test_bootstrap_ci_deterministic():
    a = em.bootstrap_auc_ci([5, 4, 3, 2, 1, 0], [1, 0, 1, 0, 1, 0], n_boot=300, seed=7)
    b = em.bootstrap_auc_ci([5, 4, 3, 2, 1, 0], [1, 0, 1, 0, 1, 0], n_boot=300, seed=7)
    assert a == b


# ---- permutation null on AUC (label-shuffle p-value, add-one) ----

def test_permutation_p_in_unit_interval():
    p = em.permutation_test_auc([4, 3, 2, 1], [1, 1, 0, 0], n_perm=200, seed=0)
    assert 0.0 < p <= 1.0


def test_permutation_strong_signal_small_p():
    # 5 vs 5 perfectly ranked: only 1 of C(10,5)=252 label arrangements ties the
    # observed AUC=1.0, so the permutation p is ~1/252 << 0.05.
    scores = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    labels = [1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    p = em.permutation_test_auc(scores, labels, n_perm=2000, seed=0)
    assert p < 0.05


def test_permutation_no_signal_p_is_one():
    # all tied -> every permutation AUC == observed (0.5) -> p == 1.0
    p = em.permutation_test_auc([5, 5, 5, 5], [1, 1, 0, 0], n_perm=200, seed=0)
    assert approx(p, 1.0)


def test_permutation_deterministic():
    args = ([5, 4, 3, 2, 1, 0], [1, 0, 1, 0, 1, 0])
    assert (em.permutation_test_auc(*args, n_perm=300, seed=3)
            == em.permutation_test_auc(*args, n_perm=300, seed=3))


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
        except AssertionError:
            print(f"  [FAIL] {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR ] {fn.__name__}: {e}")
    print(f"eval_metrics: {passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())
