#!/usr/bin/env bash
# Phase-4 end-to-end: build the instrumented lua Magma target, run the
# predictive-validity evaluation, and verify the gate (trajectory sensitivity
# beats random and coverage as a bug-location predictor).
#
#   phase4_e2e.sh <magma_repo> [work_dir] [seed_file] [max_pert]
#
# Set REBUILD=1 to force a clean rebuild of the target.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LUA="$ROOT/separatrix/eval/targets/lua"
EVAL="$ROOT/separatrix/cli/sep_eval.py"
VERIFY="$ROOT/separatrix/test/verify_phase4.py"

MAGMA="${1:?usage: phase4_e2e.sh <magma_repo> [work_dir] [seed] [corpus_n]}"
WORK="${2:-$ROOT/spike/lua_port}"
SEED="${3:-$LUA/seeds/debug.lua}"
CORPUS_N="${4:-250}"
CORPUS="$WORK/corpus"

if [ "${REBUILD:-0}" = "1" ] || [ ! -x "$WORK/lua_inst" ]; then
  bash "$LUA/build.sh" "$MAGMA" "$WORK"
fi
if [ "${REBUILD:-0}" = "1" ] || [ ! -d "$CORPUS" ]; then
  python3 "$LUA/gen_corpus.py" "$CORPUS" "$CORPUS_N"
fi

python3 "$EVAL" --bin "$WORK/lua_inst" --graph "$WORK/lua_core.sepgraph.json" \
        --bugs "$WORK/bugs.json" --seed-file "$SEED" --corpus "$CORPUS" \
        -o "$WORK/lua_core.eval.json"
echo
python3 "$VERIFY" "$WORK/lua_core.eval.json"

# Determinism: a second eval must produce an identical map.
python3 "$EVAL" --bin "$WORK/lua_inst" --graph "$WORK/lua_core.sepgraph.json" \
        --bugs "$WORK/bugs.json" --seed-file "$SEED" --corpus "$CORPUS" \
        -o "$WORK/lua_core__b.eval.json" >/dev/null
if diff -q "$WORK/lua_core.eval.json" "$WORK/lua_core__b.eval.json" >/dev/null; then
  echo "  [PASS] eval determinism        identical across runs"
else
  echo "  [FAIL] eval determinism        differs across runs"; exit 1
fi
rm -f "$WORK/lua_core__b.eval.json"
