#!/usr/bin/env python3
"""Phase-2 gate verifier — checks a sensitivity map.

  P1 non-empty      - campaign found diverging perturbations and sensitive nodes
  P2 attributable   - every ranked node is a real, source-mapped graph node
  P3 banded~exact   - banded vs exact divergence Spearman rho >= 0.90

Usage: verify_phase2.py <map.json> <graph.json>
"""
import json, os, sys


def main(map_path, graph_path):
    m = json.load(open(map_path))
    g = json.load(open(graph_path))
    node = {n["id"]: n for n in g["nodes"]}
    rank = m["ranking"]

    res = []
    res.append(("P1 non-empty", m["diverged"] > 0 and len(rank) > 0,
                f"{m['diverged']} diverged, {len(rank)} sensitive nodes"))

    bad = [r["node"] for r in rank if r["node"] not in node]
    unmapped = [r["node"] for r in rank if not (r["file"] and r["line"] > 0)]
    res.append(("P2 attributable", len(bad) == 0 and len(unmapped) == 0,
                f"{len(bad)} invalid, {len(unmapped)} unmapped of {len(rank)} ranked"))

    rho = m["validation"]["banded_spearman"]
    res.append(("P3 banded~exact", rho >= 0.90,
                f"Spearman rho={rho}, max|err|={m['validation']['banded_max_err']}"))

    print(f"== Phase-2 gate: {os.path.basename(map_path)} ==")
    for name, ok, detail in res:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:18} {detail}")
    allok = all(ok for _, ok, _ in res)
    print(f"  -> {'GATE PASS' if allok else 'GATE FAIL'}")
    return 0 if allok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(2)
    sys.exit(main(*sys.argv[1:]))
