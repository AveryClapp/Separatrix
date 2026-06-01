# Separatrix — Results & Discussion (draft, descriptive scope)

> Scope of this draft: **Results** and **Discussion** only (no abstract/intro).
> The contribution is **descriptive**: an oracle-free trajectory-divergence
> localizer and the *variation⇄fault alignment* characterization that explains
> when it works and when it does not. There is **no predictive-elevation claim**
> (the one bounded attempt to elevate the theory is a pre-registered NO-GO,
> reported in Discussion §3).
>
> **Evidence-tier discipline (read before tallying anything):** the empirical
> base is **one positive** (lua), **two limitation poles** (sqlite, md4c — these
> are *not* positives), and **one synthetic generality probe** (the agentic
> spike — mechanism-level, not a real-agent result). A reader should never
> conclude "four programs support the method." Each target plays a distinct,
> labeled role; see the eval outline (§Results.5).
>
> All numbers below are quoted from frozen committed artifacts (cited inline),
> each regenerating from a committed pipeline (including sqlite, §Results.2,
> rebuilt under a function-level ground-truth rule).

---

## Results

### 1. The localizer and the single positive (lua)

Separatrix scores each behavioral-graph node by **divergence localization**: for a
baseline input X and a perturbation X+ε, it credits every node whose
outgoing-edge profile diverges from baseline (the per-node form of the
trajectory-divergence metric), not only the first node where trajectories split.
Both inputs are computable **without a per-run pass/fail oracle**, so the score is
oracle-free.

On the Magma lua port (LUA001–004), scored **bug-blind** (the localizer never sees
which runs trigger a bug), divergence localization ranks the bug-containing
regions far above coverage (frozen: `spike/lua_port/lua_blind.eval.json`, and
identically in `lua_phaseB.eval.json`):

| predictor (lua, oracle-free, bug-blind) | region ROC-AUC | node ROC-AUC |
|---|---:|---:|
| **divergence localization** | **0.97** [0.95, 0.98] | **0.97** [0.96, 0.98] |
| coverage frequency | 0.89 | 0.91 |
| value-space output distance (same localization) | 0.85 | 0.85 |
| value distance via first-bifurcation | 0.50 | 0.50 |
| inverse-coverage | 0.11 | 0.09 |
| random | 0.50 | 0.51 |

(Region positives = 31, node positives = 6; bracketed = bootstrap 95% CI; all
non-random AUCs have permutation p ≤ 0.001.)

Two controls isolate *what* carries the signal:

- **It is the trajectory signal, not the attribution mechanism.** Value-space
  output distance, attributed through the *identical* per-node localization, scores
  only 0.85 — below divergence's 0.97. The win is in the trajectory divergence,
  not in how credit is assigned.
- **It is the per-node form, not first-bifurcation.** The same value signal
  attributed by first-bifurcation (credit only the single node where trajectories
  first split) collapses to AUC **0.50** on this staged target
  (lex→parse→compile→exec): first-bifurcation only ever credits the front-end.
  Divergence localization reaches the downstream debug subsystem where the bugs
  live.

**Uniqueness.** lua's LUA001–004 are debug-subsystem bugs that do **not** manifest
in observable output, so a per-run pass/fail oracle is unavailable and
spectrum-based fault localization (SBFL) is **inapplicable** (the eval records
`sbfl.available = false`, "no valid fail-oracle on this target"). lua therefore
demonstrates the localizer working precisely where the standard oracle-bearing
baseline cannot run — this is the contribution's distinctive regime, not a
head-to-head win.

### 2. Limitation pole A — sqlite (diffuse)

sqlite is the **diffuse** end of the alignment continuum, **not** a second
positive. A broad valid-SQL corpus (300 deterministic query variants over a
15.7k-node executed universe, oracle-free) induces variation that is only
*diffusely* related to the scattered optimizer-code faults. Under a function-level
ground truth (see below), 12 of 20 Magma bug functions are reached; divergence
localization ranks those bug regions at **region-AUC 0.61** (95% CI [0.60, 0.63],
permutation p = 5×10⁻⁴), versus **coverage 0.47** (below chance, CI [0.46, 0.48],
not significant), value-localization 0.58, and first-bifurcation 0.50 (chance).
So divergence is the only predictor reliably above chance — but at a *modest* 0.61,
far below lua's 0.97, and with precision@1 = 0 (its single top region is a generic
hot mutex-assert, `sqlite3_mutex_held`, a content/hot-code confound much like
md4c's). This is the predicted weak-alignment regime: the broad corpus couples to
the cold faults weakly rather than concentrating on any one, so the signal is real
and still beats coverage, but is far from a strong localizer.

> **Regeneration (directive-4 committed rule).** The earlier "divergence 0.61 vs
> coverage 0.47" figure originally did **not** regenerate from the committed
> `sqlite_oraclefree.eval.json`, which maps ground truth by file basename while the
> sqlite **amalgamation flattens all files** into `sqlite3.c` — so the bug sites
> (`src/select.c`, …) matched no nodes and every predictor scored AUC 0.50. It now
> regenerates from a committed pipeline: `targets/sqlite3/build.sh` re-instruments
> the patched amalgamation (66.6k-node graph) and `targets/sqlite3/func_eval.py`
> resolves each bug site to its **enclosing C function via ctags** (the bridge that
> survives amalgamation, since function names are preserved) and runs the shared
> campaign + AUC machinery from `cli/sep_eval.py`. The 0.61 / 0.47 split
> reproduces (`spike/sqlite_port/sqlite_funclevel.eval.json`). Baseline seed:
> `corpus/q0000.sql`. The 3 unmatched bugs (`zipfile.c` ×2, `shell.c.in`) are
> correctly excluded — they are not compiled into the library amalgamation.

### 3. Limitation pole B — md4c (misaligned, the confound pole)

On BugsC++ md4c #4 (a logical error in `md_link_label_cmp`), in the **suite**
setting (line-level; one benchmark-supplied failing test + a passing population —
the only setting where SBFL is applicable), the discriminative divergence
localizes the bug to **rank 29 / 1433** (top 2%) but **does not beat SBFL**
(best dstar/ochiai **16–17 / 1433**). This regenerates from the canonical target
under a committed oracle+filter rule
(`separatrix/eval/targets/md4c/suite_eval.py`; population 29 pass / 1 fail / 6
version-drift dropped, 1433 scored lines):

| signal (md4c suite) | first-GT rank / 1433 |
|---|---:|
| divergence (excess) — **cited** | **29** (top 2%) |
| SBFL ochiai / tarantula / dstar | 17 / 20 / 16 |
| divergence (raw) — *not cited, confounded* | 16 |

The *reason* md4c is misaligned is diagnostic: the failing input's unusual ligature
content (ﬕ/ﬗ) drives extra iterations in a per-codepoint Unicode loop
(`md4c.c:495–512`) that is **bug-irrelevant**, and divergence rewards that
content-driven activity. A non-discriminative raw failing-vs-passing divergence
even "ties" SBFL at rank 16 — but *only* because it is inflated by that confound;
the discriminative form (the one used everywhere else) gives 29, and that is what
we cite. md4c is a **case study of one** (n=1); we make **no** "competitive when
applicable" generalization from it.

### 4. Synthetic generality (agentic spike — mechanism-level only)

To probe whether the trajectory-attribution idea transfers beyond C control flow,
a synthetic, seeded, mechanism-faithful agent harness runs a kill-test (n = 107
instances): attribute the decision whose counterfactual **outcome-flip** changes an
agent's final result, vs a divergence-null that does not separate the true cause
from the autoregressive cascade it triggers.

| metric (synthetic agent, n=107) | divergence-null | outcome-flip |
|---|---:|---:|
| MRR of true cause | 0.24 | **0.87** |
| top-1 accuracy | 0.05 | **0.83** |

(Δ_MRR = **+0.62**; one-sided Wilcoxon **p ≈ 9 × 10⁻¹⁹**; frozen:
`agent_attrib_spike/results.json`, `replay.py` reproduces offline from the cached
manifest.) Separation holds across fault position (Δ_MRR 0.59 / 0.72 / 0.56 at
early/mid/late). **This is a synthetic mechanism check, not a result about real
LLM agents in production**, and n=1 at the mechanism level. It indicates the
bifurcation-attribution idea is not C-specific; it does not validate a system.

### 5. Eval outline (claim → evidence → role)

| # | target | setting / oracle | headline number | role | does NOT support |
|---|---|---|---|---|---|
| 1 | **lua** | oracle-free, bug-blind | div 0.97 region / 0.97 node vs cov 0.89 / 0.91 | **the positive** (+ uniqueness: SBFL inapplicable) | a multi-program robustness claim |
| 2 | sqlite | oracle-free, function-level GT | div region-AUC 0.61 vs cov 0.47 (12/20 bugs reached) | limitation pole — *diffuse* (weak but >coverage) | a second positive; a strong-localizer claim (precision@1 = 0) |
| 3 | md4c | suite, 1 fail + 29 pass | div(excess) 29/1433 vs SBFL 16/1433 | limitation pole — *misaligned* (case study, n=1) | "competitive when applicable"; SBFL-beating |
| — | md4c | Phase-B perturbation campaign | div region-AUC 0.75 | **only** the conditioning negative (§Disc.3) | anything in the suite table above |
| 4 | agentic | synthetic kill-test, n=107 | MRR 0.87 vs 0.24, top-1 0.83 vs 0.05 | synthetic generality (mechanism) | a real-agent result |

> Settings never mix: the md4c **suite** ranks and the md4c **campaign** AUC are
> different population/oracle/granularity and do not share a table.

---

## Discussion

### 1. The variation⇄fault alignment theory (descriptive)

The results fall on a single axis. Divergence localization works **to the degree
that the input-variation it induces intersects the fault's control flow**:

- **lua — aligned.** Perturbing inputs drives variation straight through the
  debug subsystem where the bugs live → strong localization (0.97).
- **sqlite — diffuse.** Variation spreads thinly across the amalgamation; it
  touches the scattered faults but is not concentrated there → weak coupling
  (AUC 0.61: above coverage and chance, but far below the aligned pole).
- **md4c — misaligned.** Variation concentrates on a content-driven hot loop that
  is *not* the fault → the signal is pulled off-target (the confound).

This is the descriptive core: a *characterization of the operating regime*, read
off the same metric across the continuum, not a predictive model of fault location.

### 2. Duality with coincidental correctness

The md4c failure is the **dual** of SBFL's classic weakness. *Coincidental
correctness* is the SBFL-side problem: passing tests that execute the fault without
failing, depressing the suspiciousness of the faulty line. The divergence-side
problem is the inverse: a **failing input whose content drives heavy control-flow
activity in bug-irrelevant code**, which divergence credits and which SBFL is
immune to (that hot code is covered by ~all runs → high ep → low suspiciousness).
The two methods fail on opposite sides of the same coincidence — which is why they
are complementary, and why md4c is a *novel* limitation relative to the
coincidental-correctness literature (which studies only the SBFL side).

### 3. The coverage-conditioning negative (a bounded, pre-registered NO-GO)

We made **one** bounded, falsifiable, pre-registered attempt to elevate the
alignment theory from descriptive to predictive/fault-agnostic: condition
divergence on coverage, `cond[n] = edge_div[n] / visits[n]`, to suppress the md4c
content confound without an oracle. The pre-registration
(`docs/PHASEB_PREREG.md`, committed before scoring) fixed the signal form and three
GO conditions; all three failed (`docs/PHASEB_RESULT.md`).

| predictor | lua region-AUC | md4c region-AUC |
|---|---:|---:|
| divergence (raw) | 0.97 | 0.75 |
| **divergence ÷ coverage** | **0.55** | **0.165** |
| inverse-coverage (baseline) | 0.11 | 0.165 |

**Mechanism (the finding):** dividing by execution count penalizes the
moderately-hot, bug-co-located nodes that *are* the signal on the aligned target
(lua 0.97 → 0.55), and on md4c collapses exactly onto inverse-coverage
(0.165 ≈ 0.165). **Faults inhabit hot code as readily as confounds do**, so
coverage carries no information that separates bug-relevant from bug-irrelevant
control-flow activity. This is the **clean limit of coverage-only reweighting in
the oracle-free regime.**

**Scope of this negative (stated precisely):** this is a negative about
**coverage-based conditioning**, *not* a claim that the alignment limitation is
irremovable in general. The conditioned signal collapsed onto inverse-coverage, so
the **only axis actually exercised was coverage**. The concentration/dispersion
mechanism named in the prereg (steering perturbation budget off zero-divergence
bytes) was **not exercised here and is not being tested**. The binding constraint
on predictive elevation is **evidence breadth (n=1 aligned target)**, which a
confound-fix would not move — so the scope stays descriptive, by design.

### 4. Threats to validity / scope discipline

- **One positive.** The strong result is lua alone. sqlite and md4c are
  limitation poles — sqlite's 0.61 is the diffuse middle (above coverage, far
  below a usable localizer), not a second positive. The agentic spike is
  synthetic. No robustness claim is drawn from a count of targets.
- **No SBFL-beating claim.** Where an oracle exists (md4c), divergence is
  competitive (top 2%) but does not beat SBFL; lua's contribution is *uniqueness*
  (SBFL inapplicable), not a head-to-head win.
- **md4c is a case study (n=1).** Its role is to mark the misaligned pole and the
  coincidental-correctness dual, not to support competitiveness.
- **The agentic spike is synthetic and mechanism-level.** Generality evidence for
  the *idea*, not validation of a real-agent system.
- **Reproducibility.** lua, sqlite, md4c, and the agentic spike all regenerate
  from committed targets/seeded harnesses. sqlite's 0.61 rebuilds via
  `targets/sqlite3/{build.sh,func_eval.py}` under the committed function-level
  ground-truth rule (§Results.2).
