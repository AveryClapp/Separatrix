# Phase B Pre-Registration — Coverage-Conditioned Divergence

> **Locked before any scoring.** This document fixes the signal form, the targets,
> and the GO/NO-GO bar for the *one* bounded attempt to elevate the variation⇄fault
> alignment theory from **descriptive** to **predictive / fault-agnostic**. Committing
> this file precedes running the conditioned signal through `sep_eval.py`. No number
> below was obtained by peeking at a conditioned-signal score.

## 1. Hypothesis and mechanism

Divergence localization (`edge_div`) credits every node whose outgoing-edge profile
moves under perturbation. Its documented failure mode (md4c) is the **content
confound**: a hot, high-coverage node accumulates large divergence *mass* simply
because its iteration count scales with input content — not because it is faulty.
On md4c the top-ranked region is `md_unicode_bsearch__` (md4c.c:495–512, a
per-character Unicode codepoint binary search), driven by the failing input's
ligature characters, **not** the bug in `md_link_label_cmp` (md4c.c:1592–1611).

**Hypothesis.** Normalizing divergence mass by execution count — *divergence per
visit* — suppresses hot-loop confounds while preserving the signal on aligned
targets. Both inputs (`edge_div`, `visits`) are computable **without the fault**, so
the conditioned signal is **fault-agnostic**: this is what would make the alignment
theory predictive rather than merely descriptive.

## 2. The conditioned signal (exact, parameter-free)

For every node `n` in the executed universe (`universe = sorted(visits)`, so
`visits[n] ≥ 1` for all `n` — no division by zero):

```
divergence_conditioned[n] = edge_div[n] / visits[n]
```

where `edge_div[n]` is the accumulated `localized_divergence` mass at `n` over the
campaign, and `visits[n]` is `n`'s total execution count over the campaign (the
existing `coverage` signal). **One form. No tunable exponent, no smoothing constant,
no alternates.** It will be implemented test-first as a pure function
`metric.conditioned_divergence(edge_div, visits, universe)` (Task 4).

### Anti-degeneracy baseline

The worry behind condition (c) below: a `1/visits`-style signal can score "rare code
is suspicious" and accidentally rank a fault high without any divergence content. To
detect that degeneracy we add an explicit baseline predictor scored in the *same*
pass:

```
inverse_coverage[n] = 1.0 / visits[n]
```

If `divergence_conditioned` does not beat `inverse_coverage`, the divergence
numerator is doing no work and the "win" is just inverse-coverage → NO-GO.

## 3. Fixed targets (frozen — lua + md4c only)

sqlite3 is **out of scope** for this prereg (its instrumented binary and sepgraph are
gone, and it requires a non-standard function-level GT path that `sep_eval.py` does
not implement; its frozen AUC-0.61 result stays the documented diffuse pole). The
GO bar references only lua and md4c, both verified runnable in the current
environment on 2026-05-31.

| Target | `--bin` | `--graph` | `--bugs` | seed | `--corpus` | `--fail-oracle` |
|---|---|---|---|---|---|---|
| **lua** (bug-blind) | `spike/lua_port/lua_inst` | `spike/lua_port/lua_core.sepgraph.json` | `spike/lua_port/bugs.json` | `separatrix/eval/targets/lua/seeds/debug_blind.lua` | `spike/lua_port/corpus_blind/` (250) | `none` |
| **md4c** (BugsC++ #4) | `/tmp/md4c_proto/work/md2html_inst` | `/tmp/md4c_proto/work/md4c.sepgraph.json` | (written this session) | `/tmp/md4c_proto/work/pop/in001.md` | `/tmp/md4c_proto/work/pop/` (36) | `differential` (`--fixed-bin /tmp/md4c_proto/work/md2html_fixed`) |

- The lua config reproduces the frozen **bug-blind** run (divergence region-AUC
  **0.97**, coverage **0.89**, universe 2277, 250 perturbations). Conditions (b)/(c)
  are measured against that same setup.
- md4c `bugs.json` = the five ground-truth sites `{md4c.c: 1592,1593,1602,1608,1613}`
  in `md_link_label_cmp`, `--window 3` (matching the Milestone-1 prototype).
- **All predictors share one campaign per target.** `divergence`, `coverage`,
  `inverse_coverage`, `divergence_conditioned` (and SBFL on md4c, where the
  differential oracle applies) are scored over the identical node universe in a
  single `sep_eval.py` invocation. No target is re-run to obtain a better number.

## 4. GO / NO-GO bar

**Granularity:** region-level ROC-AUC (region = enclosing function), the granularity
of the frozen lua headline (0.97/0.89). Node-level reported alongside but not gating.
GO requires **all three** conditions.

### (a) md4c — confound suppression (the elevation test)

*Precondition (reported, not itself gating):* raw `divergence` on md4c exhibits the
content confound — its top-ranked region (`case_study_top_region["divergence"]`) is
**not** `md_link_label_cmp` (expected: `md_unicode_bsearch__` or another hot non-bug
region).

- **If the precondition holds**, (a) is GO iff `divergence_conditioned`:
  - **(a1)** region-AUC > raw `divergence` region-AUC, **and**
  - **(a2)** its top-ranked region (`case_study_top_region["divergence_conditioned"]`)
    **is** `md_link_label_cmp` — i.e. conditioning displaces the confound and surfaces
    the bug.
- **If the precondition fails** (raw divergence already ranks the bug region on top,
  i.e. the confound does not reproduce in the perturbation-campaign setting), then (a)
  is **untestable** → recorded as **NO-GO for elevation** (we cannot demonstrate
  fault-agnostic confound suppression). The descriptive theory is undisturbed; the
  conditioned signal simply was not shown to add predictive value.

### (b) lua — no degradation

`divergence_conditioned` region-AUC **≥ 0.90** (floor set 0.07 below the frozen
bug-blind divergence AUC of 0.97; derived from the committed prior result, not from
any new score).

### (c) lua — the divergence numerator does the work (not inverse-coverage)

On lua, `divergence_conditioned` region-AUC must exceed **both**:
- raw `coverage` region-AUC (frozen 0.89), **and**
- `inverse_coverage` region-AUC (the anti-degeneracy baseline, §2).

The second clause is the operationalization of "so it's not just inverse-coverage."

### Verdict

```
GO  ⇔  (a) ∧ (b) ∧ (c)
```

Any single failure ⇒ **NO-GO**. On NO-GO, md4c remains a *documented limitation*, the
conditioned signal is reported as a non-elevating refinement, and the paper's claim
stays descriptive (alignment theory + oracle-free localizer + the coincidental-
correctness duality). A NO-GO is a legitimate, publishable negative result — not a
failure of the experiment.

## 5. Integrity commitments

1. **One signal form**, fixed in §2 before any conditioned score exists. No exponent
   sweep, no "we also tried" variants selected post hoc.
2. **One scoring pass per target.** Raw divergence, coverage, inverse-coverage, and
   the conditioned signal are produced together; no target is re-run for a better
   number.
3. **No tuning on md4c.** The form is frozen before any md4c AUC is observed.
4. **The gate may fail.** A NO-GO is reported with the same prominence as a GO.
5. **STOP at the gate (Task 5).** Report GO/NO-GO with numbers; do not proceed to
   Phase C write-up framing without the gate outcome in hand.

## 6. Provenance

- Theory record: `docs/THEORY_EVIDENCE.md`; plan doc
  `docs/plans/2026-05-29-bugscpp-fl-competitiveness.md`.
- md4c confound diagnosis (Milestone-1, suite-based): memory `md4c-prototype-eyeball`
  (bug `md_link_label_cmp`, confound `md_unicode_bsearch__`).
- lua bug-blind frozen baseline: memory `lua-bug-blind-control`;
  `spike/lua_port/lua_blind.eval.json`.
- Harness verification (2026-05-31): lua + md4c runnable; md4c trace deterministic
  (5594 nodes), differential oracle viable on `in028`; sqlite out of scope.
