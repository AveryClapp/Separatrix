# Agentic Failure-Attribution Spike

Time-boxed falsification spike: does counterfactual perturbation of agent-execution
traces localize the **decisive error step**, via a *causal* signal rather than an
autoregressive-cascade artifact? See `../docs/plans/pivot.md` for the full plan and
`PREREGISTRATION.md` for the locked experiment.

**Task-1 verdict:** GO-synthetic (no public replayable agent-failure benchmark;
Who&When is output-only static logs). See `TASK1_FEASIBILITY.md`.

## Scope (honest)

This is a **controlled kill-test of the cascade confound** and a generality
demonstration for the theory paper — NOT validation of the real agentic
application (blocked by the Task-1 finding). Evidence is mechanism-level:
synthetic system, author-injected faults.

## Components

| file | role |
|---|---|
| `llm.py` | OpenAI access + on-disk cache (cache → deterministic temp-0 replay) |
| `testbed.py` | synthetic 4-role pipeline over a fictional KB; sequential-fold task |
| `faults.py` | neutral programmatic fault injection (F1/F2/F3 × positions) + inclusion filter |
| `replay.py` | fault-aware counterfactual replay (recompute downstream; faults persist) |
| `signals.py` | `outcome_flip` (causal) and `cascade_divergence` (confound null) |
| `score.py` | tie-fair rank/MRR/EXAM/top-1 + separation + GO decision (TDD'd) |
| `test_score.py` | hand-computed unit tests for `score.py` |

Run tests: `./.venv/bin/python test_score.py`

## Design choices that make it a valid kill-test

- **Fictional KB.** Made-up entities/numbers so agents can't shortcut a lookup
  from prior knowledge or silently repair a corrupted value from memory.
- **Sequential fold, not a tree.** `running = running OP lookup`, one lookup turn
  and one calc turn per hop. This gives *dependency depth* (≥12 steps where
  perturbing step k propagates through every later step) — without it the cascade
  position-gradient does not exist and the confound is vacuous.
- **Two channels per step.** Deterministic `value` (outcome flows through it →
  API-free, reproducible replay) and an LLM `output` narration (what divergence
  embeds).
- **Faults persist through replay.** A fault is a standing miscomputation tagged
  on its step and re-applied whenever that step is recomputed, so it survives
  replay unless that exact step is repaired. (Earlier bug: recomputing a faulted
  step from its refs silently erased the fault, causing spurious flips.)
- **Blind, locally-scoped alternative-generation.** Distractors come from a
  capable model shown ONLY the step's sub-task + its own tool reading — never the
  overall task/answer. The causal signal is the locally-correct repair. This
  prevents the oracle-leakage degeneracy where a capable model "repairs" any late
  aggregation step by emitting the globally-correct total.

## Honest caveat on fault types (referenced by PREREGISTRATION.md §2)

In this numeric testbed all three pre-registered fault types manifest as a
corrupted scalar via three DISTINCT deterministic mechanisms — `F1_value`
(scaling: `v·2+1`), `F2_drop` (dropped sub-result → 0), `F3_toolarg` (additive
skew: `v + max(1, v//2)`). They are generic and not hand-picked for findability,
but they are not deep semantic faults; the spike's claim is mechanism-level
separation of the causal signal from the cascade confound, not fault realism.
