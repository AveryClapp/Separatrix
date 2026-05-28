#!/usr/bin/env python3
"""Trigger-feasibility probe — Task 2 DECISION GATE for the SBFL baseline.

For every input in the corpus (plus the seed) we run the instrumented target,
collect the canary-trigger (file,line) set via $MAGMA_TRIGGERS (through the
shared sep_eval.run so the probe and the campaign cannot drift), and map each
trigger to a bug_id by EXACT (basename, line) match against bugs.json.

It answers the only question that decides whether real SBFL is measurable here:
does this corpus actually *trigger* bugs, or merely *reach* them? Output is a
per-bug trigger table plus the overall failing-run count (a run "fails" iff it
triggers >= 1 bug).

  probe_triggers.py --bin B --bugs bugs.json --corpus dir [--seed-file seed]

Exact match is correct because MAGMA_LOG expands __LINE__ to the same line
extract_bugs.py recorded; a default +/-2 band would mis-attribute when two
canaries sit close (e.g. LUA001/002/004 all in ldebug.c). Unmatched triggers are
reported loudly rather than silently banded.
"""
import argparse, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cli"))
import sep_eval  # noqa: E402  (provides run(): single source of trigger collection)


def _base(p):
    return os.path.basename(p or "")


def parse_trigger(s):
    """'/abs/repo/ldebug.c:920' -> ('ldebug.c', 920)."""
    path, _, line = s.rpartition(":")
    return _base(path), int(line)


def load_inputs(corpus_dir, seed_file):
    inputs = []
    if seed_file:
        inputs.append(("<seed>", open(seed_file, "rb").read()))
    for name in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, name)
        if os.path.isfile(path):
            inputs.append((name, open(path, "rb").read()))
    return inputs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--bugs", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--seed-file", default=None)
    args = ap.parse_args()

    bugs = json.load(open(args.bugs))
    # (basename, line) -> bug_id ; site label for the table
    site2bug = {(_base(b["file"]), b["line"]): b["bug_id"] for b in bugs}
    site_label = {b["bug_id"]: f"{_base(b['file'])}:{b['line']}" for b in bugs}

    inputs = load_inputs(args.corpus, args.seed_file)
    tmpdir = tempfile.mkdtemp(prefix="sep_probe_")
    inpath = os.path.join(tmpdir, "in")
    tpath = os.path.join(tmpdir, "t")
    gpath = os.path.join(tmpdir, "trig")

    trig_runs = {b["bug_id"]: 0 for b in bugs}   # runs that triggered this bug
    failing = 0                                   # runs that triggered >= 1 bug
    unmatched = {}                                # (basename,line) -> count, no bug match
    total = len(inputs)

    for _, data in inputs:
        _, _, trig = sep_eval.run(args.bin, data, inpath, tpath, gpath=gpath)
        bugs_hit = set()
        for s in trig:
            key = parse_trigger(s)
            bug = site2bug.get(key)
            if bug is None:
                unmatched[key] = unmatched.get(key, 0) + 1
            else:
                bugs_hit.add(bug)
        for bug in bugs_hit:
            trig_runs[bug] += 1
        if bugs_hit:
            failing += 1

    # --- report ---
    print(f"probe: {total} inputs ({'seed + ' if args.seed_file else ''}"
          f"{total - (1 if args.seed_file else 0)} corpus)\n")
    print(f"  {'bug_id':<8} {'site':<18} triggered_runs / total")
    for b in bugs:
        bid = b["bug_id"]
        print(f"  {bid:<8} {site_label[bid]:<18} {trig_runs[bid]} / {total}")
    print(f"\nfailing runs (any bug): {failing} / {total}")

    if unmatched:
        print("\n[WARN] triggers with no exact bugs.json match "
              "(consider a +/-2 fallback band):")
        for (f, ln), c in sorted(unmatched.items()):
            print(f"  {f}:{ln}  x{c}")

    # --- decision hint (the gate is the human's; this just frames it) ---
    reached_with_5 = sum(1 for bid in trig_runs if trig_runs[bid] >= 5)
    print("\ndecision:")
    if failing >= 10 and reached_with_5 >= 1:
        print("  trigger oracle VIABLE (F >= 10 and a bug with >= 5 triggers) "
              "-> Task 4/5 with trigger oracle; skip Task 3.")
    elif failing == 0:
        print("  trigger oracle DEGENERATE (F == 0) -> Task 3 differential oracle "
              "required before Task 5.")
    else:
        print(f"  trigger oracle BORDERLINE (F == {failing}) -> proceed with "
              "small-N caveat; consider Task 3 as a cross-check.")


if __name__ == "__main__":
    main()
