# PRE-REGISTRATION — Synthetic Counterfactual Failure-Attribution Spike

**Status: LOCKED before any signal-scoring run.**
**Date:** 2026-05-30
**Branch/commit:** recorded by the git commit that adds this file (timestamp precedes all Task-4 results).

This document fixes the testbed design, the fault-injection procedure, the evaluation set, the GO/NO-GO
bar, and the external-validity caveat **before** any outcome-flip or cascade-divergence number is computed.
No dimension below may be changed after seeing results. If a number disappoints, the outcome is recorded
honestly and the fallback is executed — the bar does not move.

> **Integrity timeline.** The GO bar (§5), trace/fault set (§2–§3), and signals (§4) were committed before
> any scoring. During Task-3 build, single-trace **smoke tests** (machinery verification, NOT the
> pre-registered experiment) revealed two mechanism bugs — replay silently erased injected faults, and a
> capable distractor model leaked the global answer into late steps. Both were fixed as method
> corrections: the §4 alternative-generation scope was clarified (distractors see only a step's local tool
> reading) and faults were made persistent. **The GO bar and the frozen eval set were NOT touched.** The
> pre-registered experiment (Task 4) runs on the frozen manifest, which is created and committed only
> after this point, before any manifest-level score is read.

---

## 0. Scope (locked)

The synthetic testbed serves two purposes ONLY:
1. **KILL-TEST of the cascade confound** — does outcome-flip-on-repair *separate* from the raw
   cascade-divergence null at localizing a known injected fault?
2. **Generality demonstration for the theory paper** — mechanism-level evidence that the
   counterfactual-perturbation primitive behaves as predicted beyond the C substrate.

It does **NOT** validate the real agentic application (blocked: no public replayable agent-failure
benchmark — Task-1 finding). All conclusions are mechanism-level: author-built system, author-injected
faults. See §6.

---

## 1. Testbed design (locked) — real-ish task, NOT contrived around the signal

**Task (real-ish, deterministic, checkable):** multi-hop numeric question answering over a *fixed local
structured knowledge base* (a small bundled CSV/JSON of facts — e.g. entities with numeric attributes).
Questions require lookups + arithmetic across ≥2 hops (e.g. "What is the sum of attribute A for the two
entities with the largest attribute B?"). The task is chosen because it is (a) a realistic agent
workload, (b) fully deterministic via in-process tools (NO live web → replayable), and (c) has an exact
ground-truth answer for an unambiguous outcome check. The task is **not** designed around where the
signal would succeed; it is a generic lookup+compute pipeline.

**Agents (fixed pipeline):**
1. `Planner` — decomposes the question into an ordered sub-step list.
2. `Retriever` — resolves each lookup via a deterministic `lookup(entity, field)` tool over the local KB.
3. `Calculator` — evaluates arithmetic via a deterministic `calc(expr)` tool.
4. `Reporter` — emits the final answer.

LLM calls drive the agents; **all tools are deterministic**. Replay re-runs downstream agents at
**temperature 0** for reproducibility. A "step" = one agent turn in the trace.

**Trace depth (locked — load-bearing for the kill-test):** the cascade confound only manifests when the
trace is deep enough to create a position gradient ("perturbed early → everything after diverged"). On a
~4-step single pass the candidate space is tiny, MRR goes degenerate (random-baseline MRR ≈ 0.4–0.5,
both signals saturate), and a NO-GO would be a shallow-trace artifact, not weak signal. The fractional
positions in §2 only make sense over a longish trace. Therefore: **each lookup hop and each arithmetic
operation materializes as its own agent turn** (NOT collapsed into 4 logical stages), and the testbed
must produce traces of **≥ 12 steps** (target a dozen-plus). This is a **build-time gate**: if the
realized median trace depth is < 12 steps, the testbed is redesigned (more hops per task) before any
fault injection or scoring — a shallow testbed cannot test anything and triggers neither GO nor NO-GO.

**Outcome checker (locked):** normalized exact match of the Reporter's final answer against
`ground_truth` (numeric tolerance 0 for integers; whitespace/case-normalized for strings). Binary
`success`/`fail`.

**Replay harness contract (locked):** `replay(trace, step_idx, substituted_output) -> (outcome,
downstream_steps)` re-executes every agent turn AFTER `step_idx` with the substituted output spliced in,
tools deterministic, temperature 0; returns the new outcome and the new downstream step sequence.

## 2. Fault-injection procedure (locked) — NEUTRAL, programmatic, not hand-picked

Start from **successful baseline runs** (task solved correctly, full clean trace recorded).

**Step positions (pre-fixed, neutral):** inject at normalized trace positions {0.25, 0.50, 0.75}
(early / mid / late), mapped to the nearest agent turn. Positions are fixed *a priori*, identical across
tasks; not chosen per-instance for findability.

**Fault types (pre-fixed, generic, programmatic — applied to the chosen step's output):**
- `F1 value_corruption` — replace a numeric/entity value in the step output with a wrong-but-plausible one (deterministic rule: numeric → value × 2 + 1; entity → next entity in KB order).
- `F2 content_drop` — delete a required sub-result from the step output (truncate the last clause/field).
- `F3 toolarg_corruption` — corrupt the arguments of a tool call at that step (swap two args / wrong field name).

These are structural, domain-generic corruptions defined by fixed rules. **Faults are NOT hand-selected
for whether the signal can find them.**

**Generation:** for each task, cross {3 positions} × {3 fault types}, under fixed RNG **seed = 20260530**.

**Neutral inclusion filter (locked, applied BEFORE scoring):** keep an instance only if the injected
fault actually flips the baseline outcome success→fail — i.e. it is genuinely a *decisive* error.
Instances that do not change the outcome are not failure traces and are excluded. This filter is the
definition of the task, applied uniformly; it involves no signal computation.

**Ground truth (locked):** for each retained instance, the decisive step = the injected step; the
responsible agent = the agent at that step.

## 3. Fixed evaluation set (locked by rule + seed; manifest frozen pre-scoring)

The evaluation set = **all instances surviving §2** from {N_tasks tasks} × {3 positions} × {3 fault
types} under seed 20260530. `N_tasks` is fixed at **12** a priori, targeting ~25–40 retained instances
(consistent with the plan's scale). The cross-product is fully determined by the locked design + seed,
leaving **zero post-hoc selection freedom**.

**Procedure integrity:** the concrete materialized manifest (exact instance IDs: `task_id ×
position × fault_type`, with the injected step index per instance) is generated at the END of testbed
build (Task 3) and **committed before any signal is scored** (Task 4). Both signals are then run on
**exactly** that frozen manifest. No instance is added, dropped, or reselected after any score is seen.

> **Realized set (recorded before scoring):** the locked rule yielded **107 retained instances** (of 108
> candidate; one 0.75/F2_drop case did not flip). This exceeds the rough "~25–40" expectation above because
> the injection flip-retention rate is ~100%, not the ~30–40% guessed. The RULE (12 tasks × 3 positions ×
> 3 fault types, success→fail filter, seed 20260530) was locked, not the count; 107 is its deterministic
> consequence — more statistical power, not a chosen number. Depth gate: median 13 ≥ 12 (PASS).

**Retained-set composition reporting (locked):** the frozen manifest commit MUST report the retained-set
composition as a **count table by fault position {0.25, 0.50, 0.75} × fault type {F1, F2, F3}**. The
success→fail inclusion filter (§2) is expected to be survivorship-biased — late faults may flip the
outcome less often, under-populating the 0.75 cell that drives separation (see §5). Reporting the
composition makes any imbalance visible up front rather than letting it silently shape the aggregate.

## 4. Signals (locked)

- **Primary (causal): `outcome_flip(trace, step, n_alts)`** — generate `n_alts = 5` plausible
  *alternative* outputs for the step from a capable model, replay each, score = fraction that flip
  fail→success. Rank steps descending. Predicted decisive step = argmax.
  - **Blind alternative-generation (locked — anti-oracle-leakage):** the alternative set for a step is
    the step's **locally-correct tool output** (the canonical counterfactual repair — the agent doing
    its own job, which is oracle-LIGHT, not leakage) plus capable-model **local distractors**. The
    distractor model is given ONLY the step's sub-task and its own tool reading — **not** the overall
    task, the trace, `ground_truth`, the gold final answer, or any success signal. This scoping is
    load-bearing: given the full task a capable model trivially "repairs" any late aggregation step by
    computing and emitting the globally-correct total, so EVERY downstream step would flip (the
    oracle-leakage degeneracy). Restricting distractors to local misreadings of the step's own tool
    reading makes them structurally incapable of reproducing the final answer, so only the genuinely
    faulted step's repair flips the task. A step is decisive if its locally-correct output (or a
    plausible local alternative) saves the task. Asserted in code (`signals._gen_distractors` sees only
    sub-task + tool reading) and verifiable by inspecting the prompt.
- **Confound null (cascade): `cascade_divergence(trace, step)`** — apply a *neutral* perturbation
  (paraphrase/minor edit, not a repair) to the step, replay, score = embedding distance summed over the
  downstream steps. Rank steps descending. (Predicted to rank early/high-cascade steps high regardless
  of fault.)

Both ranked over the same candidate steps per trace. Metrics vs the injected decisive step: **top-1
accuracy** and **MRR**; EXAM/rank reported secondarily. Same scoring machinery as the C eval
(`separatrix/eval/eval_metrics.py`), with MRR added.

## 5. GO / NO-GO bar (locked) — criterion is SEPARATION FROM THE CONFOUND, not beating random

Let Δ_MRR = MRR(outcome-flip) − MRR(cascade-divergence) over the frozen eval set.

**GO** requires BOTH:
- **Δ_MRR ≥ 0.20** (aggregate over the frozen eval set), AND
- a **paired one-sided Wilcoxon signed-rank test, tie-corrected** (per-instance reciprocal rank,
  outcome-flip > cascade-divergence) with **p < 0.05**. Tie-correction is mandatory because discrete
  reciprocal ranks over a small candidate set produce many ties; the naive Wilcoxon would misstate p.

**Mandatory per-position analysis (locked):** report Δ_MRR and top-1 separation **broken out by injected
fault position {0.25, 0.50, 0.75}**, not only in aggregate. Rationale: in a linear pipeline the
cascade-divergence null ranks the injected step correctly *by position-luck* for EARLY faults (early
fault = high downstream divergence = coincidentally the fault) and fails mainly for LATE faults (low
divergence rank, but flip still pinpoints it). Separation is therefore expected to be driven by the 0.75
injections; an aggregate-only number could be washed out or inflated by the retained set's position mix.
The aggregate Δ_MRR ≥ 0.20 + Wilcoxon remains the GO gate, but the per-position breakdown must be
reported alongside it so the confound is legible and a position-imbalanced retained set cannot quietly
determine the verdict.

Corroborating (reported, non-gating): top-1(outcome-flip) − top-1(cascade-divergence) ≥ 0.20; and the
cascade null exhibits its predicted bias toward early/high-cascade steps.

**NO-GO** if outcome-flip fails to separate from the cascade null by the above (Δ_MRR < 0.20 or
p ≥ 0.05) → the perturbation primitive does not beat its own cascade artifact here. **Record honestly
and execute the theory fallback** (pivot.md §Fallback). Do **not** iterate the signal on this set to
chase a pass.

## 6. External-validity caveat (locked)

Any GO is **mechanism-level evidence only**: a synthetic, author-built multi-agent system with
deterministic tools and **author-injected faults** under a fixed neutral scheme. It demonstrates that
outcome-flip separates from the cascade confound *in this controlled setting*; it does **not**
establish performance on real-world agent failures, which remains blocked on the absence of any public
replayable agent-failure benchmark (Task-1 finding). The synthetic route is justified **only** by being
cheap (see §7).

## 7. Hard time-box (locked)

If the **testbed build (Task 3) exceeds ~2 days**, **STOP and go to the theory fallback.** The synthetic
route's sole justification is low cost; a build that blows the box invalidates that justification.
