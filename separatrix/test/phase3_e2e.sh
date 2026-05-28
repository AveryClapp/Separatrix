#!/usr/bin/env bash
# Phase-3 end-to-end: build the instrumented target, run the structural-
# targeting ablation across seeds, and verify the gate (guided > random).
#   phase3_e2e.sh <target.c> <harness.c> [budget]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEP="$ROOT/build/separatrix"; RT="$ROOT/separatrix/runtime/sep_rt.c"
ABLATE="$ROOT/separatrix/cli/sep_ablate.py"; VERIFY="$ROOT/separatrix/test/verify_phase3.py"

TARGET="$1"; HARNESS="$2"; BUDGET="${3:-120}"
WORK="$(dirname "$TARGET")"; base="$(basename "${TARGET%.c}")"

clang -g -O0 -S -emit-llvm "$TARGET" -o "$WORK/$base.ll"
"$SEP" analyze "$WORK/$base.ll" -o "$WORK/$base" >/dev/null
clang -g -O0 "$WORK/$base.inst.ll" "$HARNESS" "$RT" -o "$WORK/${base}_inst" -lm

python3 "$ABLATE" --bin "$WORK/${base}_inst" --graph "$WORK/$base.sepgraph.json" \
        --budget "$BUDGET" -o "$WORK/$base.ablation.json"
echo
python3 "$VERIFY" "$WORK/$base.ablation.json"

# Determinism: a second ablation must produce identical results.
python3 "$ABLATE" --bin "$WORK/${base}_inst" --graph "$WORK/$base.sepgraph.json" \
        --budget "$BUDGET" -o "$WORK/${base}__b.ablation.json" >/dev/null
if diff -q "$WORK/$base.ablation.json" "$WORK/${base}__b.ablation.json" >/dev/null; then
  echo "  [PASS] ablation determinism     identical across runs"
else
  echo "  [FAIL] ablation determinism     differs across runs"; exit 1
fi
rm -f "$WORK/${base}__b.ablation.json"
