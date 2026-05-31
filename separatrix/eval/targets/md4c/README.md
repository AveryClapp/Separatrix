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

## Scope note

This target was the **misalignment pole** in the descriptive alignment study and the
subject of the Phase-B coverage-conditioning negative. Its primary divergence-vs-SBFL
datapoint is the Milestone-1 **suite** setting (failing-vs-passing over the BugsC++
examples), where divergence ties SBFL. The Phase-B perturbation-**campaign** number is
a separate setting and must not be mixed with the suite number in one table.
