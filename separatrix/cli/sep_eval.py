#!/usr/bin/env python3
"""separatrix eval — Phase-4 predictive-validity evaluation.

Runs ONE perturbation campaign against an instrumented target and scores every
executed node with four predictors, then asks which predictor ranks the
ground-truth bug regions highest (ROC-AUC, precision@k, average precision):

  trajectory  - Separatrix: total trajectory divergence attributed to the node
  value       - program-derivatives baseline: total output-value distance
  coverage    - llvm-cov analogue: node execution frequency
  random      - ablation floor: mean over several random rankings (~0.5)

All four share the same campaign, attribution, and node universe (the executed
nodes), so the comparison is apples-to-apples.

  sep_eval.py --bin B --graph G --bugs bugs.json --seed-file seed.lua \
              [--max-pert N] [--window L] [-o out.json]

The instrumented binary reads its input from the file named by argv[1] (file
mode) and honors $SEP_TRACE; it prints a deterministic value-space digest to
stdout.
"""
import argparse, collections, json, os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SEPROOT = os.path.dirname(HERE)
for sub in ("detector", "engine", "eval"):
    sys.path.insert(0, os.path.join(SEPROOT, sub))
import metric          # noqa: E402
import perturb         # noqa: E402
import eval_metrics as em       # noqa: E402
import predictors as pr         # noqa: E402
import ground_truth as gt       # noqa: E402

PRINTABLE = bytes(range(0x20, 0x7F))   # broad alphabet for text targets
PCTS = (1, 5, 10, 20)
N_RANDOM = 25                          # random-ranking draws to average over
N_BOOT = 2000                          # bootstrap resamples for the AUC CI
N_PERM = 2000                          # label permutations for the AUC null p


def run(binary, data, inpath, tpath, gpath=None):
    """File-mode run: returns (trace node-id list, stdout digest, triggers set).

    `triggers` is the set of 'file:line' strings the canary reported via
    $MAGMA_TRIGGERS (empty when gpath is None). run() owns the trigger file's
    reset-before / read-after lifecycle so the Task-2 probe and the campaign
    cannot drift on how the fail signal is collected."""
    with open(inpath, "wb") as f:
        f.write(data)
    env = dict(os.environ, SEP_TRACE=tpath)
    if gpath:
        env["MAGMA_TRIGGERS"] = gpath
        open(gpath, "w").close()                         # reset before run
    p = subprocess.run([binary, inpath], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    with open(tpath) as f:
        trace = [int(x) for x in f.read().split()]
    trig = set()
    if gpath and os.path.exists(gpath):
        with open(gpath) as f:
            trig = {ln.strip() for ln in f if ln.strip()}
    return trace, p.stdout.decode("latin-1", "replace"), trig


def load_corpus(corpus_dir):
    """Read a directory of input files as the perturbation set (one valid input
    per file). Used instead of byte-mutation when inputs are structured (e.g. a
    programming language), where naive byte flips just break parsing."""
    perts = []
    for name in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, name)
        if os.path.isfile(path):
            perts.append((name, open(path, "rb").read()))
    return perts


def campaign(binary, seed, max_pert, tmpdir, corpus_dir=None):
    """Run the shared campaign; collect per-perturbation observations, coverage
    counts, and the executed-node universe."""
    inpath = os.path.join(tmpdir, "in")
    tpath = os.path.join(tmpdir, "t")

    base_trace, base_out, _ = run(binary, seed, inpath, tpath)
    base_c = metric.compress(base_trace, bucket=True)
    base_edges = metric.edge_multiset(base_trace)

    visits = collections.Counter(base_trace)
    edge_div = collections.Counter()   # per-node control-flow divergence mass
    obs = []
    if corpus_dir:
        perts = load_corpus(corpus_dir)
    else:
        perts = perturb.generate(seed, max_pert, alphabet=PRINTABLE)
    diverged = 0
    for _, buf in perts:
        trace, out, _ = run(binary, buf, inpath, tpath)
        visits.update(trace)
        d = round(metric.jaccard(base_trace, trace) * 1000)
        v = em.value_distance(base_out, out)
        if d == 0 and v == 0.0:
            continue
        diverged += 1
        # first-bifurcation attribution (the committed map's signal)
        tok = metric.bifurcation_tok(base_c, metric.compress(trace, bucket=True))
        nid = metric.first_id(tok) if tok is not None else None
        obs.append({"node": nid, "d": d, "v": v})
        # divergence-localization: credit EVERY node whose outgoing-edge profile
        # differs from baseline (where the trajectory actually diverges, not just
        # where it first diverges). Shared helper so the eval and the shipped tool
        # (sep_run.py) cannot drift on the signal that defines the contribution.
        for src, mass in metric.localized_divergence(base_edges, metric.edge_multiset(trace)).items():
            edge_div[src] += mass

    universe = sorted(visits)
    return {"obs": obs, "visits": dict(visits), "edge_div": dict(edge_div),
            "universe": universe, "perts": len(perts), "diverged": diverged,
            "base_len": len(base_trace), "base_out": base_out}


def evaluate_predictor(scores, universe, labels, with_stats=True):
    vec = [scores[n] for n in universe]
    out = {
        "auc": round(em.roc_auc(vec, labels), 4),
        "ap": round(em.average_precision(vec, labels), 4),
        "precision_at": {f"p{k}": round(em.precision_at_k(vec, labels, k), 4) for k in PCTS},
    }
    # Bootstrap CI + permutation p quantify whether the AUC is real given the
    # small positive count (a few bug regions). Skipped for the 25 random draws
    # (with_stats=False) — they are the null, and it would be 25x the cost.
    if with_stats:
        out["auc_ci"] = list(em.bootstrap_auc_ci(vec, labels, n_boot=N_BOOT, seed=0))
        out["auc_p"] = em.permutation_test_auc(vec, labels, n_perm=N_PERM, seed=0)
    return out


def top_region(scores, universe, graph_nodes):
    nid = max(universe, key=lambda n: scores[n])
    n = graph_nodes[nid]
    return {"node": nid, "function": n["function"],
            "file": os.path.basename(n["file"] or ""), "line": n["line"],
            "score": round(scores[nid], 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--bugs", required=True)
    ap.add_argument("--seed-file", default=None)
    ap.add_argument("--seed", default=None)
    ap.add_argument("--max-pert", type=int, default=2000)
    ap.add_argument("--corpus", default=None,
                    help="directory of valid input files used as the perturbation "
                         "set (instead of byte-mutating the seed); for structured "
                         "inputs like a programming language.")
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    gnodes = {n["id"]: n for n in graph["nodes"]}
    bugs = json.load(open(args.bugs))
    if args.seed_file:
        seed = open(args.seed_file, "rb").read()
    elif args.seed:
        seed = args.seed.encode("latin-1")
    else:
        ap.error("need --seed-file or --seed")

    tmpdir = tempfile.mkdtemp(prefix="sep_eval_")
    camp = campaign(args.bin, seed, args.max_pert, tmpdir, corpus_dir=args.corpus)
    universe = camp["universe"]

    # ground-truth labels at both granularities, plus reachability report
    mapped = gt.map_sites(graph, bugs, window=args.window)
    labels = {lvl: gt.labels_over(universe, mapped, level=lvl) for lvl in ("node", "region")}
    reach = []
    for m in mapped:
        reg_exec = sum(1 for n in universe if n in m["region_nodes"])
        reach.append({"bug_id": m["bug_id"], "function": m["function"],
                      "node": m["node"], "executed_nodes_in_region": reg_exec,
                      "reached": reg_exec > 0})

    # predictor scores over the shared universe
    scores = {
        "trajectory": pr.trajectory(camp["obs"], universe),       # first-bifurcation
        "divergence": pr.coverage(camp["edge_div"], universe),     # divergence-localization
        "value": pr.value(camp["obs"], universe),
        "coverage": pr.coverage(camp["visits"], universe),
    }
    # random: average AUC/AP/p@k over N_RANDOM independent rankings
    rnd_runs = [pr.random_scores(universe, random.Random(s)) for s in range(N_RANDOM)]

    results = {}
    for lvl in ("node", "region"):
        lab = labels[lvl]
        per_pred = {}
        for name, sc in scores.items():
            per_pred[name] = evaluate_predictor(sc, universe, lab)
        # random aggregated (it is the null by construction; no CI/p reported)
        rnd_evals = [evaluate_predictor(r, universe, lab, with_stats=False) for r in rnd_runs]
        per_pred["random"] = {
            "auc": round(sum(e["auc"] for e in rnd_evals) / N_RANDOM, 4),
            "ap": round(sum(e["ap"] for e in rnd_evals) / N_RANDOM, 4),
            "precision_at": {f"p{k}": round(sum(e["precision_at"][f"p{k}"] for e in rnd_evals) / N_RANDOM, 4) for k in PCTS},
            "auc_ci": None, "auc_p": None,
        }
        results[lvl] = {"positives": sum(lab), "predictors": per_pred}

    case_study = {name: top_region(sc, universe, gnodes) for name, sc in scores.items()}

    out = {
        "binary": os.path.basename(args.bin),
        "campaign": {"perturbations": camp["perts"], "diverged": camp["diverged"],
                     "universe_nodes": len(universe), "baseline_trace_len": camp["base_len"]},
        "bugs": len(bugs), "reachability": reach,
        "results": results,
        "case_study_top_region": case_study,
        "note_baselines_deferred": "Mull (mutation score) baseline not run: separate "
                                   "toolchain, not installed; framework leaves a predictor slot.",
    }
    out_path = args.out or (os.path.splitext(args.graph)[0] + ".eval.json")
    json.dump(out, open(out_path, "w"), indent=2)

    # console report
    print(f"campaign: {camp['perts']} perturbations, {camp['diverged']} diverged, "
          f"{len(universe)} executed nodes, baseline trace {camp['base_len']}")
    print("bug-region reachability:")
    for r in reach:
        print(f"  {r['bug_id']:<8} {r['function']:<18} "
              f"{'REACHED' if r['reached'] else 'unreached':<10} "
              f"({r['executed_nodes_in_region']} region nodes executed)")
    for lvl in ("region", "node"):
        res = results[lvl]
        print(f"\n== {lvl}-level ranking ({res['positives']} positive nodes) ==")
        print(f"  {'predictor':<12}{'AUC':>8}{'95%CI':>16}{'perm_p':>9}{'AP':>8}"
              f"{'p@1':>7}{'p@5':>7}{'p@10':>7}{'p@20':>7}")
        for name in ("trajectory", "divergence", "value", "coverage", "random"):
            m = res["predictors"][name]
            pa = m["precision_at"]
            ci = m.get("auc_ci")
            ci_s = f"[{ci[0]:.3f},{ci[1]:.3f}]" if ci else "--"
            p_s = f"{m['auc_p']:.4f}" if m.get("auc_p") is not None else "--"
            print(f"  {name:<12}{m['auc']:>8}{ci_s:>16}{p_s:>9}{m['ap']:>8}"
                  f"{pa['p1']:>7}{pa['p5']:>7}{pa['p10']:>7}{pa['p20']:>7}")
    print(f"\nmap: {out_path}")


if __name__ == "__main__":
    main()
