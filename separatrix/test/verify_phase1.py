#!/usr/bin/env python3
"""Phase-1 gate verifier.

Checks that an emitted behavioral graph + a runtime trace satisfy the Phase-1
verification gate:
  G1 structural    - graph has functions, CFG edges, call edges, branch conds
  G2 source map    - most nodes carry a real source (file,line) from DebugLoc
  G3 trace->nodes  - every trace ID is a valid node ID
  G4 symbolization - sampled hit nodes map to real, non-empty source lines

Usage: verify_phase1.py <graph.json> <trace.txt> <source_dir>
"""
import json, os, sys

def main(graph_path, trace_path, src_dir):
    g = json.load(open(graph_path))
    nodes = g["nodes"]
    by_id = {n["id"]: n for n in nodes}
    edges = g["edges"]
    trace = [int(x) for x in open(trace_path).read().split()]

    results = []
    def check(name, ok, detail=""):
        results.append((name, ok, detail))

    # G1 structural
    cfg = sum(1 for e in edges if e["kind"] == "cfg")
    call = sum(1 for e in edges if e["kind"] == "call")
    conds = sum(1 for n in nodes if n["branch_cond"])
    funcs = {n["function"] for n in nodes}
    check("G1 structural",
          len(nodes) > 0 and cfg > 0 and call > 0 and conds > 0 and len(funcs) > 1,
          f"{len(nodes)} nodes, {len(funcs)} funcs, cfg={cfg} call={call} conds={conds}")

    # G2 source mapping coverage
    withsrc = [n for n in nodes if n["file"] and n["line"] > 0]
    frac = len(withsrc) / len(nodes) if nodes else 0
    check("G2 source-map coverage", frac >= 0.90,
          f"{len(withsrc)}/{len(nodes)} = {frac:.0%} nodes source-mapped")

    # G3 trace IDs all valid nodes
    bad = [i for i in trace if i not in by_id]
    hit = sorted(set(trace))
    check("G3 trace->nodes", len(bad) == 0,
          f"{len(trace)} events, {len(hit)} distinct nodes, {len(bad)} invalid IDs")

    # G4 symbolization: sampled hit nodes map to real source lines
    sampled, good = 0, 0
    shown = []
    for nid in hit:
        n = by_id[nid]
        if not (n["file"] and n["line"] > 0):
            continue
        path = os.path.join(src_dir, os.path.basename(n["file"]))
        if not os.path.exists(path):
            continue
        lines = open(path, errors="replace").read().splitlines()
        if n["line"] <= len(lines):
            sampled += 1
            text = lines[n["line"] - 1].strip()
            if text:
                good += 1
            if len(shown) < 5 and n["branch_cond"]:
                shown.append(f"    node {nid} {n['function']} @ "
                             f"{os.path.basename(n['file'])}:{n['line']}  |  {text[:70]}")
    check("G4 symbolization", sampled > 0 and good / sampled >= 0.95,
          f"{good}/{sampled} sampled hit nodes -> non-empty source lines")

    print(f"== Phase-1 gate: {os.path.basename(graph_path)} ==")
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:24} {detail}")
    if shown:
        print("  sample symbolized branch nodes (trace-hit):")
        print("\n".join(shown))
    allok = all(ok for _, ok, _ in results)
    print(f"  -> {'GATE PASS' if allok else 'GATE FAIL'}")
    return 0 if allok else 1

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(2)
    sys.exit(main(*sys.argv[1:]))
