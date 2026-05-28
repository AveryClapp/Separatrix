#!/usr/bin/env bash
# Phase-1 end-to-end check on a single C target.
#   phase1_e2e.sh <target.c> <harness.c> "<input args>"
# Emits IR (-g), analyzes, builds instrumented binary, runs, verifies the gate,
# and checks node-ID determinism across a second analyze.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEP="$ROOT/build/separatrix"
RT="$ROOT/separatrix/runtime/sep_rt.c"
VERIFY="$ROOT/separatrix/test/verify_phase1.py"

TARGET="$1"; HARNESS="$2"; ARGS="${3:-}"
WORK="$(dirname "$TARGET")"
base="$(basename "${TARGET%.c}")"
ll="$WORK/$base.ll"

clang -g -O0 -S -emit-llvm "$TARGET" -o "$ll"
"$SEP" analyze "$ll" -o "$WORK/$base"
clang -g -O0 "$WORK/$base.inst.ll" "$HARNESS" "$RT" -o "$WORK/${base}_inst" -lm
SEP_TRACE="$WORK/$base.trace" "$WORK/${base}_inst" $ARGS >/dev/null

python3 "$VERIFY" "$WORK/$base.sepgraph.json" "$WORK/$base.trace" "$WORK"

# Determinism: a second analyze must produce byte-identical graph IDs.
"$SEP" analyze "$ll" -o "$WORK/${base}__b" >/dev/null
if diff -q "$WORK/$base.sepgraph.json" "$WORK/${base}__b.sepgraph.json" >/dev/null; then
  echo "  [PASS] node-ID determinism        graph identical across rebuilds"
else
  echo "  [FAIL] node-ID determinism        graph differs across rebuilds"; exit 1
fi
rm -f "$WORK/${base}__b.sepgraph.json" "$WORK/${base}__b.inst.ll"
