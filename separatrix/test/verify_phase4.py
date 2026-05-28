#!/usr/bin/env python3
"""Phase-4 gate verifier — predictive validity on a Magma library.

ROADMAP MVP bar: on one Magma library, trajectory sensitivity beats *random*
AND *coverage frequency* as a bug-location predictor. Headline granularity is
region-level (the roadmap scores "bug-containing regions").

  G1 trajectory-sensitivity > random     (region AUC)
  G2 trajectory-sensitivity > coverage   (region AUC)

Phase-4 attribution finding (surfaced, not buried — per the roadmap): the
committed map's FIRST-BIFURCATION attribution is inadequate on staged targets.
Every input-level perturbation of an interpreter first diverges in the lexer, so
first-bifurcation credits only the front-end and fails to localise downstream
bugs (AUC ~= 0.5). The trajectory-sensitivity signal that satisfies the gate is
DIVERGENCE-LOCALISATION: credit every node where the trajectory diverges under
perturbation, not just the first. Both are reported here.

Also reported (per the forward-citation review): the value-space output-distance
baseline. Value distance has no per-node structure to localise with, so it cannot
beat trajectory divergence on this task — the trajectory-vs-value result.

Usage: verify_phase4.py <eval.json>
"""
import json, sys


def main(path):
    e = json.load(open(path))
    reg = e["results"]["region"]
    pos = reg["positives"]
    P = reg["predictors"]
    traj_sens = P["divergence"]["auc"]      # corrected trajectory-sensitivity map
    first_bif = P["trajectory"]["auc"]      # committed first-bifurcation attribution
    rnd = P["random"]["auc"]
    cov = P["coverage"]["auc"]
    val = P["value"]["auc"]

    reached = sum(1 for r in e["reachability"] if r["reached"])
    print(f"== Phase-4 gate: {path.split('/')[-1]} ==")
    print(f"  campaign: {e['campaign']['perturbations']} perturbations, "
          f"{e['campaign']['universe_nodes']} executed nodes; "
          f"{reached}/{e['bugs']} bug regions reached, {pos} positive nodes")

    g1 = traj_sens > rnd
    g2 = traj_sens > cov
    print(f"  [{'PASS' if g1 else 'FAIL'}] G1 sensitivity>random    "
          f"region AUC divergence={traj_sens} vs random={rnd}")
    print(f"  [{'PASS' if g2 else 'FAIL'}] G2 sensitivity>coverage  "
          f"region AUC divergence={traj_sens} vs coverage={cov}")
    print(f"  [INFO] first-bifurcation attribution AUC={first_bif} "
          f"-> {'adequate' if first_bif > cov else 'INADEQUATE on staged target (localises to lexer)'}")
    print(f"  [INFO] value-space baseline AUC={val} "
          f"-> {'trajectory divergence > value distance' if traj_sens > val else 'value >= trajectory (reshapes framing)'}")

    ok = g1 and g2 and pos > 0
    print(f"  -> {'GATE PASS' if ok else 'GATE FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1]))
