# Separatrix — Consolidated Evidence (theory paper)

> Working consolidation across all four targets. The contribution is **oracle-free
> trajectory-divergence localization** + the **variation⇄fault alignment theory** +
> its **duality with coincidental correctness** — NOT an SBFL-beating localizer and
> NOT an "N programs" robustness claim. Read the table as *one strong positive + a
> continuum that the theory predicts + a synthetic generality demo*.

## The evidence at a glance

| Target | Regime | Headline numbers | Role in the argument |
|---|---|---|---|
| **lua** (Magma LUA001–004) | oracle-free; SBFL **inapplicable** (debug-subsystem bugs don't surface in output) | bug-blind control (frozen `lua_blind.eval.json`): region **AUC 0.97** / node **0.97** divergence vs coverage **0.89** / **0.91**; value-distance **0.85**; first-bifurcation **0.50** | **The single STRONG oracle-free positive.** Divergence dominates coverage *even when the corpus is bug-blind*, so the win is the trajectory signal, not trigger leakage. Demonstrates uniqueness: localization where SBFL cannot run. |
| **sqlite3** (amalgamation, oracle-free; function-level GT) | oracle-free | divergence region-**AUC 0.61** (95% CI [0.60,0.63], perm-p 5e-4) vs coverage **0.47** (below chance), value 0.58, first-bif 0.50; 12/20 bug functions reached, 2619/15744 positive nodes. Regenerates from `targets/sqlite3/{build.sh,func_eval.py}` (ctags enclosing-function GT, amalgamation-safe). | **The DIFFUSE pole.** Variation over a broad SQL corpus couples only weakly to scattered cold faults: divergence beats coverage and chance but at a *modest* 0.61 (precision@1 = 0; top region is a generic hot mutex-assert). NOT a second positive — the weak-alignment middle of the continuum. |
| **md4c** (BugsC++ #4; SBFL **applies**) | oracle-bearing (suite) | divergence(excess) **rank 29 / 1433** (top 2%); does **not** beat SBFL (best dstar/ochiai **16–17 / 1433**). Regenerates from `targets/md4c/suite_eval.py`. | **The MISALIGNED pole.** Divergence's *top* ranks are a bug-irrelevant Unicode hot loop (the content confound); SBFL is immune (high coverage → low suspiciousness). A case study in misalignment, not a loss. (A non-discriminative raw divergence "ties" SBFL at 16 but is confound-inflated; not cited.) |
| **agentic spike** (synthetic, `agent_attrib_spike/`) | replayable synthetic; author-injected faults | outcome-flip vs cascade-null (n=107, frozen `results.json`): MRR **0.87 vs 0.24** (**Δ 0.62**), top-1 **0.83 vs 0.05**, one-sided Wilcoxon **p ≈ 9×10⁻¹⁹** | **Synthetic generality demo (mechanism-level).** The counterfactual primitive separates from its own autoregressive-cascade artifact beyond the C substrate. NOT real-agent validation (no public replayable benchmark). |

## The alignment continuum (what the table is really showing)

These four are **not** four independent wins. They are a single ordered axis —
*how much the perturbation/variation axis intersects the fault*:

```
aligned  ───────────────────────────────────────────────►  misaligned
  lua                    sqlite3                    md4c
  AUC 0.97               div 0.61 vs cov 0.47       div(excess) 29 vs SBFL 16
  variation hits         variation only             variation concentrates on a
  the fault              weakly couples to it       bug-IRRELEVANT hot region
```

Divergence localization works **exactly to the degree the input-variation axis
overlaps the fault**. lua's perturbations bifurcate at the faulted debug logic;
sqlite's couple only weakly; md4c's pile onto a content-driven hot loop that has
nothing to do with the bug. The theory *predicts* this ordering — it is the
explanatory content of the contribution, not a robustness average.

## The duality with coincidental correctness

The same alignment condition is the **missing dual** to coincidental correctness
in the SBFL literature:

- **SBFL fails** when passing tests *coincidentally* execute the faulty statement
  without failing — coverage stops discriminating (coincidental correctness).
- **Divergence fails** when the input distribution's variation *coincidentally*
  concentrates off the fault (md4c) — perturbation stops discriminating.

Both methods are bounded by the **same** thing from opposite sides: the relation
between the probing distribution and the fault. SBFL needs failing/passing tests
that split *on* the fault; divergence needs input variation aligned *with* the
fault. Naming divergence's failure mode as the dual of coincidental correctness
positions it in established FL theory rather than as an ad-hoc limitation.

## Honest framing guardrails (carry into the paper)

- **One strong positive (n=1 program).** lua is the load-bearing oracle-free
  result. Do not phrase sqlite/md4c as additional positives.
- **No SBFL-beating claim.** On md4c divergence(excess) ranks the bug 29/1433 vs
  SBFL's best 16/1433 — competitive (top 2%) but **not** beating; SBFL is the
  head-to-head only where an oracle exists.
- **No "multiple programs" robustness claim.** The cross-target story is the
  *continuum*, not an average over a sample.
- **Agentic = synthetic, mechanism-level.** Author-built system, author-injected
  faults; the non-tautological finding is "cascade confound is real, causal
  primitive avoids it." Real-agent validation is explicitly out of scope (blocked).
- **md4c content confound stays a documented limitation.** The one bounded attempt
  to remove it without an oracle — Phase B's coverage-conditioned divergence — is a
  pre-registered **NO-GO** (`docs/PHASEB_RESULT.md`): coverage-based reweighting
  destroys the localizer (lua 0.97→0.55) and collapses to inverse-coverage on md4c.
  The negative is scoped to *coverage-only* reweighting, not general impossibility.
