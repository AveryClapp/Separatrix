# md4c eval target (BugsC++ md4c #4)

A first-class, rebuildable port of the BugsC++ `md4c` defect #4 — promoted from a
throwaway `/tmp` prototype so any md4c number cited in the paper reproduces from
source.

## The bug

A logical error in `md_link_label_cmp` (`src/md4c.c`): the loop end condition is
rewritten to use `a_reached_end`/`b_reached_end` flags but the `||` makes the loop
terminate on the wrong condition, so link-label comparison can mis-compare labels.
BugsC++ tag: `logical-error`. The fix is the dual condition described in md4c's
upstream "Fix the loop end condition (md_link_label_cmp)".

## Provenance

- Source: `https://github.com/mity/md4c.git` @ `da5821ae0ddb0e0cb853455dd018a7592a35151b`
  (the commit BugsC++ `taxonomy/md4c` checks out for this defect).
- Bug injection: `md4c004-buggy.patch` is BugsC++'s `0004-buggy.patch` verbatim,
  applied to `src/md4c.c`. (BugsC++'s `0004-common.patch` only edits the spec-test
  runner and is not needed for the Separatrix harness, so it is omitted.)
- `bugs.json` line numbers (1592, 1593, 1602, 1608, 1613) are the buggy-tree
  `md4c.c` lines the patch touches — the `reached_end` declarations, the rewritten
  `while`, and the two `reached_end` assignments.

## Build

```bash
./build.sh <work_dir>                 # instrumented buggy md2html + graph + bugs.json
BUILD_FIXED=1 ./build.sh <work_dir>   # uninstrumented clean reference (md2html_fixed)
```

The instrumented `md2html_inst` and the uninstrumented `md2html_fixed` together give
an output-differential oracle (a run fails iff their HTML digests differ).

## Harness

md4c's own `md2html` CLI is the harness — `md2html_inst <file.md>` reads the markdown
file from `argv[1]`, writes HTML to stdout, and (with `SEP_TRACE` set) writes the
node-id trace to that file. No separate harness TU is required.

`corpus/` holds the 36 markdown inputs (`in*.md`) used as the perturbation seeds /
suite population.

## Suite localization (the divergence-vs-SBFL datapoint)

`suite_eval.py <work_dir>` regenerates the line-level divergence-vs-SBFL comparison
from the canonical build under an explicit, committed oracle+filter rule (the rule is
documented in the script header — task-correctness against `expected/`, with the
version-drift both-fail drop). Build both binaries first:

```bash
./build.sh <work_dir>                 # md2html_inst + graph
BUILD_FIXED=1 ./build.sh <work_dir>   # md2html_fixed (clean reference)
python3 suite_eval.py <work_dir>
```

Regenerated population: **29 passing, 1 failing (in028), 6 dropped** (version-drift:
5, 13, 18, 22, 25, 32) = 36. Line-level first-GT ranks out of 1433 scored lines:

| signal | rank | note |
|---|---|---|
| divergence(excess) — **cited** | **29 / 1433** (top 2%, EXAM 0.020) | discriminative: failing excess over passing-pair variation |
| SBFL ochiai / tarantula / dstar | 17 / 20 / 16 | benchmark supplies the one failing test |
| divergence(raw) — *not cited* | 16 / 1433 | non-discriminative; inflated by the input-content confound |

**md4c is a misalignment pole, not a positive.** The discriminative divergence still
localizes the bug to the top 2%, but it does **not** beat SBFL here (best 16/1433) —
in contrast to lua, where divergence dominates. The earlier "ties SBFL at rank 16"
reading came from the *non-discriminative raw* failing-vs-passing divergence, which is
inflated by content difference between in028 and the passing inputs; the discriminative
form (the signal used everywhere else) gives 29, and that is the cited number.

## Scope: suite vs campaign — do not mix

This is the **suite** setting. The separate perturbation-**campaign** numbers
(divergence region-AUC 0.75; see below) belong only to the campaign docs and must not
appear in the same table as these suite ranks — different population, different oracle,
different granularity.

Campaign-setting predictor AUCs (region-level, differential oracle, F=1/P=36), from
`docs/PHASEB_RESULT.md` (Phase B) and `docs/PHASEC_RESULT.md` (Phase C):

| predictor | region-AUC | note |
|---|---|---|
| divergence (raw, oracle-free) | 0.746 | the contribution; top region a content helper |
| divergence_conditioned (Phase B) | 0.165 | coverage-conditioning NO-GO |
| divergence_dispersion (Phase C) | 0.637 | entropy-weighting NO-GO |
| **divergence_excess** (oracle-required) | **0.889** | failing-run divergence minus passing baseline; ported from the suite `div_excess` into `sep_eval.py` |
| coverage | 0.835 | |
| SBFL ochiai/tarantula/dstar | 0.924 | needs the oracle |

`divergence_excess` is the campaign port of the cited suite signal: it raises md4c
region-AUC from 0.75 (raw) to 0.89, beating coverage and approaching SBFL — but it
**requires a fail oracle** (it splits runs into failing/passing), so it is *not* in
the oracle-free class that is Separatrix's headline. Its #1 region is still the
`md_unicode_bsearch__` content confound (consistent with the suite's "top 2%, not
rank 1"). On oracle-free targets (lua) it is correctly reported N/A, alongside SBFL.
