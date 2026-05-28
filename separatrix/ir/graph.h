// Behavioral graph — language-agnostic representation of a program's structure.
//
// Nodes are basic blocks (the finest control-flow unit); edges are control-flow
// successors and call relationships. Node IDs are assigned deterministically by
// module traversal order so that (a) they are stable across rebuilds of the same
// source and (b) the instrumenter and the graph builder agree on them by
// construction — which is what lets a runtime trace of IDs map back onto graph
// nodes and their source locations without PC symbolization.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace sep {

enum class EdgeKind { Cfg, Call };

// One basic block.
struct Node {
  uint32_t id = 0;
  std::string function;          // enclosing function name
  uint32_t block_index = 0;      // index of this block within its function
  std::string file;              // source file from DebugLoc (empty if no -g)
  unsigned line = 0;             // source line from DebugLoc (0 if unknown)
  std::string terminator;        // terminator opcode (br, switch, ret, ...)
  std::string branch_cond;       // textual condition for conditional branches
  std::vector<uint32_t> succ;    // CFG successor node IDs
  std::vector<std::string> call_names;  // callees invoked in this block
};

struct Edge {
  uint32_t from = 0;
  uint32_t to = 0;
  EdgeKind kind = EdgeKind::Cfg;
};

struct BehavioralGraph {
  std::string module;
  std::vector<Node> nodes;
  std::vector<Edge> edges;

  // Serialize to JSON (hand-rolled; no external dependency).
  void writeJson(const std::string &path) const;
};

}  // namespace sep
