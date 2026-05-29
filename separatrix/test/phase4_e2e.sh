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
PROBE="$ROOT/separatrix/test/probe_triggers.py"

MAGMA="${1:?usage: phase4_e2e.sh <magma_repo> [work_dir] [seed] [corpus_n]}"
WORK="${2:-$ROOT/spike/lua_port}"
SEED="${3:-$LUA/seeds/debug.lua}"
CORPUS_N="${4:-250}"
CORPUS="$WORK/corpus"
# SBFL fail-oracle. lua defaults to 'none' (SBFL N/A — neither standard oracle is
# valid here; see PHASE4_FINDINGS). A multi-library target with an output-
# manifesting bug runs FAIL_ORACLE=differential to activate the G3 SBFL gate.
FAIL_ORACLE="${FAIL_ORACLE:-none}"
[ "$FAIL_ORACLE" = "differential" ] && export BUILD_FIXED=1

if [ "${REBUILD:-0}" = "1" ] || [ ! -x "$WORK/lua_inst" ]; then
  bash "$LUA/build.sh" "$MAGMA" "$WORK"
fi
if [ "${REBUILD:-0}" = "1" ] || [ ! -d "$CORPUS" ]; then
  python3 "$LUA/gen_corpus.py" "$CORPUS" "$CORPUS_N"
fi

# Trigger-feasibility probe — characterises reach-vs-trigger per bug (informational;
# its nonzero exit on a degenerate/nondeterministic signal must not fail the e2e).
echo "== trigger-feasibility probe (informational) =="
python3 "$PROBE" --bin "$WORK/lua_inst" --bugs "$WORK/bugs.json" \
        --corpus "$CORPUS" --seed-file "$SEED" || true
echo

ORACLE_ARGS=(--fail-oracle "$FAIL_ORACLE")
[ "$FAIL_ORACLE" = "differential" ] && ORACLE_ARGS+=(--fixed-bin "$WORK/lua_fixed")

python3 "$EVAL" --bin "$WORK/lua_inst" --graph "$WORK/lua_core.sepgraph.json" \
        --bugs "$WORK/bugs.json" --seed-file "$SEED" --corpus "$CORPUS" \
        "${ORACLE_ARGS[@]}" -o "$WORK/lua_core.eval.json"
echo
python3 "$VERIFY" "$WORK/lua_core.eval.json"

# Determinism: a second eval must produce an identical map. (Holds for oracle=none
# and differential; the trigger oracle is intentionally nondeterministic.)
python3 "$EVAL" --bin "$WORK/lua_inst" --graph "$WORK/lua_core.sepgraph.json" \
        --bugs "$WORK/bugs.json" --seed-file "$SEED" --corpus "$CORPUS" \
        "${ORACLE_ARGS[@]}" -o "$WORK/lua_core__b.eval.json" >/dev/null
if diff -q "$WORK/lua_core.eval.json" "$WORK/lua_core__b.eval.json" >/dev/null; then
  echo "  [PASS] eval determinism        identical across runs"
else
  echo "  [FAIL] eval determinism        differs across runs"; exit 1
fi
rm -f "$WORK/lua_core__b.eval.json"
