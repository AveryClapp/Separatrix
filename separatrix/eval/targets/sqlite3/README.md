# sqlite3 — oracle-free eval target (the DIFFUSE pole)

Second oracle-free target (Magma sqlite3, bugs SQL001–020). Its role in the paper
is the **diffuse middle** of the variation⇄fault alignment continuum — **not** a
second positive. A broad valid-SQL corpus couples only weakly to the scattered
cold faults, so divergence localization beats coverage and chance but only modestly.

## Regenerate (committed rule, directive-4)

```bash
# 1. instrumented build: patched amalgamation -> IR -> analyze -> link (~3 min)
bash build.sh <magma_repo> <work_dir>
# produces <work_dir>/{sqlite3_inst, sqlite3_core.sepgraph.json, bugs.json}
# and the patched source tree <work_dir>/repo

# 2. corpus (deterministic; seed 0x5EED) if not already present
python3 gen_corpus.py <work_dir>/corpus 300

# 3. function-level-GT eval campaign (~10 min)
python3 func_eval.py \
  --bin   <work_dir>/sqlite3_inst \
  --graph <work_dir>/sqlite3_core.sepgraph.json \
  --bugs  <work_dir>/bugs.json \
  --repo  <work_dir>/repo \
  --corpus <work_dir>/corpus \
  --seed-file <work_dir>/corpus/q0000.sql \
  -o <work_dir>/sqlite_funclevel.eval.json
```

## Regenerated result

| predictor | region-AUC | 95% CI | perm-p |
|---|---|---|---|
| **divergence** | **0.61** | [0.60, 0.63] | 5×10⁻⁴ |
| value-localized | 0.58 | [0.57, 0.60] | 5×10⁻⁴ |
| first-bifurcation | 0.50 | — | 1.0 |
| coverage | 0.47 (below chance) | [0.46, 0.48] | 1.0 |
| random | 0.50 | — | — |

12/20 bug functions reached by the corpus → 2619 / 15744 positive nodes.
Divergence is the only predictor reliably above chance, but at a *modest* 0.61
(far below lua's 0.97) with precision@1 = 0 — its single top region is a generic
hot mutex-assert (`sqlite3_mutex_held`), a hot-code confound like md4c's. Diffuse
but real: the weak-alignment regime the theory predicts.

## Why a function-level ground truth

The default `ground_truth.map_sites` keys nodes by file **basename**. sqlite is
built from the **amalgamation** (`sqlite3.c`), which flattens every `src/*.c` and
`ext/*.c` into one file with new line numbers, so a bug at `src/select.c:5526`
matches no node → 0 positives, every predictor AUC 0.50. The bridge that survives
amalgamation is the **function name** (kept via `-fno-discard-value-names`):
`func_eval.py` resolves each bug site to its enclosing C function via `ctags`
(greatest function-definition start-line ≤ the bug line, in the patched original
tree) and labels every executed node of that function. The campaign, attribution,
and AUC machinery are imported verbatim from `cli/sep_eval.py` so the divergence
signal cannot drift from the headline tool.

The 3 bugs that resolve to no in-graph function (`zipfile.c` ×2, `shell.c.in`) are
correctly excluded: they are not compiled into the library amalgamation.

## Bug-blind control (the diffuse pole is not a corpus artifact)

Like lua's `gen_corpus_blind.py`, sqlite now has a bug-blind control corpus that
exercises the **same subsystems** (planner, joins, aggregates, compound-select,
window functions) but **drops the query shapes nearest the SQL001-020 trigger
paths**: no `LEFT JOIN` (SQL010 outer-join where-term realloc), no `IN/EXISTS`
subqueries (SQL003 subquery flatten), no `UNION/INTERSECT/EXCEPT` (set-distinct,
SQL003/006). Same schema, same knob layout, same deterministic seed.

```bash
python3 gen_corpus_blind.py <work_dir>/corpus_blind 300
python3 func_eval.py --bin <work_dir>/sqlite3_inst \
  --graph <work_dir>/sqlite3_core.sepgraph.json --bugs <work_dir>/bugs.json \
  --repo <work_dir>/repo --corpus <work_dir>/corpus_blind \
  --seed-file <work_dir>/corpus_blind/q0000.sql \
  -o <work_dir>/sqlite_funclevel_blind.eval.json
```

| predictor | broad corpus | **bug-blind corpus** |
|---|---|---|
| divergence | 0.6143 | **0.622** |
| coverage | 0.468 (below chance) | 0.486 (below chance) |
| value-localized | 0.5845 | 0.5947 |
| bug functions reached | 12/20 | 11/20 |
| top divergence region | `sqlite3_mutex_held` | `sqlite3_mutex_held` (same hot-mutex confound) |

The result **reproduces under blinding** (0.61 → 0.62): divergence stays the only
predictor reliably above chance, coverage stays below chance, and the single top
region is the same generic hot mutex-assert. So the diffuse-pole signal is genuine
weak localization, **not** an artifact of the broad corpus quietly shaping queries
toward the bug sites. (One fewer bug function is reached — the one needing a
subquery/outer-join shape removed by the blinding — which is expected and minor.)

## Scope

This is **one datapoint on a continuum**, not a positive result. Do not present the
0.61 as validation that the method works on sqlite; present it as the diffuse pole —
divergence > coverage even under weak alignment, far short of a usable localizer.
