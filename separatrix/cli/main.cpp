// separatrix — structural testing framework CLI.
//
// Phase 1: `separatrix analyze <input.ll|.bc> [-o prefix]`
//   Builds the behavioral graph (-> prefix.sepgraph.json) and an instrumented
//   copy of the module (-> prefix.inst.ll). Compile prefix.inst.ll with the
//   sep runtime to produce ID traces that map back onto graph nodes.
#include <cstdio>
#include <string>
#include <system_error>

#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"

#include "separatrix/analyzer/builder.h"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: separatrix analyze <input.ll|.bc> [-o <prefix>]\n");
  return 2;
}

int cmdAnalyze(int argc, char **argv) {
  std::string input;
  std::string prefix;
  for (int i = 0; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "-o" && i + 1 < argc) {
      prefix = argv[++i];
    } else if (input.empty()) {
      input = a;
    } else {
      return usage();
    }
  }
  if (input.empty()) return usage();
  if (prefix.empty()) {
    prefix = input;
    size_t dot = prefix.find_last_of('.');
    if (dot != std::string::npos) prefix = prefix.substr(0, dot);
  }

  llvm::LLVMContext ctx;
  llvm::SMDiagnostic err;
  std::unique_ptr<llvm::Module> M = llvm::parseIRFile(input, err, ctx);
  if (!M) {
    err.print("separatrix", llvm::errs());
    return 1;
  }

  sep::BehavioralGraph g = sep::buildGraph(*M);
  std::string graphPath = prefix + ".sepgraph.json";
  g.writeJson(graphPath);

  sep::instrument(*M);
  std::string instPath = prefix + ".inst.ll";
  std::error_code ec;
  llvm::raw_fd_ostream out(instPath, ec);
  if (ec) {
    std::fprintf(stderr, "separatrix: cannot write %s: %s\n", instPath.c_str(),
                 ec.message().c_str());
    return 1;
  }
  M->print(out, nullptr);

  std::printf("analyzed %s: %zu nodes, %zu edges\n  graph: %s\n  instrumented: %s\n",
              g.module.c_str(), g.nodes.size(), g.edges.size(),
              graphPath.c_str(), instPath.c_str());
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc < 2) return usage();
  std::string cmd = argv[1];
  if (cmd == "analyze") return cmdAnalyze(argc - 2, argv + 2);
  return usage();
}
