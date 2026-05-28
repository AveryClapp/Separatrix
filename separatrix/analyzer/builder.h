// Behavioral-graph construction + instrumentation over an LLVM module.
//
// buildGraph and instrument number basic blocks via the SAME deterministic
// traversal, so the IDs the instrumenter emits into the runtime trace are the
// IDs of the graph nodes — no symbolization needed to align them.
#pragma once

#include "separatrix/ir/graph.h"

namespace llvm {
class Module;
}

namespace sep {

// Build the behavioral graph (read-only) from a module.
BehavioralGraph buildGraph(llvm::Module &M);

// Insert a call to `void __sep_trace_block(i32 id)` at the entry of every basic
// block. IDs match buildGraph. Mutates the module in place.
void instrument(llvm::Module &M);

}  // namespace sep
