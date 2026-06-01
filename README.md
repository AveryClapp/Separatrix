# Separatrix

A structural testing framework that scores where code is fragile by measuring how much small input perturbations make control flow diverge.

Most testing tools ask "did we execute this code?" Separatrix asks "where does this system amplify small changes into large failures?" It instruments your codebase, generates perturbations, and ranks every function and basic block by how often those perturbations push execution down a different path than baseline.

## The core idea

Coverage frequency tells you what ran. Divergence localization tells you what *bends* under pressure.

For each code region, Separatrix scores how much a perturbed corpus shifts its outgoing-edge profile away from baseline. Regions with high divergence scores are the sensitive joints in your code: places where small input changes cascade into different behavior. On Magma fault benchmarks this signal predicts real bug locations better than coverage frequency, and works in cases where spectrum-based fault localization (SBFL) is inapplicable because bugs never surface in observable output.

## Results

Three Magma targets, evaluated as an alignment continuum:

| Target | Divergence AUC | Coverage AUC | Note |
|---|---|---|---|
| lua (LUA001-004) | **0.97** | 0.89 | SBFL inapplicable; bug-blind corpus; trajectory signal wins |
| sqlite3 | **0.61** | 0.47 (below chance) | Diffuse pole: weak corpus-fault coupling, divergence still above chance |
| md4c | top 2% (29/1433 nodes) | n/a | Misaligned pole: input variation concentrates off the fault, matches SBFL rank but doesn't beat it |

The three targets are an ordered axis, not an N-program average. Divergence localization works to the degree the input variation axis overlaps the fault. lua's perturbations bifurcate at faulted debug logic; sqlite's couple only weakly; md4c's pile onto a content-driven hot loop unrelated to the bug. The failure mode is named, not hidden.

## Architecture

```
separatrix/
├── analyzer/    # LLVM pass: builds behavioral graph from IR
├── engine/      # Chaos engine: generates perturbations from graph
├── detector/    # Divergence detector: runs perturbations, scores sensitivity
├── ir/          # Behavioral graph IR: language-agnostic representation
└── cli/         # Entry point: analyze and run commands
```

## Building

Requires LLVM 17+ and CMake.

```bash
git clone https://github.com/AveryClapp/Separatrix
cd Separatrix
cmake -B build -DLLVM_DIR=/path/to/llvm/lib/cmake/llvm
cmake --build build
```

## Usage

```bash
# Instrument a target and build its behavioral graph
separatrix analyze ./your_project

# Run perturbation campaign and generate sensitivity map
separatrix run ./your_project
```

## Status

Research prototype. C/C++ targets via LLVM instrumentation. Validated on Magma libraries.

---

*Named for the set of points in a dynamical system from which small perturbations push trajectories apart: exactly what the tool scores.*
