#!/usr/bin/env bash
# Phase-2 end-to-end check on a C target.
#   phase2_e2e.sh <target.c> <harness.c> "<seed input>"
# Builds the instrumented binary (via Phase-1 path), runs the sensitivity
# campaign, verifies the map gate, checks campaign determinism (same seed ->
# identical map), and reports a coarse instrumentation-overhead figure.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SEP="$ROOT/build/separatrix"
RT="$ROOT/separatrix/runtime/sep_rt.c"
RUN="$ROOT/separatrix/cli/sep_run.py"
VERIFY="$ROOT/separatrix/test/verify_phase2.py"

TARGET="$1"; HARNESS="$2"; SEED="$3"
WORK="$(dirname "$TARGET")"
base="$(basename "${TARGET%.c}")"

# Instrumented + native binaries from the same IR.
clang -g -O0 -S -emit-llvm "$TARGET" -o "$WORK/$base.ll"
"$SEP" analyze "$WORK/$base.ll" -o "$WORK/$base" >/dev/null
clang -g -O0 "$WORK/$base.inst.ll" "$HARNESS" "$RT" -o "$WORK/${base}_inst" -lm
clang -g -O0 "$WORK/$base.ll" "$HARNESS" -o "$WORK/${base}_native" -lm

python3 "$RUN" --bin "$WORK/${base}_inst" --graph "$WORK/$base.sepgraph.json" \
        --seed "$SEED" -o "$WORK/$base.sepmap.json"
echo
python3 "$VERIFY" "$WORK/$base.sepmap.json" "$WORK/$base.sepgraph.json"

# Determinism: a second campaign must produce an identical map.
python3 "$RUN" --bin "$WORK/${base}_inst" --graph "$WORK/$base.sepgraph.json" \
        --seed "$SEED" -o "$WORK/${base}__b.sepmap.json" >/dev/null
if diff -q "$WORK/$base.sepmap.json" "$WORK/${base}__b.sepmap.json" >/dev/null; then
  echo "  [PASS] campaign determinism      identical map across runs"
else
  echo "  [FAIL] campaign determinism      map differs across runs"; exit 1
fi
rm -f "$WORK/${base}__b.sepmap.json"

# Coarse instrumentation overhead (re-exec dominated; indicative only).
N=200
t_n=$( { /usr/bin/time -p bash -c "for i in \$(seq $N); do '$WORK/${base}_native' '$SEED' >/dev/null; done"; } 2>&1 | awk '/real/{print $2}')
t_i=$( { SEP_TRACE=/dev/null /usr/bin/time -p bash -c "for i in \$(seq $N); do SEP_TRACE=/tmp/sep_ov '$WORK/${base}_inst' '$SEED' >/dev/null; done"; } 2>&1 | awk '/real/{print $2}')
echo "  [INFO] coarse overhead           native ${t_n}s vs instrumented ${t_i}s over $N runs (exec-dominated)"
