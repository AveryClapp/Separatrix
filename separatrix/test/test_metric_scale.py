#!/usr/bin/env python3
"""Scale-metric validation: jaccard is a faithful O(n) rank-proxy for exact.

`sep_run.py` offers two trajectory-distance metrics:
  - exact   : Levenshtein over the cycle-compressed token sequence (metric.distance)
              — O(m^2) in the COMPRESSED length m; the reference signal.
  - jaccard : weighted Jaccard over the bucketed edge multiset (metric.jaccard)
              — O(n) in the raw trace length; the production scale metric.

`sep_run.py` documents jaccard as "validated rho>=0.98 vs exact on long traces",
but that validation was never in the committed test suite. This file supplies it:
it generates synthetic LONG (>=50k-event) traces with loop structure, computes
BOTH metrics over a perturbation population spanning a wide divergence range, and
verifies the Spearman rank-correlation between them.

WHY SYNTHETIC, AND WHY LOOP STRUCTURE. The "exact" metric is only tractable when
the trace COMPRESSES: a 50k-event loop-heavy trace collapses to a few hundred
tokens, so O(m^2) Levenshtein is cheap. Real traces that DON'T compress make exact
infeasible — e.g. the committed lua debug-trace baseline is 51,870 raw events but
only compresses to 36,398 tokens (its hook-driven path has few tight loops), so
exact Levenshtein there is ~1.3e9 ops/pair (hours in Python). That infeasibility
is exactly why the O(n) jaccard proxy exists; this test validates the proxy in the
compressible regime where exact can be computed as ground truth.

MEASURED RESULT (this generator, 6 deterministic trials): mean Spearman ~0.954,
min ~0.937 — a strong proxy, slightly below the favorable-end 0.98 figure quoted in
sep_run.py. The correlation is highest when divergences are substantial (the
long-trace regime the proxy targets) and degrades toward ties when perturbations
are sub-bucket-small. The asserted floors below sit under the measured values with
margin so the test is robust, not threshold-fitted.
"""
import os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "detector"))
import metric  # noqa: E402

N_TRIALS = 6        # independent deterministic baselines+populations
POP = 80            # perturbations per trial
RHO_MEAN_FLOOR = 0.93   # measured ~0.954; floor set below with margin (not fitted)
RHO_MIN_FLOOR = 0.88    # measured min ~0.937
LONG_FLOOR = 50_000  # "long trace" threshold (raw events)


def _build(blocks):
    """A trace is a sequence of blocks; each block is a loop (motif repeated `reps`
    times) followed by a unique join node — the structure cycle-compression targets."""
    out = []
    for motif, reps, join in blocks:
        out += motif * reps
        out.append(join)
    return out


def _baseline(rng, n_blocks=140, reps_base=200):
    blocks, nid = [], 0
    for _ in range(n_blocks):
        L = rng.randint(2, 4)
        motif = list(range(nid, nid + L)); nid += L
        join = nid; nid += 1
        blocks.append((motif, reps_base + rng.randint(-50, 50), join))
    return blocks, nid


def _mutate(blocks, next_id, rng, k):
    """k independent local mutations of mixed kinds, rebuilt into a full trace:
    loop-count change, branch flip (swap a motif node), block insert, block delete."""
    blks = [(list(m), r, j) for (m, r, j) in blocks]
    nid = next_id
    for _ in range(k):
        kind = rng.choice(["count", "flip", "insert", "delete"])
        i = rng.randrange(len(blks))
        m, r, j = blks[i]
        if kind == "count":
            blks[i] = (m, max(1, int(r * rng.choice([0.25, 0.5, 1.5, 2.0, 4.0]))), j)
        elif kind == "flip":
            m = list(m); m[rng.randrange(len(m))] = nid; nid += 1; blks[i] = (m, r, j)
        elif kind == "insert":
            blks.insert(i, ([nid, nid + 1], rng.randint(50, 250), nid + 2)); nid += 3
        elif kind == "delete" and len(blks) > 2:
            del blks[i]
    return _build(blks)


def _trial(seed):
    """One (baseline, exact_distances, jaccard_distances) trial. Variants span a
    graded severity range so the divergence magnitudes are well spread."""
    rng = random.Random(seed)
    blocks, nid = _baseline(rng)
    base = _build(blocks)
    severities = [1, 1, 1, 2, 2, 3, 4, 6, 9, 13, 18, 25, 34, 45]
    exact, jac = [], []
    for i in range(POP):
        r2 = random.Random(seed * 7919 + i + 1)
        k = severities[i % len(severities)] if i < len(severities) else r2.choice(severities)
        var = _mutate(blocks, nid, r2, k)
        exact.append(metric.distance(base, var)[0])   # compressed Levenshtein (reference)
        jac.append(metric.jaccard(base, var))          # O(n) edge-set proxy
    return base, exact, jac


def test_baseline_is_long_and_compressible():
    # The validated regime: a LONG trace that COMPRESSES (so exact is tractable).
    base, _, _ = _trial(0)
    assert len(base) >= LONG_FLOOR, f"baseline only {len(base)} events"
    comp = metric.compress(base)
    assert len(comp) < len(base) // 50, (
        f"baseline did not compress ({len(comp)} tokens from {len(base)} events); "
        "exact Levenshtein would be intractable")


def test_population_has_divergence_spread():
    # Spearman is only meaningful if the population spans a range (not all tied).
    _, exact, jac = _trial(0)
    assert max(exact) > min(exact), "exact distances are all tied"
    assert max(jac) > min(jac), "jaccard distances are all tied"
    assert len(set(exact)) >= 5, "too few distinct exact distances to rank"


def test_jaccard_rank_correlates_with_exact():
    # The headline claim: jaccard ranks divergence the same way exact does, on long
    # traces. Measured over N_TRIALS deterministic trials.
    rhos = []
    for s in range(N_TRIALS):
        _, exact, jac = _trial(s)
        rhos.append(metric.spearman(exact, jac))
    mean = sum(rhos) / len(rhos)
    print(f"\n  jaccard-vs-exact Spearman over {N_TRIALS} trials: "
          f"min={min(rhos):.4f} mean={mean:.4f} max={max(rhos):.4f}")
    assert mean >= RHO_MEAN_FLOOR, f"mean rho {mean:.4f} < {RHO_MEAN_FLOOR}"
    assert min(rhos) >= RHO_MIN_FLOOR, f"min rho {min(rhos):.4f} < {RHO_MIN_FLOOR}"


def test_trials_are_deterministic():
    # Two runs of the same trial seed produce identical metrics (reproducibility).
    _, ex1, jc1 = _trial(3)
    _, ex2, jc2 = _trial(3)
    assert ex1 == ex2 and jc1 == jc2


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR ] {fn.__name__}: {e}")
    print(f"metric_scale: {passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    sys.exit(_run())
