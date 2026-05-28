#!/usr/bin/env bash
# Build+run smoke test for the canary trigger plumbing.
#
#   test_canary_trigger.sh [magma_repo] [work_dir] [seed_file]
#
# Asserts the instrumented target still emits its S<status> digest line and that
# the canary writes the $MAGMA_TRIGGERS file. The file MAY be empty — whether any
# canary actually fires on this seed is Task 2's question, not a test failure.
# Set REBUILD=1 to force a clean rebuild. Exits nonzero only on build/exec error.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LUA="$ROOT/separatrix/eval/targets/lua"

MAGMA="${1:-$ROOT/spike/magma}"
WORK="${2:-$ROOT/spike/lua_port}"
SEED="${3:-$LUA/seeds/debug.lua}"

if [ "${REBUILD:-0}" = "1" ] || [ ! -x "$WORK/lua_inst" ]; then
  bash "$LUA/build.sh" "$MAGMA" "$WORK"
fi

TRIG="$WORK/.trig"
: > "$TRIG"
out="$(MAGMA_TRIGGERS="$TRIG" SEP_TRACE="$WORK/.trace" "$WORK/lua_inst" "$SEED")"

if ! grep -q '^S' <<<"$out"; then
  echo "  [FAIL] digest line               missing S<status> (got: ${out:-<empty>})"; exit 1
fi
echo "  [PASS] digest line               $(grep -m1 '^S' <<<"$out")"

if [ ! -f "$TRIG" ]; then
  echo "  [FAIL] trigger file              \$MAGMA_TRIGGERS not created"; exit 1
fi
n="$(wc -l < "$TRIG" | tr -d ' ')"
echo "  [PASS] trigger file              created ($n trigger line(s))"
