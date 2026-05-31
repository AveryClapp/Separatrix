"""Hand-computed tests for the step-attribution scoring metrics (score.py).

Run: ../.venv/bin/python test_score.py   (pure-python; no deps needed for these)
Every expected value below is hand-computable from the docstring conventions.
"""
import score


def _approx(a, b, eps=1e-9):
    assert abs(a - b) < eps, f"expected {b}, got {a}"


def test_rank_of_descending_no_ties():
    # higher score = better = lower (closer to 1) rank
    s = [0.9, 0.5, 0.1]
    _approx(score.rank_of(s, 0), 1.0)
    _approx(score.rank_of(s, 1), 2.0)
    _approx(score.rank_of(s, 2), 3.0)


def test_rank_of_ties_get_average_rank():
    # idx0,idx1 tied at top -> each gets average of ranks {1,2} = 1.5
    _approx(score.rank_of([0.5, 0.5, 0.1], 0), 1.5)
    _approx(score.rank_of([0.5, 0.5, 0.1], 1), 1.5)
    # bottom two tied -> ranks {2,3} -> 2.5
    _approx(score.rank_of([0.9, 0.4, 0.4], 1), 2.5)
    # all equal -> (1+2+3)/3 = 2.0
    _approx(score.rank_of([0.3, 0.3, 0.3], 0), 2.0)


def test_reciprocal_rank_is_one_over_rank():
    _approx(score.reciprocal_rank([0.9, 0.5, 0.1], 0), 1.0)
    _approx(score.reciprocal_rank([0.9, 0.5, 0.1], 1), 0.5)
    _approx(score.reciprocal_rank([0.5, 0.5, 0.1], 0), 1.0 / 1.5)


def test_mrr_averages_reciprocal_ranks_over_instances():
    instances = [([0.9, 0.5, 0.1], 0), ([0.9, 0.5, 0.1], 1)]
    _approx(score.mrr(instances), (1.0 + 0.5) / 2.0)


def test_expected_top1_handles_ties_by_random_tiebreak_probability():
    _approx(score.expected_top1([0.9, 0.5, 0.1], 0), 1.0)   # unique max
    _approx(score.expected_top1([0.9, 0.5, 0.1], 1), 0.0)   # not max
    _approx(score.expected_top1([0.5, 0.5, 0.1], 0), 0.5)   # tied with one
    _approx(score.expected_top1([0.3, 0.3, 0.3], 0), 1.0 / 3.0)


def test_exam_is_fraction_of_others_ranked_above():
    _approx(score.exam([0.9, 0.5, 0.1], 0), 0.0)            # best -> examine none
    _approx(score.exam([0.9, 0.5, 0.1], 1), 0.5)            # (2-1)/2
    _approx(score.exam([0.9, 0.5, 0.1], 2), 1.0)            # worst -> examine all others
    _approx(score.exam([0.5, 0.5, 0.1], 0), 0.25)          # (1.5-1)/2
    _approx(score.exam([0.9], 0), 0.0)                      # single candidate


def test_top1_accuracy_and_mean_exam_aggregate_over_instances():
    inst = [([0.9, 0.5, 0.1], 0), ([0.9, 0.5, 0.1], 2)]
    _approx(score.top1_accuracy(inst), (1.0 + 0.0) / 2.0)
    _approx(score.mean_exam(inst), (0.0 + 1.0) / 2.0)


def test_separation_delta_mrr_and_wilcoxon_direction():
    # flip ranks target #1 (RR=1.0); div ranks it uniquely last (RR=1/3). 6 pairs.
    flip = [([1.0, 0.0, 0.0], 0)] * 6
    div = [([0.1, 0.2, 0.3], 0)] * 6
    sep = score.separation(flip, div)
    _approx(sep["mrr_flip"], 1.0)
    _approx(sep["mrr_div"], 1.0 / 3.0)
    _approx(sep["delta_mrr"], 1.0 - 1.0 / 3.0)
    assert sep["n"] == 6
    assert sep["wilcoxon_p"] < 0.05, sep["wilcoxon_p"]
    # reversed: flip is now worse than div -> one-sided (flip>div) p must be large
    sep_rev = score.separation(div, flip)
    assert sep_rev["wilcoxon_p"] > 0.95, sep_rev["wilcoxon_p"]


def test_go_decision_requires_both_margin_and_significance():
    assert score.go_decision({"delta_mrr": 0.25, "wilcoxon_p": 0.01}) is True
    assert score.go_decision({"delta_mrr": 0.25, "wilcoxon_p": 0.20}) is False  # not sig
    assert score.go_decision({"delta_mrr": 0.10, "wilcoxon_p": 0.01}) is False  # margin


def test_separation_by_position_subsets_by_label():
    flip = [([1.0, 0.0, 0.0], 0), ([1.0, 0.0, 0.0], 0),
            ([1.0, 0.0, 0.0], 0), ([1.0, 0.0, 0.0], 0)]
    # at 0.25 div also nails it (no separation); at 0.75 div misses (target last)
    div = [([1.0, 0.0, 0.0], 0), ([1.0, 0.0, 0.0], 0),
           ([0.1, 0.2, 0.3], 0), ([0.1, 0.2, 0.3], 0)]
    positions = [0.25, 0.25, 0.75, 0.75]
    by_pos = score.separation_by_position(flip, div, positions)
    _approx(by_pos[0.25]["delta_mrr"], 0.0)
    _approx(by_pos[0.75]["delta_mrr"], 1.0 - 1.0 / 3.0)
    assert by_pos[0.25]["n"] == 2 and by_pos[0.75]["n"] == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\n{len(fns)} passed")
