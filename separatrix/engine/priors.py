"""Static structural priors over behavioral-graph nodes.

A node is a likely separatrix location — where a small perturbation can flip the
trajectory — to the extent that it is a data-dependent decision point. Computed
purely from the graph (before any execution), so it can *guide* where to spend
perturbation budget rather than reacting after the fact.

prior(node) =
    (out_degree - 1)                      # branchiness: straight-line -> 0
  * (2 if data-dependent conditional)     # a real branch condition, not fallthrough
  + (1 if predicate is a comparison)      # icmp/fcmp = an equality/range boundary

Switches (many successors) and comparison branches score highest; basic blocks
that just fall through score 0.
"""


def node_priors(graph):
    pri = {}
    for n in graph["nodes"]:
        succ = len(n["succ"])
        cond = bool(n["branch_cond"])
        p = max(0, succ - 1) * (2.0 if cond else 1.0)
        bc = n["branch_cond"]
        if "icmp" in bc or "fcmp" in bc:
            p += 1.0
        pri[n["id"]] = p
    return pri
