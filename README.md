# Separatrix

A structural testing framework that finds where your code is fragile.

Most testing tools ask *did we execute this code?* Separatrix asks *where does this system amplify small changes into large failures?* It builds a structural model of your codebase, identifies the regions most sensitive to perturbation, and attacks them.

## How it works

1. **Analyze** — a static pass builds a behavioral graph of your code: call structure, data flow, branch boundaries, implicit invariants
2. **Perturb** — targeted mutations are generated at high-sensitivity regions, not random fuzzing
3. **Score** — outputs a sensitivity map of your codebase, every component ranked by how much it amplifies small changes

## Status

Early development. C++ only for now, via LLVM instrumentation.

## Building

```bash
git clone https://github.com/AveryClapp/separatrix
cd separatrix
cmake -B build && cmake --build build
```

## Usage

```bash
separatrix analyze ./your_project
separatrix run ./your_project
```

## Motivation

Coverage tells you what ran. Separatrix tells you what breaks.

---

*Named after the boundary curve in dynamical systems that separates regions of qualitatively different behavior.*
