"""Phase-4 ranking-quality metrics: ROC-AUC, precision@k, average precision.

Pure python (no numpy/sklearn) so the evaluation harness has no new deps. Each
takes parallel `scores` (predictor value per node) and `labels` (1 = node is in a
ground-truth bug region, 0 = not) and asks: does a higher score rank bug regions
higher? Higher is better for all three.
"""
import random


def value_distance(a, b):
    """Normalized Levenshtein distance in [0,1] between two output digests.
    The value-space predictor's per-perturbation signal: how far the program's
    observable output moved, independent of control-flow trajectory."""
    la, lb = len(a), len(b)
    if la == 0 and lb == 0:
        return 0.0
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb] / max(la, lb)


def roc_auc(scores, labels):
    """Rank-based AUC (Mann-Whitney U). Ties contribute 0.5.

    AUC = P(score(random positive) > score(random negative)). Returns 0.5 when
    there are no positive/negative pairs to compare (degenerate / undefined)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return 0.5
    concordant = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                concordant += 1.0
            elif p == n:
                concordant += 0.5
    return concordant / (len(pos) * len(neg))


def _avg_ranks(scores):
    """1-based average ranks (ascending); tied scores share their mean rank.
    Lets AUC be computed by rank-sum in O(n log n) instead of O(pos*neg)."""
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i, n = 0, len(scores)
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _auc_from_ranks(ranks, labels):
    """Mann-Whitney AUC from precomputed average ranks (ties = 0.5),
    identical to roc_auc. 0.5 when a class is empty."""
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    r_pos = sum(r for r, y in zip(ranks, labels) if y)
    return (r_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def bootstrap_auc_ci(scores, labels, n_boot=2000, seed=0, alpha=0.05):
    """Percentile bootstrap CI for the ROC-AUC, stratified within class.

    Resamples positives and negatives separately (with replacement, preserving
    each class size) so no resample is degenerate — the standard bootstrap for
    AUC when positives are few (the small-N case this evaluation lives in).
    Returns the (alpha/2, 1-alpha/2) percentiles as (lo, hi). Seeded for
    reproducibility. Degenerate input (a class is empty) -> (0.5, 0.5)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return (0.5, 0.5)
    rng = random.Random(seed)
    y = [1] * len(pos) + [0] * len(neg)
    aucs = []
    for _ in range(n_boot):
        s = [rng.choice(pos) for _ in pos] + [rng.choice(neg) for _ in neg]
        aucs.append(_auc_from_ranks(_avg_ranks(s), y))
    aucs.sort()
    lo = aucs[max(0, int((alpha / 2.0) * n_boot))]
    hi = aucs[min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot))]
    return (round(lo, 4), round(hi, 4))


def paired_bootstrap_auc_diff(scores_a, scores_b, labels, n_boot=2000, seed=0, alpha=0.05):
    """Paired percentile-bootstrap CI for AUC(a) - AUC(b) over the SAME nodes.

    Predictors are scored on the same node universe, so they are correlated; the
    rigorous test resamples the shared NODE INDICES (stratified within class so no
    resample is degenerate), recomputes BOTH AUCs on that identical resample, and
    takes the difference. Returns (observed_diff, lo, hi) where observed_diff is
    the full-data AUC(a)-AUC(b). Degenerate (a class empty) -> (0.0, 0.0, 0.0)."""
    pos = [i for i, y in enumerate(labels) if y]
    neg = [i for i, y in enumerate(labels) if not y]
    obs = roc_auc(scores_a, labels) - roc_auc(scores_b, labels)
    if not pos or not neg:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    y = [1] * len(pos) + [0] * len(neg)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.choice(pos) for _ in pos] + [rng.choice(neg) for _ in neg]
        sa = [scores_a[i] for i in idx]
        sb = [scores_b[i] for i in idx]
        diffs.append(_auc_from_ranks(_avg_ranks(sa), y) - _auc_from_ranks(_avg_ranks(sb), y))
    diffs.sort()
    lo = diffs[max(0, int((alpha / 2.0) * n_boot))]
    hi = diffs[min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot))]
    return (round(obs, 4), round(lo, 4), round(hi, 4))


def permutation_test_auc(scores, labels, n_perm=2000, seed=0):
    """One-sided permutation p-value for H0: score is unrelated to label.

    Scores are fixed, so item ranks are computed once; each permutation just
    reassigns which positions are positive and recomputes AUC by rank-sum.
    p = (1 + #{permuted AUC >= observed}) / (n_perm + 1) — the add-one keeps p
    strictly positive (never claims p=0) and is the unbiased small-sample form.
    Seeded for reproducibility."""
    ranks = _avg_ranks(scores)
    obs = _auc_from_ranks(ranks, labels)
    lab = list(labels)
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(lab)
        if _auc_from_ranks(ranks, lab) >= obs - 1e-12:
            ge += 1
    return round((1 + ge) / (n_perm + 1), 4)


def _order(scores):
    """Indices sorted by descending score, ties broken by original index."""
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


def precision_at_k(scores, labels, k):
    """Fraction of the top-k highest-scoring items that are positive.
    k is capped at the number of items."""
    k = min(k, len(scores))
    if k == 0:
        return 0.0
    order = _order(scores)
    hits = sum(labels[i] for i in order[:k])
    return hits / k


def average_precision(scores, labels):
    """Mean of precision@(rank) over the positions of the positives.
    0.0 if there are no positives."""
    order = _order(scores)
    total_pos = sum(labels)
    if total_pos == 0:
        return 0.0
    hits = 0
    ap = 0.0
    for rank, i in enumerate(order, start=1):
        if labels[i]:
            hits += 1
            ap += hits / rank
    return ap / total_pos
