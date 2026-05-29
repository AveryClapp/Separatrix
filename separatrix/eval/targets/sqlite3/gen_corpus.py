#!/usr/bin/env python3
"""Generate a corpus of valid SQL scripts for the sqlite3 Phase-4 eval campaign.

Byte-mutation of SQL overwhelmingly breaks parsing (as with lua source), so it
never reaches the semantic bug regions. Instead we vary independent, validity-
preserving knobs that exercise sqlite's query-planner / expression / compound-
select / window / aggregate subsystems — exactly where the Magma SQL bugs live
(select.c, where.c, whereexpr.c, expr.c, window.c, resolve.c, vdbe.c, ...). The
eval asks whether trajectory divergence localizes those spots among the broadly-
exercised code. Generation is deterministic (seeded) so the campaign reproduces.

Every script is self-contained: fixed seed schema + data, then one varied query.

  gen_corpus.py <out_dir> [n]
"""
import itertools, os, random, sys

# Fixed seed schema + data: two base tables with overlapping keys (joins), an
# indexed column (planner choices), NULLs (three-valued logic), and duplicates
# (DISTINCT / GROUP BY). Identical across the corpus so the only variation is the
# query, isolating which subsystem each script stresses.
PRELUDE = """CREATE TABLE t(id INTEGER PRIMARY KEY, k INTEGER, v TEXT, w REAL);
CREATE TABLE u(id INTEGER PRIMARY KEY, k INTEGER, tag TEXT);
CREATE INDEX it_k ON t(k);
INSERT INTO t(id,k,v,w) VALUES
 (1,10,'a',1.5),(2,10,'b',2.5),(3,20,'a',NULL),(4,30,'c',3.0),
 (5,20,'b',2.5),(6,40,NULL,4.0),(7,10,'a',1.5),(8,50,'z',9.0);
INSERT INTO u(id,k,tag) VALUES
 (1,10,'p'),(2,20,'q'),(3,20,'p'),(4,60,'r'),(5,10,'q');
"""

# --- independent knobs (cartesian product, deterministic sample) ---
COLS      = ["t.id, t.k, t.v", "t.*", "t.k, count(*)", "t.v, sum(t.w)"]
JOIN      = ["", "JOIN u ON u.k=t.k", "LEFT JOIN u ON u.k=t.k", ", u"]
WHERE     = ["", "WHERE t.k>=20", "WHERE t.v IS NOT NULL", "WHERE t.k IN (SELECT k FROM u)",
             "WHERE EXISTS (SELECT 1 FROM u WHERE u.k=t.k)", "WHERE t.w BETWEEN 1 AND 3"]
GROUP     = ["", "GROUP BY t.k", "GROUP BY t.k HAVING count(*)>1", "GROUP BY t.v"]
ORDER     = ["", "ORDER BY t.k", "ORDER BY t.k DESC, t.id", "ORDER BY 1"]
LIMIT     = ["", "LIMIT 3", "LIMIT 5 OFFSET 1"]
COMPOUND  = ["", "UNION ALL SELECT id,k,v,w FROM t", "UNION SELECT id,k,v,w FROM t",
             "INTERSECT SELECT id,k,v,w FROM t", "EXCEPT SELECT id,k,v,w FROM t"]
WINDOW    = ["", "SELECT t.k, row_number() OVER (PARTITION BY t.k ORDER BY t.id) FROM t",
             "SELECT t.k, sum(t.w) OVER (ORDER BY t.id) FROM t"]


def query(cols, join, where, group, order, limit, compound, window):
    if window:                                  # window-function scripts stand alone
        return window + ";"
    # a compound (UNION/...) requires matching column counts -> use the 4-col form
    if compound:
        return f"SELECT id,k,v,w FROM t {where} {compound};"
    sel = f"SELECT {cols} FROM t {join} {where} {group} {order} {limit}".strip()
    return " ".join(sel.split()) + ";"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "corpus"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".sql"):
            os.remove(os.path.join(out, f))

    combos = list(itertools.product(COLS, JOIN, WHERE, GROUP, ORDER, LIMIT, COMPOUND, WINDOW))
    rng = random.Random(0x5EED)
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
        fh.write("sqlite3 valid-SQL corpus (structured variants, NOT byte-mutation)\n")
        fh.write(f"generator     : gen_corpus.py (deterministic, seed 0x5EED)\n")
        fh.write(f"requested     : {n}\n")
        fh.write(f"written       : {written}\n")
        fh.write("knobs         : cols/join/where/group/order/limit/compound/window\n")
    print(f"generated {written} valid SQL variants -> {out}")


if __name__ == "__main__":
    main()
