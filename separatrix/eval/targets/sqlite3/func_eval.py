#!/usr/bin/env python3
"""sqlite3 oracle-free eval with FUNCTION-LEVEL ground truth.

WHY THIS EXISTS (committed regeneration rule — see docs/, sqlite memory):
The default eval (`cli/sep_eval.py`) maps bug sites onto graph nodes by file
BASENAME + line band (`ground_truth.map_sites`). That is correct for lua, whose
graph keeps per-file DebugLoc. It SILENTLY FAILS on sqlite3: the build compiles
the *amalgamation* (`sqlite3.c`), which flattens every src/*.c and ext/*.c into
one file with brand-new line numbers. So a bug recorded as `src/select.c:5526`
finds no `select.c` node -> 0 mapped positives -> every predictor AUC = 0.50.
The previously-reported 0.61 came from a function-level computation that was
never committed; this script makes that rule reproducible.

THE RULE (deterministic, regenerates from the canonical target):
  1. Each bug site (file:line in the PATCHED original tree, $REPO from build.sh)
     is resolved to its enclosing C function via ctags: the function-definition
     whose start line is the greatest <= the bug line, within that file. (C
     functions don't nest, so this is exact.)
  2. The amalgamation flattens files but PRESERVES function names (built with
     -fno-discard-value-names). So positives = every EXECUTED graph node whose
     `function` equals any bug's enclosing function. This is the region-level
     granularity ("does the predictor rank the bug-containing function high").
  3. A bug whose enclosing function never appears in the executed universe is
     UNREACHED (the diffuse-coupling story) and contributes no positives.

Everything else — the perturbation campaign, the divergence/coverage/value
attribution, the node universe, the AUC/CI/permutation machinery — is imported
verbatim from cli/sep_eval.py so the signal cannot drift from the headline tool.

  func_eval.py --bin sqlite3_inst --graph G.sepgraph.json --bugs bugs.json \
               --repo <patched-src-tree> --corpus corpus/ --seed-file seed.sql -o out.json
"""
import argparse, json, os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SEPROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))   # .../separatrix (package dir)
sys.path.insert(0, os.path.join(SEPROOT, "cli"))
import sep_eval as se          # noqa: E402  (campaign, evaluate_predictor, N_RANDOM, PCTS)
sys.path.insert(0, os.path.join(SEPROOT, "eval"))
import predictors as pr        # noqa: E402


def enclosing_functions(repo, sites):
    """Resolve each bug site to its enclosing C function name via ctags.

    Returns {bug_id: function_name | None}. None when the file is absent from the
    tree (e.g. shell.c.in / a loadable ext not amalgamated) or no function
    precedes the line."""
    out = {}
    for s in sites:
        path = os.path.join(repo, s["file"])
        if not os.path.isfile(path):
            out[s["bug_id"]] = None
            continue
        # ctags: function tags with line numbers, one per definition in this file.
        p = subprocess.run(
            ["ctags", "-x", "--c-kinds=f", "--c++-kinds=f", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        best_name, best_line = None, -1
        for ln in p.stdout.splitlines():
            # `-x` format: <name> function <line> <file> <source-text>
            parts = ln.split(None, 4)
            if len(parts) < 4 or parts[1] != "function":
                continue
            try:
                start = int(parts[2])
            except ValueError:
                continue
            if start <= s["line"] and start > best_line:
                best_line, best_name = start, parts[0]
        out[s["bug_id"]] = best_name
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--bugs", required=True)
    ap.add_argument("--repo", required=True, help="patched original src tree (build.sh $WORK/repo)")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--seed-file", required=True)
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    gnodes = {n["id"]: n for n in graph["nodes"]}
    bugs = json.load(open(args.bugs))
    seed = open(args.seed_file, "rb").read()

    # --- function-level ground truth (the committed rule) ---
    encl = enclosing_functions(args.repo, bugs)
    # function name -> set of graph node ids (over the WHOLE graph, restricted to
    # universe below). Built once.
    fn_to_nodes = {}
    for n in graph["nodes"]:
        fn_to_nodes.setdefault(n["function"], set()).add(n["id"])

    # --- run the shared campaign (oracle-free; SBFL not applicable here) ---
    tmpdir = tempfile.mkdtemp(prefix="sqlite_func_eval_")
    camp = se.campaign(args.bin, seed, max_pert=0, tmpdir=tmpdir,
                       corpus_dir=args.corpus, fail_oracle="none")
    universe = camp["universe"]
    uset = set(universe)

    # bug -> enclosing function -> positives within the executed universe
    bug_rows = []
    positives = set()
    for s in bugs:
        fn = encl[s["bug_id"]]
        region = fn_to_nodes.get(fn, set()) if fn else set()
        exec_region = region & uset
        reached = len(exec_region) > 0
        if reached:
            positives |= exec_region
        bug_rows.append({"bug_id": s["bug_id"], "file": s["file"], "line": s["line"],
                         "function": fn, "region_nodes": len(region),
                         "executed_region_nodes": len(exec_region), "reached": reached})
    labels = [1 if u in positives else 0 for u in universe]

    # --- predictor scores over the shared universe (same as sep_eval) ---
    scores = {
        "trajectory": pr.trajectory(camp["obs"], universe),
        "divergence": pr.coverage(camp["edge_div"], universe),
        "value_localized": pr.coverage(camp["val_div"], universe),
        "value_firstbif": pr.value(camp["obs"], universe),
        "coverage": pr.coverage(camp["visits"], universe),
    }
    rnd_runs = [pr.random_scores(universe, random.Random(s)) for s in range(se.N_RANDOM)]

    per_pred = {name: se.evaluate_predictor(sc, universe, labels) for name, sc in scores.items()}
    rnd_evals = [se.evaluate_predictor(r, universe, labels, with_stats=False) for r in rnd_runs]
    per_pred["random"] = {
        "auc": round(sum(e["auc"] for e in rnd_evals) / se.N_RANDOM, 4),
        "ap": round(sum(e["ap"] for e in rnd_evals) / se.N_RANDOM, 4),
        "precision_at": {f"p{k}": round(sum(e["precision_at"][f"p{k}"] for e in rnd_evals) / se.N_RANDOM, 4) for k in se.PCTS},
        "auc_ci": None, "auc_p": None,
    }

    case_study = {name: se.top_region(sc, universe, gnodes) for name, sc in scores.items()}

    out = {
        "binary": os.path.basename(args.bin),
        "ground_truth": "function-level (ctags enclosing-function; amalgamation-safe)",
        "campaign": {"perturbations": camp["perts"], "diverged": camp["diverged"],
                     "universe_nodes": len(universe), "baseline_trace_len": camp["base_len"]},
        "bugs": len(bugs), "positives": sum(labels),
        "bug_reachability": bug_rows,
        "predictors": per_pred,
        "case_study_top_region": case_study,
    }
    out_path = args.out or (os.path.splitext(args.graph)[0] + ".funceval.json")
    json.dump(out, open(out_path, "w"), indent=2)

    # console report
    reached = [b for b in bug_rows if b["reached"]]
    print(f"campaign: {camp['perts']} perturbations, {camp['diverged']} diverged, "
          f"{len(universe)} executed nodes, baseline trace {camp['base_len']}")
    print(f"function-level GT: {len(reached)}/{len(bugs)} bugs reached -> "
          f"{sum(labels)} positive nodes")
    for b in bug_rows:
        tag = "REACHED" if b["reached"] else "unreached"
        print(f"  {b['bug_id']:<8} {str(b['function']):<22} {tag:<10} "
              f"({b['executed_region_nodes']}/{b['region_nodes']} region nodes executed)")
    print(f"\n== region-level ranking ({sum(labels)} positive nodes) ==")
    print(f"  {'predictor':<16}{'AUC':>8}{'95%CI':>16}{'perm_p':>9}{'AP':>8}"
          f"{'p@1':>7}{'p@5':>7}{'p@10':>7}{'p@20':>7}")
    for name in ["trajectory", "divergence", "value_localized", "value_firstbif", "coverage", "random"]:
        m = per_pred[name]; pa = m["precision_at"]; ci = m.get("auc_ci")
        ci_s = f"[{ci[0]:.3f},{ci[1]:.3f}]" if ci else "--"
        p_s = f"{m['auc_p']:.4f}" if m.get("auc_p") is not None else "--"
        print(f"  {name:<16}{m['auc']:>8}{ci_s:>16}{p_s:>9}{m['ap']:>8}"
              f"{pa['p1']:>7}{pa['p5']:>7}{pa['p10']:>7}{pa['p20']:>7}")
    print(f"\nmap: {out_path}")


if __name__ == "__main__":
    main()
