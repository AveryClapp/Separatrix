"""Map Magma canary sites onto behavioral-graph nodes (Phase-4 ground truth).

A Magma bug is a `#ifdef`-gated revert of a historical fix carrying a
`MAGMA_LOG("%MAGMA_BUG%", ...)` canary at the bug's exact source line. Given the
canary sites (bug_id, file, line) and the graph, produce labels at two
granularities:

  node-level   - graph nodes whose source line is within `window` of the canary
                 (a tight band; DebugLoc granularity is coarse so an exact-line
                 hit is not guaranteed).
  region-level - every node in the function enclosing the canary; the roadmap
                 scores whether predictors rank "bug-containing regions" high.

File matching is by basename: the graph stores 'repo/ldebug.c', the patch hunk
says 'ldebug.c'.
"""
import os


def _base(p):
    return os.path.basename(p or "")


def map_sites(graph, sites, window=3):
    """Resolve each canary site to its function, nearest node, line-band, and
    enclosing-function node set. Sites in files with no graph nodes are skipped."""
    nodes = graph["nodes"]
    by_file = {}
    for n in nodes:
        by_file.setdefault(_base(n["file"]), []).append(n)

    mapped = []
    for s in sites:
        cands = by_file.get(_base(s["file"]), [])
        if not cands:
            continue
        # nearest node by line distance; ties -> smaller line then smaller id.
        nearest = min(cands, key=lambda n: (abs(n["line"] - s["line"]), n["line"], n["id"]))
        fn = nearest["function"]
        band = {n["id"] for n in cands if abs(n["line"] - s["line"]) <= window}
        region = {n["id"] for n in nodes if n["function"] == fn}
        mapped.append({
            "bug_id": s["bug_id"], "file": s["file"], "line": s["line"],
            "function": fn, "node": nearest["id"],
            "node_band": band, "region_nodes": region,
        })
    return mapped


def labels_over(universe, mapped, level="region"):
    """0/1 label per node in `universe` (in order). level in {'node','region'}."""
    key = "node_band" if level == "node" else "region_nodes"
    positives = set()
    for m in mapped:
        positives |= m[key]
    return [1 if u in positives else 0 for u in universe]
