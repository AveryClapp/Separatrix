# Task 1 — Benchmark + Replayability Feasibility (DECISION GATE)

**Date:** 2026-05-30
**Question:** Can we *replay* (counterfactually intervene on) LLM agent-execution traces to test whether
outcome-flip-on-repair localizes the decisive error step? Replay is REQUIRED for the strong form of the idea.

**Verdict: GO-synthetic.** No public benchmark gives labels + replay + outcome-check together.
Who&When supplies labels/inputs/outcome but ships **static logs, not a runnable system**.
AgenTracer/TracerTraj is not usable as a public replayable benchmark in the time box. The plan's
endorsed path therefore applies: build a minimal replayable multi-agent testbed with programmatic
fault injection at a known step (injected fault = clean ground truth).

### Scope reframe (post-approval, 2026-05-30)
The synthetic testbed's purpose is strictly:
1. **A controlled KILL-TEST of the cascade confound** — can outcome-flip-on-repair separate from the
   raw cascade-divergence null when localizing a *known* injected fault?
2. **A generality demonstration for the theory paper** — mechanism-level evidence that the
   perturbation/counterfactual primitive behaves as the theory predicts beyond the C substrate.

It is **NOT validation of the real agentic application.** That validation is *blocked* by the Task-1
finding: there is no public replayable agent-failure benchmark (Who&When is output-only static logs;
TracerTraj is unreleased/out-of-scope). Any positive synthetic result is mechanism-level only —
author-built system, author-injected faults — and must be reported with that limitation explicit.

---

## Candidate 1: Who&When (mingyin1/ag2ai `Agents_Failure_Attribution`)

Cloned to `agent_attrib_spike/whoandwhen_repo/`. **184 traces present and loadable**:
58 Hand-Crafted (Magentic-One systems) + 126 Algorithm-Generated (CaptainAgent). Source tasks: GAIA + AssistantBench.

**One trace loaded end-to-end** (`Who&When/Hand-Crafted/1.json`): dict with these fields —

| field | type | role | example |
|---|---|---|---|
| `question` | str | task input | "Where can I take martial arts classes within a 5-min walk of the NYSE…" |
| `history` | list[ {role, content} ] | **structured per-step trace** | 29 messages; roles: `human`, `Orchestrator (thought)`, `Orchestrator (-> WebSurfer)`, `WebSurfer` |
| `ground_truth` | str | correct answer (→ outcome checker) | "Renzo Gracie Jiu-Jitsu Wall Street" |
| `is_corrected` | bool | task outcome | `False` (failed) |
| `mistake_agent` | str | GT responsible agent | "WebSurfer" |
| `mistake_step` | str | GT decisive step index | "12" |
| `mistake_reason` | str | GT explanation | "WebSurfer clicks an irrelevant website and disrupts the task." |

So Who&When DOES provide: labels (who/when/why) ✓, task input ✓, structured per-step messages ✓,
ground-truth answer ✓, and a binary outcome flag ✓. This is everything an *LLM-reads-the-trace judge*
needs — and that is exactly (and only) what the shipped code does.

### Why it is NOT replayable (the decisive finding)
1. **No orchestration/runner is shipped.** The only Python in the repo is the attribution *judge*:
   `Automated_FA/{inference.py, evaluate.py, Lib/utils.py, Lib/local_model.py}`. There is no agent
   system, no agent system-prompts, no tool definitions, no handoff/control logic — nothing to
   re-execute the trace from a substituted step.
2. **The agents take live, non-deterministic actions.** Hand-Crafted traces are Magentic-One with a
   `WebSurfer` browsing the *live web* on GAIA tasks. Re-running step k depends on the web as it was at
   annotation time; it is neither reproducible nor deterministic now.
3. **Per-step executable context is not captured.** `history` stores rendered text turns, not the tool
   state (browser DOM, file state, intermediate API results) an agent would need to actually continue.

This confirms the 2026 critique flagged in the plan ("Who&When is partly output-only — constrains replay").
Both spike signals (outcome-flip AND the cascade-divergence null) require replay, so static logs are
insufficient for the core experiment. Who&When remains useful only as (a) an external reference for the
published *judge* baseline (~14% step-level) and (b) a possible later external-validity check.

## Candidate 2: AgenTracer / TracerTraj (arXiv 2509.03312)

Built TracerTraj-2.5K via counterfactual replay + programmatic fault injection — i.e. replayable by
construction. But as of this investigation it is **not usable as a public replayable benchmark**:
- No dataset on HuggingFace (`datasets?search=TracerTraj` / `AgenTracer` → 0 results); no usable
  public GitHub repo surfaced (project page `bingreeky.github.io/atracer`, no released replay harness/dataset confirmed).
- It is a **competitor's training corpus for a trained tracer (AgenTracer-8B)** — and "training a tracer
  model" is explicitly **out of scope** for this spike. Even if released, standing up their injection
  harness + frameworks (MetaGPT/MaAS) is not a time-box-friendly path to *our* training-free signal.

---

## Classification → GO-synthetic

- **GO-replayable?** No — no public benchmark provides labels + replay + outcome-check together.
- **GO-synthetic?** **Yes (selected).** A minimal replayable testbed is buildable in ~1–2 days:
  2–3 agents, deterministic in-process tools (NO live web), a handful of tasks with a programmatic
  success checker, and fault injection at a *known* step. The injected step = clean ground truth
  (the lua-synthetic analogue). Honest caveat to carry forward: results are on a synthetic system; the
  cascade confound must still be controlled exactly as pre-registered, and external validity is limited
  until/unless a replayable real benchmark appears.
- **NO-GO?** Not warranted — the synthetic path is clearly feasible.

## Verify checklist (Task 1)
- [x] Written feasibility note (this file).
- [x] Replayability verdict: **GO-synthetic**, with the specific replay-relevant fields enumerated.
- [x] One trace loaded end-to-end (`Hand-Crafted/1.json`, 29 steps, outcome+labels parsed).
- [~] Re-executed to reproduce failure: **N/A by finding** — the trace is not replayable (no runner,
  live-web actions, no executable per-step context). Non-replayability *is* the gate result; this is
  what selects GO-synthetic over GO-replayable.

## Next (await go-ahead — do not build yet)
Per plan: **STOP and report** before building anything. If approved, Task 2 = pre-register the
experiment (`PREREGISTRATION.md`: fixed trace/task set, signals, numeric GO bar + confound-separation
margin) *before* any scoring run, then Task 3 builds the synthetic replay harness.
