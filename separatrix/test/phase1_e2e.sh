#!/usr/bin/env bash
# Phase-1 end-to-end check on a single C or C++ target.
#   phase1_e2e.sh <target.c|.cpp> [harness.c] "<input args>"
# C target:   pass a separate harness.c providing main().
# C++ target: omit harness (the target TU is its own main); pass args as $2.
# Emits IR (-g), analyzes, builds the instrumented binary, runs, verifies the
# gate, and checks node-ID determinism across a second analyze.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEP="$ROOT/build/separatrix"
RT="$ROOT/separatrix/runtime/sep_rt.c"
VERIFY="$ROOT/separatrix/test/verify_phase1.py"

TARGET="$1"
case "$TARGET" in
  *.cpp|*.cc|*.cxx) CXX=1; HARNESS=""; ARGS="${2:-}";;
  *)                CXX=0; HARNESS="$2"; ARGS="${3:-}";;
esac
WORK="$(dirname "$TARGET")"
base="$(basename "$TARGET")"; base="${base%.*}"
ll="$WORK/$base.ll"

if [ "$CXX" = 1 ]; then
  clang++ -g -O0 -std=c++17 -S -emit-llvm "$TARGET" -o "$ll"
  "$SEP" analyze "$ll" -o "$WORK/$base"
  clang -g -O0 -c "$RT" -o "$WORK/$base.rt.o"
  clang++ -g -O0 "$WORK/$base.inst.ll" "$WORK/$base.rt.o" -o "$WORK/${base}_inst"
else
  clang -g -O0 -S -emit-llvm "$TARGET" -o "$ll"
  "$SEP" analyze "$ll" -o "$WORK/$base"
  clang -g -O0 "$WORK/$base.inst.ll" "$HARNESS" "$RT" -o "$WORK/${base}_inst" -lm
fi
SEP_TRACE="$WORK/$base.trace" "$WORK/${base}_inst" $ARGS >/dev/null

python3 "$VERIFY" "$WORK/$base.sepgraph.json" "$WORK/$base.trace" "$WORK"

# Determinism: a second analyze must produce a byte-identical graph.
"$SEP" analyze "$ll" -o "$WORK/${base}__b" >/dev/null
if diff -q "$WORK/$base.sepgraph.json" "$WORK/${base}__b.sepgraph.json" >/dev/null; then
  echo "  [PASS] node-ID determinism        graph identical across rebuilds"
else
  echo "  [FAIL] node-ID determinism        graph differs across rebuilds"; exit 1
fi
rm -f "$WORK/${base}__b.sepgraph.json" "$WORK/${base}__b.inst.ll"
