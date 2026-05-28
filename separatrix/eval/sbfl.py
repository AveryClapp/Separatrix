"""Spectrum-based fault localization (SBFL) — Ochiai, Tarantula, DStar.

The classic coverage-spectrum fault-location baselines this evaluation was
missing. Each scores a node from its execution spectrum over a labeled run set:

  ef - #failing runs that executed the node
  ep - #passing runs that executed the node
  F  - total failing runs   (so nf = F - ef = failing runs that did NOT execute it)
  P  - total passing runs

All three are **higher = more suspicious**, so they slot directly into the
existing higher-is-better ranking metrics (roc_auc / precision_at_k). They ride
the same shared campaign as `divergence` (same executed-node universe, same union
ground truth) for an apples-to-apples comparison.
"""
import math

# DStar's denominator (ep + nf) is 0 for a node executed by ALL failing and NO
# passing runs — the maximally-suspicious case (e.g. a canary co-located with the
# bug). Returning inf there breaks the rank-sum AUC and sorts unpredictably, so
# we substitute a fixed tiny EPS: such nodes get a finite ef^2/EPS that ranks
# strictly above any finite-denominator node and ties among themselves by ef^2.
EPS = 1e-9
STAR = 2


def ochiai(ef, ep, F, P):
    """ef / sqrt(F * (ef + ep)); 0 when F == 0 or ef == 0."""
    if F == 0 or ef == 0:
        return 0.0
    return ef / math.sqrt(F * (ef + ep))


def tarantula(ef, ep, F, P):
    """(ef/F) / (ef/F + ep/P); 0 when F == 0. With no passing runs (P == 0) the
    passing-rate term is 0, so a node hit by failing runs scores 1.0."""
    if F == 0:
        return 0.0
    ef_rate = ef / F
    ep_rate = ep / P if P else 0.0
    denom = ef_rate + ep_rate
    return ef_rate / denom if denom else 0.0


def dstar(ef, ep, F, P):
    """DStar (star=2): ef^2 / (ep + nf), nf = F - ef. Zero denominator -> finite
    sentinel ef^2/EPS (see EPS) instead of inf."""
    nf = F - ef
    denom = ep + nf
    return (ef * ef) / (denom if denom else EPS)


_FORMULAS = {"ochiai": ochiai, "tarantula": tarantula, "dstar": dstar}


def score_all(ef_map, ep_map, F, P, universe, formula):
    """{node: suspiciousness} over `universe` for the named formula. A node never
    executed in a failing run (ef == 0) scores 0 for all three by construction."""
    try:
        fn = _FORMULAS[formula]
    except KeyError:
        raise ValueError(f"unknown SBFL formula: {formula!r}")
    return {n: fn(ef_map.get(n, 0), ep_map.get(n, 0), F, P) for n in universe}
