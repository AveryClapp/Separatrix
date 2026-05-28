"""Phase-4 bug-location predictors, scored over a shared node universe.

Every predictor returns {node_id: score} for *every* node in `universe`, so the
four rankings are directly comparable (same candidates, same attribution). Higher
score = predicted more bug-prone.

  trajectory  - Separatrix's signal: total trajectory divergence attributed to
                the node (the bifurcation point of each diverging perturbation).
  value       - the program-derivatives baseline: total value-space output
                distance attributed to the same bifurcation node. Isolates
                trajectory-vs-value (the Feldt-Dobslaw objection).
  coverage    - the llvm-cov analogue: how often the node executes.
  random      - the ablation floor: a reproducible random score per node.

Observations are dicts {node, d, v}: bifurcation node (or None if unattributed),
trajectory divergence d, value-space distance v.
"""


def _sum_attributed(observations, key, universe):
    score = {n: 0 for n in universe}
    for o in observations:
        nid = o["node"]
        if nid is not None and nid in score:
            score[nid] += o[key]
    return score


def trajectory(observations, universe):
    return _sum_attributed(observations, "d", universe)


def value(observations, universe):
    return _sum_attributed(observations, "v", universe)


def coverage(visit_counts, universe):
    return {n: visit_counts.get(n, 0) for n in universe}


def random_scores(universe, rng):
    return {n: rng.random() for n in universe}
