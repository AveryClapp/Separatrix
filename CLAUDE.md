# CLAUDE.md — Separatrix

## What this is

Separatrix is a structural testing framework for C/C++ codebases. It uses LLVM instrumentation to record execution trajectories over a behavioral graph, perturbs program inputs, and scores each node by **how much those perturbations make its control flow diverge from baseline** — *divergence localization*. The evidence-supported contribution: this score predicts real fault locations better than coverage.

On a Magma library (lua, LUA001–004) divergence localization ranks bug-containing regions at ROC-AUC **0.93**, vs coverage frequency **0.81**, and vs value-space output distance attributed through the *same* localization **0.81** (so the win is in the trajectory signal, not the attribution mechanism). The head-to-head against spectrum-based fault localization (SBFL) is the *multi-library* comparison: SBFL needs a per-run pass/fail oracle, which lua's debug-subsystem bugs don't manifest in observable output — so lua shows divergence localization works where SBFL is *inapplicable* (uniqueness), and oracle-bearing targets provide the SBFL head-to-head (competitiveness).

The goal is a sensitivity map — **the set of points where small perturbations push trajectories apart** — not a coverage report.

> Secondary refinement (Phase-3 partial negative): a static structural prior (branch density, etc.) was expected to steer perturbation budget, but ablation found the active mechanism is *divergence-aware concentration* (steering off zero-divergence input bytes); the static prior adds only ~1.08×. The prior is a refinement, not the load-bearing signal.

## Architecture

```
separatrix/
├── analyzer/       # LLVM pass — builds behavioral graph from IR
├── engine/         # Chaos engine — generates perturbations from graph
├── detector/       # Divergence detector — runs perturbations, scores sensitivity
├── ir/             # Internal representation — language-agnostic behavioral graph
└── cli/            # Entry point — analyze and run commands
```

## Core concepts

- **Behavioral graph** — nodes are functions/basic blocks, edges are call/control-flow relationships, annotated with branch conditions and source locations
- **Divergence localization** — for input X and perturbation X+ε, credit *every* node whose outgoing-edge profile diverges from baseline (the per-node form of the trajectory-divergence metric), not just the first node where trajectories split (first-bifurcation, which fails on staged targets — AUC ~0.50)
- **Sensitivity map** — full codebase scored by divergence localization: the set of points where small perturbations push trajectories apart, high-divergence regions flagged for inspection
- **Perturbation types** — boundary values, dependency injection failures, resource exhaustion, invariant violations, concurrency interleavings

## Build system

CMake. Requires LLVM 17+.

```bash
cmake -B build -DLLVM_DIR=/path/to/llvm/lib/cmake/llvm
cmake --build build
```

## Code style

- C++20
- No exceptions in core analysis paths
- Prefer explicit over clever
- Every public API documented with intent, not just signature

## What to avoid

- Do not add language frontends until the C++ pipeline is end-to-end and validated
- Do not generalize the IR prematurely — let the C++ implementation drive its shape
- Do not conflate coverage with sensitivity — they measure different things and the distinction matters
