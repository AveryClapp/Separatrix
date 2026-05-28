#!/usr/bin/env python3
"""Phase-3 gate verifier — structural-targeting ablation.

  A1 guided>random   - structural guidance beats random at equal budget on
                       every seed, with a meaningful mean uplift and a
                       significant paired sign test (p < 0.05)
  A2 structural edge  - INFORMATIONAL: does the static prior add value beyond
                       probe-informed concentration (struct vs shuffled-prior)?

The ROADMAP gate is A1. A2 is reported honestly: if struct ~= shuffled, the
active mechanism is divergence-aware concentration, and the static prior is a
secondary refinement (flag for richer-target evaluation in Phase 4).

Usage: verify_phase3.py <ablation.json>
"""
import json, sys


def main(path):
    a = json.load(open(path))
    rows = a["rows"]
    n = len(rows)
    wins_r = sum(1 for r in rows if r["struct"]["divergence"] > r["random"]["divergence"])
    mean_sr = a["mean_divergence_ratio_struct_over_random"]
    p = 0.5 ** wins_r if wins_r == n else 1.0  # one-sided sign test (all-win case)

    a1 = wins_r == n and mean_sr >= 1.2 and p < 0.05
    print(f"== Phase-3 gate: {path.split('/')[-1]} ==")
    print(f"  [{'PASS' if a1 else 'FAIL'}] A1 guided>random   "
          f"struct/random={mean_sr}x, wins {wins_r}/{n}, sign-test p={p:.4f}")

    wins_s = sum(1 for r in rows if r["struct"]["divergence"] > r["shuffled"]["divergence"])
    mean_ss = a["mean_divergence_ratio_struct_over_shuffled"]
    verdict = ("structural prior adds signal" if mean_ss >= 1.15 and wins_s > n // 2
               else "marginal: concentration is the active mechanism, prior is secondary")
    print(f"  [INFO] A2 structural edge  struct/shuffled={mean_ss}x, wins {wins_s}/{n} "
          f"-> {verdict}")

    print(f"  -> {'GATE PASS' if a1 else 'GATE FAIL'}")
    return 0 if a1 else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1]))
