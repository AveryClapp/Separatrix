# Phase B Result — Coverage-Conditioned Divergence: **NO-GO**

> Pre-registered in `PHASEB_PREREG.md` (commit 734fadf, **before** any scoring).
> This records the outcome with equal prominence per the prereg's integrity
> commitment. The one bounded attempt to elevate the variation⇄fault alignment
> theory from *descriptive* to *predictive/fault-agnostic* **failed, decisively and
> for a principled reason.** The descriptive theory and the oracle-free localizer are
> undisturbed.

## Verdict

**NO-GO** — all three pre-registered GO conditions fail.

| Condition | Requirement | Result | Pass? |
|---|---|---|---|
| **(a)** md4c confound suppression | conditioned region-AUC > raw divergence **and** top region = `md_link_label_cmp` | conditioned **0.165** ≪ raw **0.746**; top region `md_analyze_line` | ❌ |
| **(b)** lua no-degradation | conditioned region-AUC ≥ **0.90** | conditioned **0.549** | ❌ |
| **(c)** lua, numerator does the work | conditioned > coverage (**0.891**) **and** > inverse-coverage (**0.109**) | conditioned **0.549** < coverage 0.891 | ❌ |

## Region-level AUC (the gating granularity)

| Predictor | **lua** (bug-blind, oracle none) | **md4c** (BugsC++ #4, differential oracle) |
|---|---|---|
| `divergence` (raw) | **0.9676** | 0.7464 |
| `divergence_conditioned` | **0.5486** | **0.1649** |
| `inverse_coverage` (baseline) | 0.1088 | 0.1646 |
| `coverage` | 0.8912 | 0.8354 |
| `value_localized` | 0.8459 | 0.5715 |
| SBFL (ochiai/tarantula/dstar) | N/A (no oracle) | 0.9239 |
| random | 0.4954 | 0.495 |

lua reproduces the frozen bug-blind baseline (divergence 0.97 / coverage 0.89), so
the comparison is on the same footing as the published headline.

## Why it failed (the mechanism — this is the finding)

Coverage-conditioning (`edge_div / visits`) assumes divergence mass is *spuriously
inflated by execution count everywhere*, so dividing it out should isolate the fault.
That assumption is **false on the aligned target**:

- **lua (aligned):** the high-divergence nodes *are* the bug subsystem (debug
  hooks/varargs). They are moderately hot, so dividing by `visits` **penalizes
  exactly the informative nodes** — collapsing the strong signal from **0.97 → 0.55**.
  Conditioning throws out the signal along with the (absent) confound.
- **md4c (misaligned):** conditioning collapses onto `inverse_coverage`
  (0.1649 ≈ 0.1646) — the exact degeneracy the prereg's anti-degeneracy baseline was
  built to detect. `1/visits` rewards the *rarest* (cold, non-bug) code and demotes
  the moderately-executed bug region **below chance (0.16)**. Raw divergence (0.75)
  and even raw coverage (0.84) both beat it.

**The deep reason:** coverage does not distinguish *bug-relevant* from
*bug-irrelevant* control-flow activity. There is no fault-agnostic reweighting *by
coverage alone* that separates "confound divergence" (md4c's content-driven hot
loops) from "signal divergence" (lua's bug-co-located hot nodes), because on aligned
targets the signal itself lives at moderately-hot nodes. The confound and the signal
are not separable on the coverage axis.

## What stands

- The **descriptive alignment theory** is unaffected: divergence localizes to the
  degree input-variation intersects the fault (lua aligned 0.97; md4c misaligned —
  here raw divergence 0.75, top region the content-driven helper `membuf_append`, well
  below SBFL 0.92 in the one SBFL-applicable case).
- The **oracle-free localizer** (raw divergence) remains the contribution; this
  experiment confirms it should **not** be coverage-conditioned.
- The **md4c misalignment** stays a *documented limitation*, not a fixed one, and is
  framed as the dual of coincidental correctness (per `THEORY_EVIDENCE.md`).
- A clean, pre-registered negative: the alignment limitation is **not removable by a
  coverage-only reweighting**. This is a substantive result for the Discussion, not a
  null.

## Artifacts

- Signal: `metric.conditioned_divergence` (TDD'd; `separatrix/test/test_metric_localize.py`).
- Predictors wired into `separatrix/cli/sep_eval.py` (`divergence_conditioned`,
  `inverse_coverage`), scored in one pass alongside raw divergence/coverage/SBFL.
- Eval outputs: `spike/lua_port/lua_phaseB.eval.json`,
  `/tmp/md4c_proto/work/md4c_phaseB.eval.json`.
- md4c reachability: bug region `md_link_label_cmp` REACHED (13 region nodes);
  differential oracle F=1 (in028) / P=36.

> **Reproducibility note (flag for cleanup):** the md4c instrumented binary, graph,
> and corpus currently live under `/tmp/md4c_proto/work/` (survived from the
> Milestone-1 prototype). They are *not* yet a committed first-class target like
> lua/sqlite. If md4c's Phase-B numbers are to appear in the paper, the md4c port
> should be promoted to `separatrix/eval/targets/md4c/` (build.sh + harness +
> bugs.json) so the result is rebuildable from source.
