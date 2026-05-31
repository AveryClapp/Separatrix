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

**The deep reason (Discussion finding):** coverage does not distinguish
*bug-relevant* from *bug-irrelevant* control-flow activity. On the aligned target the
fault co-locates with *moderately-hot* nodes — **faults inhabit hot code as readily as
confounds do** — so dividing by execution count cannot separate "confound divergence"
(md4c's content-driven hot loops) from "signal divergence" (lua's bug-co-located hot
nodes). Coverage carries no information that separates the two. This is the **clean
limit of coverage-only reweighting in the oracle-free regime.**

## Scope of this negative (what was, and was not, tested)

This is a negative about **coverage-based conditioning**, *not* a claim that the
alignment limitation is irremovable in general:

- The conditioned signal **collapsed onto `inverse_coverage`** on md4c
  (0.1649 ≈ 0.1646), so the *only axis actually exercised was coverage* — the
  experiment tested "can dividing by execution count fix the confound," and the answer
  is no.
- The prereg also *named* a concentration/dispersion mechanism (steering off
  zero-divergence bytes). That mechanism was **not exercised here and is not being
  tested** — `edge_div/visits` does not implement it. Do not read this result as
  evidence about concentration/dispersion either way.
- The binding constraint on elevating the alignment theory from descriptive to
  predictive is **evidence breadth (n=1 aligned target)**, which a confound-fix would
  not move. We are therefore not pursuing a further conditioning variant; the scope
  stays descriptive.

## What stands

- The **descriptive alignment theory** is unaffected: divergence localizes to the
  degree input-variation intersects the fault (lua aligned 0.97; md4c misaligned —
  here raw divergence 0.75, top region the content-driven helper `membuf_append`, well
  below SBFL 0.92 in the one SBFL-applicable case).
- The **oracle-free localizer** (raw divergence) remains the contribution; this
  experiment confirms it should **not** be coverage-conditioned.
- The **md4c misalignment** stays a *documented limitation*, not a fixed one, and is
  framed as the dual of coincidental correctness (per `THEORY_EVIDENCE.md`).
- A clean, pre-registered negative: **coverage-based conditioning fails** — dividing
  divergence by execution count does not isolate the fault and destroys the localizer
  on the aligned target. This is a substantive result for the Discussion, not a null.
  (It is *not* a claim that the limitation is irremovable in general — see "Scope of
  this negative".)

## Artifacts

- Signal: `metric.conditioned_divergence` (TDD'd; `separatrix/test/test_metric_localize.py`).
- Predictors wired into `separatrix/cli/sep_eval.py` (`divergence_conditioned`,
  `inverse_coverage`), scored in one pass alongside raw divergence/coverage/SBFL.
- Eval outputs: `spike/lua_port/lua_phaseB.eval.json`,
  `/tmp/md4c_proto/work/md4c_phaseB.eval.json`.
- md4c reachability: bug region `md_link_label_cmp` REACHED (9 region nodes,
  fully reached by in028); differential oracle F=1 (in028) / P=36.

> **Reproducibility:** the md4c port has been promoted from `/tmp` to a first-class
> rebuildable target at `separatrix/eval/targets/md4c/` (`build.sh` clones
> md4c @ `da5821a` + applies the BugsC++ #4 buggy patch; md2html's own CLI is the
> harness; `bugs.json` + `corpus/` vendored). The rebuilt instrumented binary
> reproduces the original byte-for-byte (identical HTML, identical 5594-token trace
> on in028).
