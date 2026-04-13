# CLAUDE.md — Separatrix

## What this is

Separatrix is a structural testing framework for C++ codebases. It uses LLVM instrumentation to build a behavioral graph of a program, identifies high-sensitivity regions via static and dynamic analysis, generates targeted perturbations at those regions, and scores each component by how much it amplifies small changes.

The goal is a sensitivity map — not a coverage report.

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

- **Behavioral graph** — nodes are functions, edges are call/data relationships, annotated with branch conditions and inferred invariants
- **Sensitivity score** — for input X and perturbation X+ε, how far apart are the outputs relative to the size of the perturbation
- **Sensitivity map** — full codebase scored, high-sensitivity regions flagged for inspection
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
