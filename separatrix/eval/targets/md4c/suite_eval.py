#!/usr/bin/env python3
"""Suite-based divergence-vs-SBFL localization on the promoted md4c #4 target.

This is the *suite* setting (the divergence-vs-SBFL comparison and md4c's
misalignment-pole role) — NOT the Phase-B perturbation campaign. It regenerates
the Milestone-1 figure from the canonical, rebuildable target so the cited number
is reproducible rather than a lost manual step.

  suite_eval.py <work_dir>

<work_dir> must hold both binaries + graph produced by this target's build.sh:
  build.sh <work_dir>                 -> md2html_inst, md4c_core.sepgraph.json
  BUILD_FIXED=1 build.sh <work_dir>   -> md2html_fixed   (uninstrumented clean ref)

================================ THE COMMITTED RULE ================================
Population = the 36 CommonMark-spec link-label examples (corpus/in*.md), labeled by
a TASK-CORRECTNESS oracle against the bundled expected HTML (expected/exp*.html):

  pass(binary, n)  :=  binary(in{n}) == exp{n}            (exact byte match)

  failing  := { n : buggy fails  AND fixed passes }       (bug manifests, not drift)
  passing  := { n : buggy passes AND fixed passes }
  DROPPED  := { n : fixed FAILS }  (version drift: the spec's expected HTML predates
              commit da5821a, so md2html's output differs for reasons unrelated to
              the injected bug — uninformative, removed by this filter)

This drop is part of the pipeline, not a manual step. Milestone-1 saw 29 passing +
1 failing, 6 dropped (= 36). The asserted-and-printed counts below let the reader
verify the population that produced the cited rank.
===================================================================================

Both methods then consume the IDENTICAL population/traces; the only asymmetry is the
benchmark handing SBFL one failing test. Line-level localization, GT = bugs.json
+/- WINDOW lines in md4c.c. Reports the rank of the first GT line out of all scored
lines for SBFL (ochiai/tarantula/dstar) and suite divergence (failing-excess).
"""
import json, os, subprocess, sys
from itertools import permutations

HERE = os.path.dirname(os.path.abspath(__file__))
SEP_PKG = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # .../separatrix
sys.path.insert(0, os.path.join(SEP_PKG, "detector"))
sys.path.insert(0, os.path.join(SEP_PKG, "eval"))
import metric, sbfl  # noqa: E402

WINDOW = 3  # GT line tolerance (line-level localization)


def _run(binary, inp, trace_path=None):
    env = dict(os.environ)
    if trace_path:
        env["SEP_TRACE"] = trace_path
    return subprocess.run([binary, inp], capture_output=True, env=env).stdout


def main(work):
    inst = os.path.join(work, "md2html_inst")
    fixed = os.path.join(work, "md2html_fixed")
    graph_path = os.path.join(work, "md4c_core.sepgraph.json")
    for p in (inst, fixed, graph_path):
        if not os.path.exists(p):
            sys.exit(f"missing {p}\n  build with: build.sh {work} AND BUILD_FIXED=1 build.sh {work}")

    graph = json.load(open(graph_path))
    node = {n["id"]: n for n in graph["nodes"]}
    gt_lines = {b["line"] for b in json.load(open(os.path.join(HERE, "bugs.json")))}
    gt_file = "md4c.c"

    corpus = os.path.join(HERE, "corpus")
    expected = os.path.join(HERE, "expected")
    examples = sorted(int(f[2:5]) for f in os.listdir(corpus) if f.startswith("in"))

    # --- the committed oracle + version-drift filter ---
    passing, failing, dropped = [], [], []
    for n in examples:
        inp = os.path.join(corpus, f"in{n:03d}.md")
        exp = open(os.path.join(expected, f"exp{n:03d}.html"), "rb").read()
        buggy_ok = _run(inst, inp) == exp
        fixed_ok = _run(fixed, inp) == exp
        if not fixed_ok:        dropped.append(n)      # version drift -> uninformative
        elif not buggy_ok:      failing.append(n)      # bug manifests as task failure
        else:                   passing.append(n)
    print(f"population: {len(passing)} passing, {len(failing)} failing {failing}, "
          f"{len(dropped)} dropped(version-drift) {dropped}")
    if not failing:
        sys.exit("no failing example -> SBFL inapplicable; population rule needs review")

    # --- one trace per population member (determinism is verified in build) ---
    edges = {}
    for n in passing + failing:
        edges[n] = metric.edge_multiset(
            [int(x) for x in open(_trace(inst, corpus, n, work)).read().split()])
    fail = failing[0]

    # --- executed-node universe (edge sources appearing in any trace) ---
    universe = set()
    for em in edges.values():
        for (s, _t) in em:
            universe.add(s)
    universe &= set(node)

    # --- SBFL on the identical population ---
    def covered(em):
        c = set()
        for (s, t) in em:
            c.add(s); c.add(t)
        return c & universe
    cov = {n: covered(em) for n, em in edges.items()}
    F, P = 1, len(passing)
    ef = {nid: (1 if nid in cov[fail] else 0) for nid in universe}
    ep = {nid: sum(1 for p in passing if nid in cov[p]) for nid in universe}
    sbfl_scores = {f: sbfl.score_all(ef, ep, F, P, universe, f)
                   for f in ("ochiai", "tarantula", "dstar")}

    # --- suite divergence: failing excess over passing-pair variation ---
    d_fail = {nid: 0.0 for nid in universe}
    for r in passing:
        for nid, m in metric.localized_divergence(edges[r], edges[fail]).items():
            if nid in d_fail:
                d_fail[nid] += m
    for nid in d_fail:
        d_fail[nid] /= len(passing)
    d_var = {nid: 0.0 for nid in universe}
    pairs = list(permutations(passing, 2))
    for r, p in pairs:
        for nid, m in metric.localized_divergence(edges[r], edges[p]).items():
            if nid in d_var:
                d_var[nid] += m
    for nid in d_var:
        d_var[nid] /= len(pairs)
    # The DISCRIMINATIVE signal (the headline): failing divergence in EXCESS of the
    # normal passing-pair variation. Subtracting d_var controls for the input-content
    # confound, so credit reflects what is special about the failing run, not merely
    # that in028's markdown content differs from the passing inputs.
    div_excess = {nid: max(0.0, d_fail[nid] - d_var[nid]) for nid in universe}
    # The NON-discriminative raw failing-vs-passing divergence, reported only to expose
    # the confound: it ranks the bug better here (it is inflated by content difference),
    # which is why the discriminative form is the one cited.
    div_raw = d_fail

    # --- node scores -> source lines (sum aggregation) ---
    def to_lines(scores):
        acc = {}
        for nid, s in scores.items():
            n = node[nid]
            if not n.get("file") or n.get("line", 0) <= 0:
                continue
            key = (os.path.basename(n["file"]), n["line"])
            acc[key] = acc.get(key, 0.0) + s
        return acc

    def is_gt(key):
        f, L = key
        return f == gt_file and min(abs(L - g) for g in gt_lines) <= WINDOW

    def rank(name, line_scores):
        ranked = sorted(line_scores.items(), key=lambda kv: (-kv[1], kv[0]))
        total = len(ranked)
        first = next((i for i, (k, _s) in enumerate(ranked) if is_gt(k)), None)
        if first is None:
            print(f"  {name:22s} NO gt line scored / {total} lines")
            return
        k, s = ranked[first]
        print(f"  {name:22s} first-gt rank {first+1:>4}/{total}  "
              f"(EXAM {first/total:.3f})  line {k[0]}:{k[1]} score {s:.4g}")

    print("=== suite line-level localization (agg=sum) ===")
    rank("divergence(excess)*", to_lines(div_excess))   # * = cited headline
    rank("divergence(raw-conf)", to_lines(div_raw))      # confounded, for contrast only
    for fml in ("ochiai", "tarantula", "dstar"):
        rank(f"sbfl/{fml}", to_lines(sbfl_scores[fml]))
    print("(* cited number = discriminative divergence(excess); raw-conf is shown only "
          "to expose the input-content confound and is NOT cited.)")


def _trace(binary, corpus, n, work):
    tp = os.path.join(work, f"_suite_tr_{n:03d}")
    _run(binary, os.path.join(corpus, f"in{n:03d}.md"), trace_path=tp)
    return tp


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: suite_eval.py <work_dir>")
    main(sys.argv[1])
