#!/usr/bin/env python3
"""Phase-4 gate verifier — predictive validity on a Magma library.

ROADMAP MVP bar: on one Magma library, trajectory sensitivity beats *random*
AND *coverage frequency* as a bug-location predictor. Headline granularity is
region-level (the roadmap scores "bug-containing regions").

  G1 trajectory-sensitivity > random     (region AUC)
  G2 trajectory-sensitivity > coverage   (region AUC)
  G3 trajectory-sensitivity > best SBFL  (region AUC; max of ochiai/tarantula/dstar)

G3 is the spectrum-based fault-localization comparison (the baseline this eval was
missing). It is only meaningful when a valid fail-oracle produced failing runs;
on lua neither standard oracle is valid (debug-subsystem bug → differential F=0;
trigger non-reproducible via ASLR), so SBFL is N/A and G3 is reported N/A — it
does NOT auto-pass. G3 activates on the first multi-library target whose bug
manifests in observable output.

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
    val_loc = P["value_localized"]["auc"]   # value through the SAME localization (fair vs divergence)
    val_fb = P["value_firstbif"]["auc"]     # old first-bifurcation value attribution

    # Paired-difference bootstrap CIs (Bonferroni-widened to alpha/m): divergence
    # is scored over the SAME node universe as each baseline, so this paired test
    # is the rigorous AUC-difference comparison. "excludes 0" carries the
    # multiple-comparison correction directly (no separate p-value).
    pd = e.get("paired_diffs", {})

    def pd_line(other_key, label):
        # other_key=None -> the per-level best-SBFL key (which can differ between
        # region and node), read from the block so neither line is dropped.
        for lvl in ("region", "node"):
            block = pd.get(lvl, {})
            key = other_key or block.get("best_sbfl")
            triple = block.get(f"divergence_minus_{key}") if key else None
            if not triple:
                continue
            lab = label or f"best SBFL {key}"
            obs, lo, hi = triple
            sig = "excludes 0" if lo > 0 else "includes 0"
            print(f"  [INFO] div - {lab} ({lvl}): {obs:+.3f} CI[{lo:.3f},{hi:.3f}] "
                  f"(alpha={block['alpha']:.4f}, m={block['family_size']}) ({sig})")

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
    pd_line("coverage", "coverage")

    # G3: divergence vs the best SBFL formula. Only meaningful when SBFL is
    # available (a valid oracle produced failing runs); otherwise N/A — never an
    # auto-pass on a degenerate/absent baseline.
    sbfl = e.get("sbfl", {"available": False, "reason": "no sbfl block in eval"})
    g3 = None
    if sbfl.get("available"):
        sbfl_aucs = {name: P[name]["auc"] for name in sbfl["predictors"]}
        best = max(sbfl_aucs, key=sbfl_aucs.get)
        g3 = traj_sens > sbfl_aucs[best]
        for name in sbfl["predictors"]:
            ci = P[name].get("auc_ci")
            ci_s = f" CI[{ci[0]:.3f},{ci[1]:.3f}]" if ci else ""
            print(f"  [INFO] {name:<14} region AUC={sbfl_aucs[name]}{ci_s}")
        print(f"  [{'PASS' if g3 else 'FAIL'}] G3 sensitivity>SBFL      "
              f"region AUC divergence={traj_sens} vs best SBFL {best}={sbfl_aucs[best]}")
        pd_line(None, None)
    else:
        print(f"  [N/A ] G3 sensitivity>SBFL      {sbfl.get('reason', '')}")

    print(f"  [INFO] first-bifurcation attribution AUC={first_bif} "
          f"-> {'adequate' if first_bif > cov else 'INADEQUATE on staged target (localises to lexer)'}")
    print(f"  [INFO] value-localized baseline AUC={val_loc} "
          f"-> {'trajectory divergence > value (same localization)' if traj_sens > val_loc else 'value >= trajectory (reshapes framing)'}")
    pd_line("value_localized", "value_localized")
    print(f"  [INFO] value-firstbif baseline AUC={val_fb} (old attribution, for the record)")

    # Headline gate = G1 & G2 (& G3 when SBFL is available). A N/A G3 neither
    # passes nor fails the gate.
    ok = g1 and g2 and pos > 0 and (g3 is not False)
    print(f"  -> {'GATE PASS' if ok else 'GATE FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1]))
