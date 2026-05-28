#include "separatrix/analyzer/builder.h"

#include <unordered_map>

#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/DebugLoc.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/Support/raw_ostream.h"

namespace sep {

namespace {

// Deterministic block ordering: functions in module order, blocks in function
// order. Index in this vector IS the node ID. Both buildGraph and instrument
// use this identical traversal, guaranteeing matching IDs.
std::vector<llvm::BasicBlock *> orderedBlocks(llvm::Module &M) {
  std::vector<llvm::BasicBlock *> blocks;
  for (llvm::Function &F : M) {
    if (F.isDeclaration()) continue;
    for (llvm::BasicBlock &BB : F) blocks.push_back(&BB);
  }
  return blocks;
}

std::string valueToString(const llvm::Value *V) {
  std::string s;
  llvm::raw_string_ostream os(s);
  V->print(os);
  os.flush();
  // Trim leading whitespace LLVM emits for inlined value printing.
  size_t start = s.find_first_not_of(" \t");
  return start == std::string::npos ? s : s.substr(start);
}

}  // namespace

BehavioralGraph buildGraph(llvm::Module &M) {
  BehavioralGraph g;
  g.module = M.getName().str();

  std::vector<llvm::BasicBlock *> blocks = orderedBlocks(M);
  std::unordered_map<const llvm::BasicBlock *, uint32_t> id;
  id.reserve(blocks.size());
  for (uint32_t i = 0; i < blocks.size(); ++i) id[blocks[i]] = i;

  // Per-function running block index.
  std::unordered_map<const llvm::Function *, uint32_t> fnBlockIdx;

  g.nodes.reserve(blocks.size());
  for (uint32_t i = 0; i < blocks.size(); ++i) {
    llvm::BasicBlock *BB = blocks[i];
    const llvm::Function *F = BB->getParent();

    Node n;
    n.id = i;
    n.function = F->getName().str();
    n.block_index = fnBlockIdx[F]++;

    // Source location: first instruction carrying a DebugLoc.
    for (const llvm::Instruction &I : *BB) {
      if (const llvm::DebugLoc &dl = I.getDebugLoc()) {
        n.line = dl.getLine();
        if (llvm::DILocation *loc = dl.get())
          n.file = loc->getFilename().str();
        break;
      }
    }

    const llvm::Instruction *TI = BB->getTerminator();
    if (TI) {
      n.terminator = TI->getOpcodeName();
      if (const auto *BR = llvm::dyn_cast<llvm::BranchInst>(TI)) {
        if (BR->isConditional())
          n.branch_cond = valueToString(BR->getCondition());
      } else if (const auto *SW = llvm::dyn_cast<llvm::SwitchInst>(TI)) {
        n.branch_cond = valueToString(SW->getCondition());
      }
      for (unsigned s = 0; s < TI->getNumSuccessors(); ++s) {
        auto it = id.find(TI->getSuccessor(s));
        if (it != id.end()) {
          n.succ.push_back(it->second);
          g.edges.push_back({i, it->second, EdgeKind::Cfg});
        }
      }
    }

    // Call edges.
    for (const llvm::Instruction &I : *BB) {
      const auto *CB = llvm::dyn_cast<llvm::CallBase>(&I);
      if (!CB) continue;
      const llvm::Function *callee = CB->getCalledFunction();
      if (!callee) {
        n.call_names.push_back("<indirect>");
        continue;
      }
      n.call_names.push_back(callee->getName().str());
      if (!callee->isDeclaration() && !callee->empty()) {
        auto it = id.find(&callee->getEntryBlock());
        if (it != id.end()) g.edges.push_back({i, it->second, EdgeKind::Call});
      }
    }

    g.nodes.push_back(std::move(n));
  }
  return g;
}

void instrument(llvm::Module &M) {
  llvm::LLVMContext &ctx = M.getContext();
  llvm::Type *voidTy = llvm::Type::getVoidTy(ctx);
  llvm::Type *i32Ty = llvm::Type::getInt32Ty(ctx);
  llvm::FunctionCallee traceFn =
      M.getOrInsertFunction("__sep_trace_block",
                            llvm::FunctionType::get(voidTy, {i32Ty}, false));

  std::vector<llvm::BasicBlock *> blocks = orderedBlocks(M);
  for (uint32_t i = 0; i < blocks.size(); ++i) {
    llvm::BasicBlock *BB = blocks[i];
    llvm::IRBuilder<> b(&*BB->getFirstInsertionPt());
    b.CreateCall(traceFn, {llvm::ConstantInt::get(i32Ty, i)});
  }
}

}  // namespace sep
