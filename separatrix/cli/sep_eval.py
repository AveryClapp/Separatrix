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
import sbfl                      # noqa: E402

PRINTABLE = bytes(range(0x20, 0x7F))   # broad alphabet for text targets
PCTS = (1, 5, 10, 20)
N_RANDOM = 25                          # random-ranking draws to average over
N_BOOT = 2000                          # bootstrap resamples for the AUC CI
N_PERM = 2000                          # label permutations for the AUC null p
SBFL_NA_REASON = (                     # why SBFL is N/A on lua (both oracles invalid)
    "SBFL N/A: no valid fail-oracle on this target. Differential is degenerate "
    "(F=0 — LUA004 is a debug-subsystem bug that never reaches the harness's "
    "observable output); trigger is non-reproducible (the canary does "
    "ASLR-sensitive cross-Proto pointer arithmetic; F jitters ~107-122/251). "
    "The divergence-vs-SBFL gate (G3) activates on the first multi-library "
    "target whose bug manifests in observable output (differential oracle)."
)


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


def run_digest(binary, data, inpath):
    """Run a (possibly uninstrumented) binary on `data`; return its stdout digest
    only. The differential oracle's fixed reference emits no trace, so run() —
    which reads $SEP_TRACE — can't be used for it."""
    with open(inpath, "wb") as f:
        f.write(data)
    p = subprocess.run([binary, inpath], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.stdout.decode("latin-1", "replace")


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


def campaign(binary, seed, max_pert, tmpdir, corpus_dir=None, fail_oracle="none",
             fixed_bin=None):
    """Run the shared campaign; collect per-perturbation observations, coverage
    counts, the executed-node universe, and (when an oracle is selected) the SBFL
    pass/fail spectrum.

    fail_oracle decides each run's SBFL label:
      "none" (default) — no fail signal; SBFL is not computed. Correct when no
        valid oracle exists for the target (e.g. lua: see below).
      "differential" — fails iff the buggy stdout digest differs from the fixed
        reference (`fixed_bin`, built with MAGMA_ENABLE_FIXES). Reproducible
        (trace+digest are deterministic). DEGENERATE on lua (F=0): LUA004 is a
        debug-subsystem bug that never reaches the harness's observable output.
      "trigger" — fails iff the canary reported >=1 trigger. NON-reproducible on
        lua (the canary does ASLR-sensitive cross-Proto pointer arithmetic; F
        jitters 107-122/251). A documented cross-check only.
    So lua runs with "none"; the differential/trigger machinery is retained for
    the first multi-library target whose bug manifests in observable output."""
    if fail_oracle not in ("none", "differential", "trigger"):
        raise ValueError(f"unsupported fail-oracle {fail_oracle!r}")
    if fail_oracle == "differential" and not fixed_bin:
        raise ValueError("differential oracle needs fixed_bin (build.sh BUILD_FIXED=1)")
    sbfl_on = fail_oracle != "none"
    inpath = os.path.join(tmpdir, "in")
    tpath = os.path.join(tmpdir, "t")
    gpath = os.path.join(tmpdir, "g")    # canary trigger file (trigger oracle only)
    fpath = os.path.join(tmpdir, "fin")  # scratch input for the fixed reference run
    gp = gpath if fail_oracle == "trigger" else None

    def fail_label(buf, out, trig):
        """SBFL fail label for one run under the active oracle."""
        if fail_oracle == "trigger":
            return bool(trig)
        return run_digest(fixed_bin, buf, fpath) != out

    base_trace, base_out, base_trig = run(binary, seed, inpath, tpath, gpath=gp)
    base_c = metric.compress(base_trace, bucket=True)
    base_edges = metric.edge_multiset(base_trace)

    visits = collections.Counter(base_trace)
    edge_div = collections.Counter()   # per-node control-flow divergence mass
    val_div = collections.Counter()    # per-node value-distance mass (localized attribution)
    # SBFL spectrum: ef/ep = #failing/#passing runs that executed each node.
    ef = collections.Counter()
    ep = collections.Counter()
    F = 0
    P = 0

    def account(trace, buf, out, trig):
        """Fold one run (any run — baseline, diverging, or not) into the SBFL
        spectrum, keyed by the oracle's pass/fail label. No-op when SBFL is off."""
        nonlocal F, P
        if not sbfl_on:
            return
        nodes_run = set(trace)
        if fail_label(buf, out, trig):
            F += 1
            for nd in nodes_run:
                ef[nd] += 1
        else:
            P += 1
            for nd in nodes_run:
                ep[nd] += 1

    account(base_trace, seed, base_out, base_trig)
    obs = []
    if corpus_dir:
        perts = load_corpus(corpus_dir)
    else:
        perts = perturb.generate(seed, max_pert, alphabet=PRINTABLE)
    diverged = 0
    for _, buf in perts:
        trace, out, trig = run(binary, buf, inpath, tpath, gpath=gp)
        visits.update(trace)
        account(trace, buf, out, trig)   # SBFL counts every run, before the divergence filter
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
        pert_edges = metric.edge_multiset(trace)
        for src, mass in metric.localized_divergence(base_edges, pert_edges).items():
            edge_div[src] += mass
        # value-localization: credit the value-distance v through the SAME node
        # set, so value-vs-divergence isolates signal, not attribution method.
        for src, val in metric.localized_value(base_edges, pert_edges, v).items():
            val_div[src] += val

    universe = sorted(visits)
    return {"obs": obs, "visits": dict(visits), "edge_div": dict(edge_div),
            "val_div": dict(val_div),
            "ef": dict(ef), "ep": dict(ep), "F": F, "P": P,
            "fail_oracle": fail_oracle, "sbfl_on": sbfl_on,
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
    ap.add_argument("--fail-oracle", choices=["none", "differential", "trigger"], default="none",
                    help="SBFL pass/fail signal. 'none' (default): no oracle, SBFL "
                         "reported N/A (correct for lua — neither standard oracle is "
                         "valid). 'differential': buggy digest != fixed reference "
                         "(--fixed-bin); reproducible but DEGENERATE on lua (F=0). "
                         "'trigger': canary fired — NON-reproducible on lua (ASLR). "
                         "Use differential on a multi-library target whose bug "
                         "manifests in observable output.")
    ap.add_argument("--fixed-bin", default=None,
                    help="fixed reference binary (build.sh BUILD_FIXED=1) for the "
                         "differential oracle.")
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
    if args.fail_oracle == "differential" and not args.fixed_bin:
        ap.error("--fail-oracle differential needs --fixed-bin")
    camp = campaign(args.bin, seed, args.max_pert, tmpdir, corpus_dir=args.corpus,
                    fail_oracle=args.fail_oracle, fixed_bin=args.fixed_bin)
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
        "value_localized": pr.coverage(camp["val_div"], universe), # value through the SAME localization (fair vs divergence)
        "value_firstbif": pr.value(camp["obs"], universe),         # old first-bifurcation value attribution (kept for the record)
        "coverage": pr.coverage(camp["visits"], universe),
    }
    # SBFL baselines: only when an oracle produced failing runs. On lua neither
    # standard oracle is valid (see SBFL_NA_REASON), so they are reported N/A and
    # left out of the ranking — not silently scored 0.5 on a degenerate spectrum.
    sbfl_available = camp["sbfl_on"] and camp["F"] > 0
    if sbfl_available:
        for f in ("ochiai", "tarantula", "dstar"):
            scores[f"sbfl_{f}"] = sbfl.score_all(camp["ef"], camp["ep"], camp["F"], camp["P"], universe, f)
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

    # Paired-difference bootstrap CIs for the headline comparisons. The
    # predictors are scored over the SAME node universe (correlated), so a paired
    # resample of node indices is the right test for an AUC difference, not
    # marginal-CI overlap. Each CI is Bonferroni-widened to alpha/m, where m is the
    # per-granularity headline family size (Decision #4): divergence vs
    # {coverage, value_localized, best-SBFL} (m=3 with SBFL, m=2 when N/A). A
    # difference is significant iff its alpha/m CI excludes 0.
    paired_diffs = {}
    for lvl in ("node", "region"):
        lab = labels[lvl]
        others = ["coverage", "value_localized"]
        best_sbfl = None
        if sbfl_available:
            sbfl_aucs = {f: results[lvl]["predictors"][f]["auc"]
                         for f in ("sbfl_ochiai", "sbfl_tarantula", "sbfl_dstar")}
            best_sbfl = max(sbfl_aucs, key=sbfl_aucs.get)
            others.append(best_sbfl)
        m = len(others)
        alpha = 0.05 / m
        div_vec = [scores["divergence"][n] for n in universe]
        block = {"family_size": m, "alpha": alpha, "best_sbfl": best_sbfl}
        for other in others:
            ovec = [scores[other][n] for n in universe]
            block[f"divergence_minus_{other}"] = list(
                em.paired_bootstrap_auc_diff(div_vec, ovec, lab, n_boot=N_BOOT, seed=0, alpha=alpha))
        paired_diffs[lvl] = block

    case_study = {name: top_region(sc, universe, gnodes) for name, sc in scores.items()}

    out = {
        "binary": os.path.basename(args.bin),
        "campaign": {"perturbations": camp["perts"], "diverged": camp["diverged"],
                     "universe_nodes": len(universe), "baseline_trace_len": camp["base_len"],
                     "fail_oracle": camp["fail_oracle"], "F": camp["F"], "P": camp["P"]},
        "bugs": len(bugs), "reachability": reach,
        "sbfl": {"available": sbfl_available,
                 "predictors": ["sbfl_ochiai", "sbfl_tarantula", "sbfl_dstar"] if sbfl_available else [],
                 "reason": None if sbfl_available else SBFL_NA_REASON},
        "results": results,
        "paired_diffs": paired_diffs,
        "case_study_top_region": case_study,
        "note_baselines_deferred": "Mull (mutation score) baseline not run: separate "
                                   "toolchain, not installed; framework leaves a predictor slot.",
    }
    out_path = args.out or (os.path.splitext(args.graph)[0] + ".eval.json")
    json.dump(out, open(out_path, "w"), indent=2)

    # console report
    print(f"campaign: {camp['perts']} perturbations, {camp['diverged']} diverged, "
          f"{len(universe)} executed nodes, baseline trace {camp['base_len']}")
    if sbfl_available:
        print(f"fail-oracle ({camp['fail_oracle']}): F={camp['F']} failing / P={camp['P']} passing runs")
    else:
        print(f"SBFL: N/A ({SBFL_NA_REASON.split('.')[0]}.)")
    print("bug-region reachability:")
    for r in reach:
        print(f"  {r['bug_id']:<8} {r['function']:<18} "
              f"{'REACHED' if r['reached'] else 'unreached':<10} "
              f"({r['executed_nodes_in_region']} region nodes executed)")
    for lvl in ("region", "node"):
        res = results[lvl]
        print(f"\n== {lvl}-level ranking ({res['positives']} positive nodes) ==")
        print(f"  {'predictor':<16}{'AUC':>8}{'95%CI':>16}{'perm_p':>9}{'AP':>8}"
              f"{'p@1':>7}{'p@5':>7}{'p@10':>7}{'p@20':>7}")
        order = ["trajectory", "divergence", "value_localized", "value_firstbif", "coverage"]
        if sbfl_available:
            order += ["sbfl_ochiai", "sbfl_tarantula", "sbfl_dstar"]
        order.append("random")
        for name in order:
            m = res["predictors"][name]
            pa = m["precision_at"]
            ci = m.get("auc_ci")
            ci_s = f"[{ci[0]:.3f},{ci[1]:.3f}]" if ci else "--"
            p_s = f"{m['auc_p']:.4f}" if m.get("auc_p") is not None else "--"
            print(f"  {name:<16}{m['auc']:>8}{ci_s:>16}{p_s:>9}{m['ap']:>8}"
                  f"{pa['p1']:>7}{pa['p5']:>7}{pa['p10']:>7}{pa['p20']:>7}")
    print(f"\nmap: {out_path}")


if __name__ == "__main__":
    main()
