#!/usr/bin/env python3
"""separatrix run — Phase-2 sensitivity-map campaign.

Runs a structurally-unguided perturbation campaign against an instrumented
target, scores each behavioral-graph node by trajectory divergence, and emits a
ranked sensitivity map.

  sep_run.py --bin <inst_binary> --graph <graph.json> --seed "<input>" \
             [-o map.json] [--max-pert N]

The instrumented binary must take the input as argv[1] and honor $SEP_TRACE
(produced by `separatrix analyze` + the sep runtime).
"""
import argparse, json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SEPROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SEPROOT, "detector"))
sys.path.insert(0, os.path.join(SEPROOT, "engine"))
import metric          # noqa: E402
import perturb         # noqa: E402


def run_trace(binary, data: bytes, trace_path):
    env = dict(os.environ, SEP_TRACE=trace_path)
    subprocess.run([binary, data.decode("latin-1")], env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(trace_path) as f:
        return [int(x) for x in f.read().split()]


def pct(vals, q):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--max-pert", type=int, default=4000)
    args = ap.parse_args()

    g = json.load(open(args.graph))
    node = {n["id"]: n for n in g["nodes"]}
    seed = args.seed.encode("latin-1")

    tdir = tempfile.mkdtemp(prefix="sep_run_")
    tpath = os.path.join(tdir, "t")

    base = run_trace(args.bin, seed, tpath)
    cbase = metric.compress(base, bucket=True)

    perts = perturb.generate(seed, args.max_pert)

    per_node = {}          # node_id -> list of D
    exact_v, banded_v = [], []
    t_start = time.time()
    diverged = 0
    for label, buf in perts:
        trace = run_trace(args.bin, buf, tpath)
        cp = metric.compress(trace, bucket=True)
        d = metric.lev(cbase, cp)
        if d == 0:
            continue
        diverged += 1
        tok = metric.bifurcation_tok(cbase, cp)
        nid = metric.first_id(tok) if tok is not None else None
        if nid is not None and nid in node:
            per_node.setdefault(nid, []).append(d)
        exact_v.append(d)
        banded_v.append(metric.lev_banded(cbase, cp))
    elapsed = time.time() - t_start

    ranking = []
    for nid, ds in per_node.items():
        n = node[nid]
        ranking.append({
            "node": nid, "function": n["function"], "file": n["file"],
            "line": n["line"], "branch_cond": n["branch_cond"],
            "count": len(ds), "sum_d": sum(ds),
            "mean_d": round(sum(ds) / len(ds), 3),
            "p90_d": round(pct(ds, 0.9), 3), "max_d": max(ds),
        })
    ranking.sort(key=lambda r: (-r["sum_d"], -r["count"], r["node"]))

    rho = metric.spearman(exact_v, banded_v)
    max_err = max((abs(a - b) for a, b in zip(exact_v, banded_v)), default=0)
    out = {
        "binary": os.path.basename(args.bin), "seed": args.seed,
        "metric": "trajectory-divergence/compressed-bucketed-levenshtein",
        "perturbations": len(perts), "diverged": diverged,
        "baseline_trace_len": len(base),
        "validation": {"banded_spearman": round(rho, 4), "banded_max_err": max_err},
        "ranking": ranking,
    }
    out_path = args.out or (os.path.splitext(args.graph)[0] + ".sepmap.json")
    json.dump(out, open(out_path, "w"), indent=2)

    runs = len(perts) + 1
    print(f"campaign: {len(perts)} perturbations, {diverged} diverged, "
          f"{len(ranking)} sensitive nodes")
    print(f"cost: {runs} runs in {elapsed:.2f}s = {runs/elapsed:.0f} runs/s; "
          f"baseline trace {len(base)} events")
    print(f"validation: banded vs exact Spearman rho={rho:.4f}, max|err|={max_err}")
    print(f"map: {out_path}")
    print("top sensitive regions (by total divergence originating there):")
    for r in ranking[:10]:
        loc = f"{os.path.basename(r['file'])}:{r['line']}" if r["file"] else "?"
        cond = (r["branch_cond"][:48] + "...") if len(r["branch_cond"]) > 48 else r["branch_cond"]
        print(f"  node {r['node']:<5} sum_d={r['sum_d']:<5} n={r['count']:<3} "
              f"{r['function'][:24]:<24} {loc:<20} {cond}")


if __name__ == "__main__":
    main()
