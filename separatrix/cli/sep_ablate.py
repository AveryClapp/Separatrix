#!/usr/bin/env python3
"""separatrix ablate — Phase-3 structural-targeting ablation.

Tests the core thesis: do static structural priors (graph branchiness /
comparison predicates) let us find behavioral divergence faster than random
perturbation, at equal budget? Three arms per seed, equal budget B:

  random   - B uniform-random single-byte perturbations (naive baseline)
  struct   - probe (one perturbation per input position) -> rank positions by
             the STATIC prior of the node each probe bifurcated at -> spend the
             remaining budget on the highest-prior positions
  shuffled - identical algorithm, but node priors are shuffled (control: removes
             the structural signal while keeping probe+concentrate)

struct > random  => guidance helps.   struct > shuffled => the *structure* (not
just concentration) is what helps. Divergence uses the O(n) jaccard metric.

  sep_ablate.py --bin B --graph G [--budget 120] [--seeds "a,b,c"] [-o out.json]
"""
import argparse, json, os, random, sys, tempfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SEPROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SEPROOT, "detector"))
sys.path.insert(0, os.path.join(SEPROOT, "engine"))
import metric              # noqa: E402
import perturb             # noqa: E402
import priors as priors_m  # noqa: E402
from sep_run import run_trace  # noqa: E402

DEFAULT_SEEDS = ["3+4*2", "sqrt(3+4*2)/(1-5)", "cos(0)+sin(3.14)/2",
                 "2^3^2-1", "(1+2)*(3+4)/5", "abs(-7)+ln(10)"]


def evaluate(binary, base_c, base_trace, buf, tpath):
    """Return (divergence D, bifurcation node id or None)."""
    trace = run_trace(binary, buf, tpath)
    d = round(metric.jaccard(base_trace, trace) * 1000)
    if d == 0:
        return 0, None
    tok = metric.bifurcation_tok(base_c, metric.compress(trace, bucket=True))
    return d, (metric.first_id(tok) if tok is not None else None)


def score(inputs, binary, base_c, base_trace, tpath):
    """Total divergence + distinct sensitive regions over a set of inputs."""
    seen, total, regions = set(), 0, set()
    probe_map = {}   # input -> (D, bif_node)
    for buf in inputs:
        if buf in seen:
            continue
        seen.add(buf)
        d, nid = evaluate(binary, base_c, base_trace, buf, tpath)
        probe_map[buf] = (d, nid)
        total += d
        if d > 0 and nid is not None:
            regions.add(nid)
    return total, regions, probe_map


def run_seed(binary, graph, pri, seed_str, budget, tpath, rng):
    seed = seed_str.encode("latin-1")
    base_trace = run_trace(binary, seed, tpath)
    base_c = metric.compress(base_trace, bucket=True)
    L = len(seed)

    # --- random arm ---
    rand_inputs = [b for _, b in perturb.sample_random(seed, budget, rng)]
    r_total, r_regions, _ = score(rand_inputs, binary, base_c, base_trace, tpath)
    r_reg = len(r_regions)

    # --- shared probe: exactly one perturbation per position ---
    pos_bif = {}   # position -> (D, prior of bifurcation node)
    p_total, p_reg = 0, set()
    for i, buf in perturb.probe_once(seed):
        d, nid = evaluate(binary, base_c, base_trace, buf, tpath)
        p_total += d
        if d > 0 and nid is not None:
            p_reg.add(nid)
        pos_bif[i] = (d, pri.get(nid, 0.0) if nid is not None else 0.0)
    probe_cost = len(pos_bif)
    exploit_budget = max(0, budget - probe_cost)

    def exploit(rank_key):
        order = sorted(range(L), key=rank_key, reverse=True)
        inputs = [b for _, b in perturb.generate_at(seed, order, exploit_budget)]
        t, regions, _ = score(inputs, binary, base_c, base_trace, tpath)
        return t, regions

    # struct: rank positions by the TRUE static prior of their bifurcation node
    s_exp_total, s_exp_reg = exploit(lambda i: pos_bif.get(i, (0, 0))[1])
    struct_total = p_total + s_exp_total
    struct_reg = len(p_reg | s_exp_reg)

    # shuffled control: same algorithm, priors permuted. Averaged over several
    # permutations so the structural-edge estimate is not a single-shuffle fluke.
    keys = list(pos_bif)
    base_priors = [pos_bif[i][1] for i in keys]
    shuf_totals, shuf_regs = [], []
    for _ in range(3):
        perm = base_priors[:]
        rng.shuffle(perm)
        sp = {keys[j]: perm[j] for j in range(len(keys))}
        t, reg = exploit(lambda i: sp.get(i, 0.0))
        shuf_totals.append(p_total + t)
        shuf_regs.append(len(p_reg | reg))
    shuf_total = round(sum(shuf_totals) / len(shuf_totals))
    shuf_reg = round(sum(shuf_regs) / len(shuf_regs))

    return {
        "seed": seed_str, "budget": budget, "probe_cost": probe_cost,
        "random": {"divergence": r_total, "regions": r_reg},
        "struct": {"divergence": struct_total, "regions": struct_reg},
        "shuffled": {"divergence": shuf_total, "regions": shuf_reg},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--seeds", default=None)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    pri = priors_m.node_priors(graph)
    seeds = args.seeds.split(",") if args.seeds else DEFAULT_SEEDS
    tdir = tempfile.mkdtemp(prefix="sep_ablate_")
    tpath = os.path.join(tdir, "t")

    rows = []
    for s in seeds:
        rng = random.Random(0xC0FFEE ^ zlib.crc32(s.encode("latin-1")))  # deterministic per seed
        rows.append(run_seed(args.bin, graph, pri, s, args.budget, tpath, rng))

    # aggregate
    def ratios(key):
        rs, rh = [], []
        for r in rows:
            base = r["random"][key] or 1
            rs.append(r["struct"][key] / base)
            rh.append(r["shuffled"][key] / (r["random"][key] or 1))
        return rs, rh
    div_sr = [r["struct"]["divergence"] / (r["random"]["divergence"] or 1) for r in rows]
    div_ss = [r["struct"]["divergence"] / (r["shuffled"]["divergence"] or 1) for r in rows]
    wins_vs_random = sum(1 for r in rows if r["struct"]["divergence"] > r["random"]["divergence"])
    wins_vs_shuf = sum(1 for r in rows if r["struct"]["divergence"] > r["shuffled"]["divergence"])
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0

    summary = {
        "seeds": len(rows), "budget": args.budget,
        "mean_divergence_ratio_struct_over_random": round(mean(div_sr), 3),
        "mean_divergence_ratio_struct_over_shuffled": round(mean(div_ss), 3),
        "struct_wins_vs_random": f"{wins_vs_random}/{len(rows)}",
        "struct_wins_vs_shuffled": f"{wins_vs_shuf}/{len(rows)}",
        "rows": rows,
    }
    out_path = args.out or (os.path.splitext(args.graph)[0] + ".ablation.json")
    json.dump(summary, open(out_path, "w"), indent=2)

    print(f"ablation: {len(rows)} seeds, budget {args.budget}/arm")
    print(f"{'seed':<22}{'random':>10}{'struct':>10}{'shuffled':>10}  (divergence discovered)")
    for r in rows:
        print(f"{r['seed'][:22]:<22}{r['random']['divergence']:>10}"
              f"{r['struct']['divergence']:>10}{r['shuffled']['divergence']:>10}")
    print(f"\nmean divergence ratio  struct/random   = {mean(div_sr):.2f}x  "
          f"(struct wins {wins_vs_random}/{len(rows)})")
    print(f"mean divergence ratio  struct/shuffled = {mean(div_ss):.2f}x  "
          f"(struct wins {wins_vs_shuf}/{len(rows)})  [isolates structural signal]")
    print(f"map: {out_path}")


if __name__ == "__main__":
    main()
