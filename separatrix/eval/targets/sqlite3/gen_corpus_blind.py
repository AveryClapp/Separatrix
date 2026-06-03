#!/usr/bin/env python3
"""BUG-BLIND sqlite3 corpus — the control for the sqlite diffuse-pole result.

Structurally identical to gen_corpus.py (same PRELUDE schema/data, same knob
layout, same deterministic cartesian-sample) so the ONLY difference is that the
knob VALUES drop the query shapes that sit closest to the known SQL001-020 trigger
paths, while STILL exercising the same subsystems (query planner, joins,
aggregates, compound-select, window functions). This mirrors lua's
gen_corpus_blind.py: keep the subsystem reachable, remove the trigger-adjacent
shaping.

What is removed vs gen_corpus.py, and why (per memory `magma-triggering-bottleneck`
— the hand-crafted sqlite trigger attempts were SQL003 distinct-subquery-flatten,
SQL006 distinct+window, SQL010 LEFT-JOIN where-term realloc):

  gen_corpus.py (broad)                 gen_corpus_blind.py (blind)
  JOIN includes "LEFT JOIN ..."         INNER JOIN / comma-join only
   (outer-join where-term realloc,       (still joins.c / where.c, no outer-join
    SQL010-adjacent)                      realloc path)
  WHERE includes IN (SELECT...) /        scalar predicates only (k>=, IS NOT NULL,
    EXISTS (SELECT...)                    BETWEEN, comparison)
   (subquery flattening, SQL003-adj.)    (still where.c/whereexpr.c, no flatten)
  COMPOUND includes UNION / INTERSECT /  UNION ALL only
    EXCEPT (DISTINCT-compound)           (still select.c compound path, no
   (set-distinct machinery, SQL003/006)   distinct dedup near the bugs)

The planner/join/aggregate/window/compound subsystems are STILL exercised (so the
12/20 reached bug functions should remain reached and in the executed universe —
verified post-hoc by func_eval's reachability report), but no script is shaped to
sit on a bug's flatten/realloc/distinct path. If divergence still ranks the bug
functions at ~AUC 0.61 here, the diffuse-pole result is genuine localization, not a
corpus that quietly targets the bug sites; if it collapses to coverage, the 0.61
was corpus shaping.

  gen_corpus_blind.py <out_dir> [n]
"""
import itertools, os, random, sys

# Identical schema + data to gen_corpus.py (the only-the-query-varies invariant).
PRELUDE = """CREATE TABLE t(id INTEGER PRIMARY KEY, k INTEGER, v TEXT, w REAL);
CREATE TABLE u(id INTEGER PRIMARY KEY, k INTEGER, tag TEXT);
CREATE INDEX it_k ON t(k);
INSERT INTO t(id,k,v,w) VALUES
 (1,10,'a',1.5),(2,10,'b',2.5),(3,20,'a',NULL),(4,30,'c',3.0),
 (5,20,'b',2.5),(6,40,NULL,4.0),(7,10,'a',1.5),(8,50,'z',9.0);
INSERT INTO u(id,k,tag) VALUES
 (1,10,'p'),(2,20,'q'),(3,20,'p'),(4,60,'r'),(5,10,'q');
"""

# --- independent knobs (same layout as gen_corpus.py; trigger-adjacent values removed) ---
COLS      = ["t.id, t.k, t.v", "t.*", "t.k, count(*)", "t.v, sum(t.w)"]
JOIN      = ["", "JOIN u ON u.k=t.k", ", u"]              # no LEFT JOIN (SQL010-adjacent realloc)
WHERE     = ["", "WHERE t.k>=20", "WHERE t.v IS NOT NULL",
             "WHERE t.w BETWEEN 1 AND 3", "WHERE t.k<>30"]  # scalar only; no IN/EXISTS subquery (flatten)
GROUP     = ["", "GROUP BY t.k", "GROUP BY t.k HAVING count(*)>1", "GROUP BY t.v"]
ORDER     = ["", "ORDER BY t.k", "ORDER BY t.k DESC, t.id", "ORDER BY 1"]
LIMIT     = ["", "LIMIT 3", "LIMIT 5 OFFSET 1"]
COMPOUND  = ["", "UNION ALL SELECT id,k,v,w FROM t"]      # UNION ALL only; no UNION/INTERSECT/EXCEPT (set-distinct)
WINDOW    = ["", "SELECT t.k, row_number() OVER (PARTITION BY t.k ORDER BY t.id) FROM t",
             "SELECT t.k, sum(t.w) OVER (ORDER BY t.id) FROM t"]


def query(cols, join, where, group, order, limit, compound, window):
    if window:                                  # window-function scripts stand alone
        return window + ";"
    if compound:                                # compound requires matching column counts
        return f"SELECT id,k,v,w FROM t {where} {compound};"
    sel = f"SELECT {cols} FROM t {join} {where} {group} {order} {limit}".strip()
    return " ".join(sel.split()) + ";"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "corpus_blind"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".sql"):
            os.remove(os.path.join(out, f))

    combos = list(itertools.product(COLS, JOIN, WHERE, GROUP, ORDER, LIMIT, COMPOUND, WINDOW))
    rng = random.Random(0x5EED)                 # same seed as gen_corpus.py (matched sampling)
    rng.shuffle(combos)

    seen, written = set(), 0
    for c in combos:
        q = query(*c)
        if q in seen:
            continue
        seen.add(q)
        with open(os.path.join(out, f"q{written:04d}.sql"), "w") as fh:
            fh.write(PRELUDE + q + "\n")
        written += 1
        if written >= n:
            break

    with open(os.path.join(out, "PROVENANCE.txt"), "w") as fh:
        fh.write("sqlite3 BUG-BLIND valid-SQL corpus (control for the diffuse-pole result)\n")
        fh.write("generator     : gen_corpus_blind.py (deterministic, seed 0x5EED)\n")
        fh.write(f"requested     : {n}\n")
        fh.write(f"written       : {written}\n")
        fh.write("blinding      : no LEFT JOIN, no IN/EXISTS subquery, no UNION/INTERSECT/EXCEPT\n")
        fh.write("                (trigger-adjacent shapes removed; subsystems still exercised)\n")
    print(f"generated {written} bug-blind SQL variants -> {out}")


if __name__ == "__main__":
    main()
