#!/usr/bin/env bash
# Build the instrumented lua Phase-4 eval target with Magma bugs applied.
#
#   build.sh <magma_repo> <work_dir>
#
# Fetches the pinned lua source (if absent), applies Magma's LUA001-004 bug
# patches (buggy branch live: -DMAGMA_ENABLE_CANARIES, no MAGMA_ENABLE_FIXES),
# compiles every core TU to LLVM IR, links one module, runs `separatrix analyze`
# to instrument + emit the behavioral graph, then links the file-mode harness +
# trace runtime + canary stub into $work_dir/lua_inst.
#
# Outputs in <work_dir>: lua_core.sepgraph.json, lua_inst, bugs.json.
set -euo pipefail

MAGMA="$(cd "${1:?usage: build.sh <magma_repo> <work_dir>}" && pwd)"
mkdir -p "${2:?usage: build.sh <magma_repo> <work_dir>}"
WORK="$(cd "$2" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEPROOT="$(cd "$HERE/../../../.." && pwd)"
SEP="$SEPROOT/build/separatrix"
RT="$SEPROOT/separatrix/runtime/sep_rt.c"
EXTRACT="$HERE/extract_bugs.py"

CLANG="${CLANG:-/opt/homebrew/opt/llvm/bin/clang}"
LLVMLINK="${LLVMLINK:-/opt/homebrew/opt/llvm/bin/llvm-link}"
LUA_COMMIT="dbdc74dc5502c2e05e1c1e2ac894943f418c8431"
PATCHDIR="$MAGMA/targets/lua/patches/bugs"

mkdir -p "$WORK"
REPO="$WORK/repo"

# --- fetch pinned lua source ---
if [ ! -d "$REPO" ]; then
  echo "[build] cloning lua @ $LUA_COMMIT"
  git clone --no-checkout --quiet https://github.com/lua/lua.git "$REPO"
  git -C "$REPO" checkout --quiet "$LUA_COMMIT"
fi

# --- apply Magma bug patches (clean tree first for idempotency) ---
git -C "$REPO" checkout --quiet -- .
git -C "$REPO" clean -fdq
for p in "$PATCHDIR"/LUA*.patch; do
  echo "[build] applying $(basename "$p")"
  git -C "$REPO" apply "$p"
done

# --- determinism fix: lua's short-string cache (luaS_new) is indexed by the
# string's POINTER address, so under ASLR its GC branch in luaS_clearcache flips
# run-to-run during init. That spurious early divergence is jaccard-invisible but
# corrupts first-bifurcation attribution (every perturbation looks like it first
# diverges in luaS_clearcache). Re-index by a content hash: deterministic, and
# behaviour-preserving (still a valid string cache). ---
sed -i '' 's|point2uint(str) % STRCACHE_N|luaS_hash(str, strlen(str), 0u) % STRCACHE_N|' "$REPO/lstring.c"
grep -q 'luaS_hash(str, strlen(str), 0u)' "$REPO/lstring.c" || { echo "determinism fix failed to apply"; exit 1; }

# --- extract ground-truth bug sites from the patched tree ---
python3 "$EXTRACT" "$PATCHDIR" "$REPO" -o "$WORK/bugs.json"

# --- compile every core TU to IR (buggy branch + canaries live) ---
# -Dluai_makeseed=...=0u pins lua's string-hash seed: by default lua 5.4 seeds it
# from time()/addresses per process, which jitters trace length run-to-run and
# destroys map reproducibility. A fixed seed makes traces deterministic.
CFLAGS="-g -O0 -S -emit-llvm -fno-discard-value-names -I $REPO -include $HERE/magma_canary.h -DMAGMA_ENABLE_CANARIES -Dluai_makeseed(L)=0u"
mkdir -p "$WORK/ll"
for f in "$REPO"/*.c; do
  b="$(basename "$f" .c)"
  case "$b" in lua|luac|onelua|ltests) continue ;; esac
  $CLANG $CFLAGS "$f" -o "$WORK/ll/$b.ll"
done
$LLVMLINK "$WORK"/ll/*.ll -S -o "$WORK/lua_core.ll"

# --- instrument + build behavioral graph ---
"$SEP" analyze "$WORK/lua_core.ll" -o "$WORK/lua_core"

# --- link instrumented module + harness + runtime + canary stub ---
$CLANG -g -O0 \
  "$WORK/lua_core.inst.ll" \
  "$HERE/lua_harness.c" \
  "$HERE/magma_stub.c" \
  "$RT" \
  -I "$REPO" \
  -o "$WORK/lua_inst" -lm
echo "[build] done -> $WORK/lua_inst , $WORK/lua_core.sepgraph.json , $WORK/bugs.json"

# --- optional fixed reference build (differential SBFL oracle, Task 3) ---
# Same patched+determinised sources, but with the historical fix active
# (-DMAGMA_ENABLE_FIXES, no canaries) and NO instrumentation — we only need its
# stdout digest, not a trace or graph. A run "fails" iff buggy and fixed digests
# differ. Opt-in: the trigger oracle is nondeterministic (uninitialised oldpc in
# LUA004), so the differential digest is the reproducible fail signal.
if [ "${BUILD_FIXED:-0}" = "1" ]; then
  echo "[build] fixed reference build (MAGMA_ENABLE_FIXES, uninstrumented)"
  FIXFLAGS="-g -O0 -S -emit-llvm -fno-discard-value-names -I $REPO -include $HERE/magma_canary.h -DMAGMA_ENABLE_FIXES -Dluai_makeseed(L)=0u"
  mkdir -p "$WORK/ll_fixed"
  for f in "$REPO"/*.c; do
    b="$(basename "$f" .c)"
    case "$b" in lua|luac|onelua|ltests) continue ;; esac
    $CLANG $FIXFLAGS "$f" -o "$WORK/ll_fixed/$b.ll"
  done
  $LLVMLINK "$WORK"/ll_fixed/*.ll -S -o "$WORK/lua_fixed_core.ll"
  $CLANG -g -O0 \
    "$WORK/lua_fixed_core.ll" \
    "$HERE/lua_harness.c" \
    "$HERE/magma_stub.c" \
    -I "$REPO" \
    -o "$WORK/lua_fixed" -lm
  echo "[build] done -> $WORK/lua_fixed"
fi
