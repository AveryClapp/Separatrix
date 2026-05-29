# Separatrix

A structural testing framework that finds where your code is fragile.

Most testing tools ask *did we execute this code?* Separatrix asks *where does this system amplify small changes into large failures?* It builds a structural model of your codebase, identifies the regions most sensitive to perturbation, and attacks them.

## How it works

1. **Analyze** — a static pass builds a behavioral graph of your code: call structure, control flow, branch boundaries, source locations
2. **Perturb** — perturbation budget is *concentrated* where it produces divergence (steered off input bytes that change nothing), rather than spent uniformly at random
3. **Score** — outputs a sensitivity map: every node ranked by **how much perturbation makes its control flow diverge** from baseline (divergence localization), which on a Magma library predicts real bug locations better than coverage frequency

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

*Named for the set of points in a dynamical system from which small perturbations push trajectories apart — which is exactly what the tool scores: the nodes where a tiny input change makes execution diverge.*
