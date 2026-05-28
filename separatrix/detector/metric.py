"""Trajectory-divergence metric (committed spec, validated in Phase 0).

A trace is the ordered sequence of behavioral-graph node IDs emitted by the
instrumented target. Behavioral distance between two traces is the edit distance
over a cycle-compressed, log-bucketed token sequence:

  1. cycle-compress immediate repetitions (period <= MAX_PERIOD) so multi-block
     loops collapse to one token;
  2. log-bucket the repeat count (AFL-style) so benign loop-count jitter does
     not register as divergence;
  3. Levenshtein over the resulting tokens (exact); banded variant for scale.

The first differing token's leading node ID is the *bifurcation point* — the
graph node where the trajectories first diverge — used for attribution.
"""

MAX_PERIOD = 6
BAND = 8


def classify(k):
    """AFL-style log bucket index for a repeat count."""
    if k <= 3:
        return k
    b, lim = 4, 7
    while k > lim:
        b += 1
        lim = lim * 2 + 1
    return b


def compress(seq, bucket=True, max_period=MAX_PERIOD):
    """Cycle-compress immediate repetitions into ('R', block, count) tokens;
    singletons become ('S', id). bucket=False keeps the raw repeat count."""
    out, i, n = [], 0, len(seq)
    while i < n:
        best = None  # (covered, period, reps, block)
        for p in range(1, max_period + 1):
            if i + 2 * p > n:
                break
            block = tuple(seq[i:i + p])
            k = 1
            while i + (k + 1) * p <= n and tuple(seq[i + k*p:i + (k+1)*p]) == block:
                k += 1
            if k >= 2 and (best is None or k * p > best[0]):
                best = (k * p, p, k, block)
        if best:
            _, p, k, block = best
            out.append(("R", block, classify(k) if bucket else k))
            i += k * p
        else:
            out.append(("S", seq[i]))
            i += 1
    return out


def first_id(tok):
    return tok[1][0] if tok[0] == "R" else tok[1]


def lev(a, b):
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def lev_banded(a, b, band=BAND):
    """Banded Levenshtein — production-candidate approximation. O((la)*band)."""
    la, lb = len(a), len(b)
    INF = float("inf")
    prev = [INF] * (lb + 1)
    for j in range(0, min(band, lb) + 1):
        prev[j] = j
    for i in range(1, la + 1):
        cur = [INF] * (lb + 1)
        lo, hi = max(1, i - band), min(lb, i + band)
        if i <= band:
            cur[0] = i
        for j in range(lo, hi + 1):
            c = 0 if a[i - 1] == b[j - 1] else 1
            opts = []
            if prev[j] < INF:
                opts.append(prev[j] + 1)
            if cur[j - 1] < INF:
                opts.append(cur[j - 1] + 1)
            if prev[j - 1] < INF:
                opts.append(prev[j - 1] + c)
            if opts:
                cur[j] = min(opts)
        prev = cur
    return prev[lb] if prev[lb] < INF else abs(la - lb) + band


def edge_multiset(seq):
    """Bucketed edge multiset: consecutive node pairs -> log-bucketed count.
    O(n), alignment-free — the scale fallback for long traces where banded
    Levenshtein loses fidelity (large divergence exceeds any fixed band)."""
    counts = {}
    for i in range(len(seq) - 1):
        e = (seq[i], seq[i + 1])
        counts[e] = counts.get(e, 0) + 1
    return {e: classify(c) for e, c in counts.items()}


def jaccard(t0, t1):
    """Weighted Jaccard distance over bucketed edge multisets, in [0,1].
    Different scale from Levenshtein but rank-correlates with it; O(n)."""
    m0, m1 = edge_multiset(t0), edge_multiset(t1)
    keys = set(m0) | set(m1)
    inter = sum(min(m0.get(k, 0), m1.get(k, 0)) for k in keys)
    union = sum(max(m0.get(k, 0), m1.get(k, 0)) for k in keys)
    return 0.0 if union == 0 else 1.0 - inter / union


def localized_divergence(base_edges, pert_edges):
    """Per-node trajectory divergence for one perturbation (divergence
    localization). Given two bucketed edge multisets, credit each edge's SOURCE
    node with the absolute bucketed-count delta of every edge that differs.

    Unlike first-bifurcation attribution (which credits only the single node
    where trajectories first diverge), this credits EVERY node whose outgoing-
    edge profile moved — the per-node form of the trajectory-divergence metric.
    On staged targets (lex->parse->compile->exec) first-bifurcation only ever
    credits the front-end; localization reaches downstream regions (Phase 4)."""
    out = {}
    for e in set(base_edges) | set(pert_edges):
        delta = abs(base_edges.get(e, 0) - pert_edges.get(e, 0))
        if delta:
            out[e[0]] = out.get(e[0], 0) + delta
    return out


def localized_value(base_edges, pert_edges, v):
    """Per-node value-distance attribution for one perturbation. Credits the
    scalar output-value distance `v` to every node where the trajectory diverges
    (the SAME node set as localized_divergence), so a value predictor can be
    attributed through the identical localization mechanism as the divergence
    predictor — isolating trajectory-vs-value signal from attribution method."""
    out = {}
    for e in set(base_edges) | set(pert_edges):
        if base_edges.get(e, 0) != pert_edges.get(e, 0):
            out[e[0]] = v
    return out


def bifurcation_tok(a, b):
    """First differing token between two compressed sequences (None if equal)."""
    m = min(len(a), len(b))
    for i in range(m):
        if a[i] != b[i]:
            return a[i]
    if len(a) != len(b):
        return a[m] if len(a) > m else b[m]
    return None


def distance(t0, t1, bucket=True):
    """Exact behavioral distance between two raw traces + bifurcation node."""
    c0, c1 = compress(t0, bucket), compress(t1, bucket)
    tok = bifurcation_tok(c0, c1)
    return lev(c0, c1), (first_id(tok) if tok is not None else None)


def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    if len(x) < 2:
        return 1.0
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx > 0 and vy > 0 else 1.0
