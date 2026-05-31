"""Step-attribution scoring metrics for the synthetic counterfactual spike.

Pure python. Each instance scores every candidate step with a signal; the
labeled decisive step is one index. Metrics ask: does the signal rank the
decisive step near the top? Higher signal = better = nearer rank 1.

Tie convention (load-bearing — the prereg flags heavy discrete-rank ties):
ranks use the AVERAGE-RANK rule, so a decisive step tied with k-1 others at the
top gets rank (1+...+k)/k rather than an index-order-dependent 1 or k. This
keeps MRR/top-1/EXAM fair and tie-corrected by construction.
"""


def rank_of(scores, target):
    """1-based average rank (descending) of index `target` among `scores`.

    Higher score = nearer rank 1. Tied scores share the mean of the ranks they
    span, so the result is independent of input order among ties.
    """
    # ascending order; tied scores share mean ascending rank, then flip to descending
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    n = len(scores)
    asc = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based mean ascending rank
        for k in range(i, j + 1):
            asc[order[k]] = avg
        i = j + 1
    # descending rank = n + 1 - ascending rank
    return n + 1.0 - asc[target]


def reciprocal_rank(scores, target):
    """1 / rank_of(scores, target)."""
    return 1.0 / rank_of(scores, target)


def mrr(instances):
    """Mean reciprocal rank over instances, each a (scores, target_idx) pair."""
    if not instances:
        return 0.0
    return sum(reciprocal_rank(s, t) for s, t in instances) / len(instances)


def expected_top1(scores, target):
    """P(target ranked #1) under uniform random tie-breaking.

    1.0 if target is the unique max; 1/m if tied for max with m total; else 0.0.
    """
    mx = max(scores)
    if scores[target] != mx:
        return 0.0
    return 1.0 / sum(1 for s in scores if s == mx)


def exam(scores, target):
    """Fraction of the OTHER candidates that rank above target = (rank-1)/(n-1).

    The proportion of steps examined before reaching the decisive step. Lower is
    better. 0.0 when there is a single candidate.
    """
    n = len(scores)
    if n <= 1:
        return 0.0
    return (rank_of(scores, target) - 1.0) / (n - 1)


def top1_accuracy(instances):
    """Mean expected_top1 over (scores, target_idx) instances."""
    if not instances:
        return 0.0
    return sum(expected_top1(s, t) for s, t in instances) / len(instances)


def mean_exam(instances):
    """Mean exam over (scores, target_idx) instances."""
    if not instances:
        return 0.0
    return sum(exam(s, t) for s, t in instances) / len(instances)


def _wilcoxon_greater(rr_flip, rr_div):
    """One-sided, tie-corrected Wilcoxon signed-rank p for H1: rr_flip > rr_div.

    Paired over the same instances. scipy drops zero differences (zero_method
    'wilcox') and, when |difference| ties occur — which discrete reciprocal ranks
    produce constantly — falls back to the normal approximation with tie
    correction in the variance. All-zero differences (no signal either way) ->
    p = 1.0 (no evidence flip beats div).
    """
    from scipy.stats import wilcoxon
    if all(abs(a - b) < 1e-12 for a, b in zip(rr_flip, rr_div)):
        return 1.0
    try:
        res = wilcoxon(rr_flip, rr_div, alternative="greater",
                       zero_method="wilcox", correction=True)
        return float(res.pvalue)
    except ValueError:
        return 1.0


def separation(flip_instances, div_instances):
    """Confound-separation summary: outcome-flip vs cascade-divergence null.

    Both arguments are parallel lists of (scores, target_idx) over the SAME
    frozen eval set with the SAME decisive target per instance. Returns the
    prereg §5 quantities: Δ_MRR, both MRRs, both top-1s, the one-sided
    tie-corrected Wilcoxon p, and n.
    """
    mrr_f, mrr_d = mrr(flip_instances), mrr(div_instances)
    rr_f = [reciprocal_rank(s, t) for s, t in flip_instances]
    rr_d = [reciprocal_rank(s, t) for s, t in div_instances]
    return {
        "n": len(flip_instances),
        "mrr_flip": mrr_f,
        "mrr_div": mrr_d,
        "delta_mrr": mrr_f - mrr_d,
        "top1_flip": top1_accuracy(flip_instances),
        "top1_div": top1_accuracy(div_instances),
        "wilcoxon_p": _wilcoxon_greater(rr_f, rr_d),
    }


def go_decision(sep, dmrr_margin=0.20, alpha=0.05):
    """GO iff Δ_MRR >= margin AND the Wilcoxon p < alpha (prereg §5 gate)."""
    return sep["delta_mrr"] >= dmrr_margin and sep["wilcoxon_p"] < alpha


def separation_by_position(flip_instances, div_instances, positions):
    """`separation` computed within each injected-fault position label.

    `positions` is parallel to the instance lists. Returns {position: separation}.
    Mandatory per prereg §5 so the cascade confound's position-luck is legible.
    """
    out = {}
    for pos in sorted(set(positions)):
        f = [fi for fi, p in zip(flip_instances, positions) if p == pos]
        d = [di for di, p in zip(div_instances, positions) if p == pos]
        out[pos] = separation(f, d)
    return out
