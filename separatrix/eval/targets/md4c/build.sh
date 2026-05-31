#!/usr/bin/env bash
# Build the instrumented md4c eval target with the BugsC++ md4c #4 bug applied.
#
#   build.sh <work_dir>
#
# Fetches the pinned md4c source (if absent), applies the BugsC++ defect-#4
# "buggy" patch (a logical error in md_link_label_cmp — wrong loop end
# condition), compiles the md2html application's translation units to LLVM IR,
# links one module, runs `separatrix analyze` to instrument + emit the
# behavioral graph, then links the instrumented module + trace runtime into
# $work_dir/md2html_inst.
#
# md4c's own md2html CLI is the harness: `md2html_inst <file.md>` reads the
# markdown file from argv[1] and writes HTML to stdout; SEP_TRACE names the
# trace output file. No separate harness TU is needed (unlike lua).
#
# Outputs in <work_dir>: md4c_core.sepgraph.json, md2html_inst, bugs.json.
#
# BUILD_FIXED=1 also builds an uninstrumented fixed reference (md2html_fixed,
# the clean unpatched source) for the output-differential oracle: a run "fails"
# iff the buggy and fixed HTML digests differ.
set -euo pipefail

mkdir -p "${1:?usage: build.sh <work_dir>}"
WORK="$(cd "$1" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEPROOT="$(cd "$HERE/../../../.." && pwd)"
SEP="$SEPROOT/build/separatrix"
RT="$SEPROOT/separatrix/runtime/sep_rt.c"

CLANG="${CLANG:-/opt/homebrew/opt/llvm/bin/clang}"
LLVMLINK="${LLVMLINK:-/opt/homebrew/opt/llvm/bin/llvm-link}"
# BugsC++ taxonomy/md4c checks this commit out, then applies the defect patch.
MD4C_COMMIT="da5821ae0ddb0e0cb853455dd018a7592a35151b"
PATCH="$HERE/md4c004-buggy.patch"

REPO="$WORK/repo"

# --- fetch pinned md4c source ---
if [ ! -d "$REPO" ]; then
  echo "[build] cloning md4c @ $MD4C_COMMIT"
  git clone --no-checkout --quiet https://github.com/mity/md4c.git "$REPO"
  git -C "$REPO" checkout --quiet "$MD4C_COMMIT"
fi

# --- clean tree for idempotency, then (buggy build) apply the defect patch ---
git -C "$REPO" checkout --quiet -- .
git -C "$REPO" clean -fdq
if [ "${BUILD_FIXED:-0}" != "1" ]; then
  echo "[build] applying BugsC++ md4c #4 buggy patch"
  git -C "$REPO" apply "$PATCH"
fi

# md2html's translation units. Both inputs are computable without an oracle.
TUS=(src/md4c.c src/md4c-html.c src/entity.c md2html/md2html.c md2html/cmdline.c)
# MD_VERSION_* are normally injected by CMake as compile-definitions (md4c 0.4.5
# at this commit); md2html.c's --version path needs them. Pin them here so the
# IR build does not depend on running CMake.
CFLAGS="-g -O0 -S -emit-llvm -fno-discard-value-names -I $REPO/src -I $REPO/md2html \
-DMD_VERSION_MAJOR=0 -DMD_VERSION_MINOR=4 -DMD_VERSION_RELEASE=5"

if [ "${BUILD_FIXED:-0}" = "1" ]; then
  # --- uninstrumented fixed reference (clean source, no trace/graph) ---
  echo "[build] fixed reference build (unpatched, uninstrumented)"
  mkdir -p "$WORK/ll_fixed"
  for f in "${TUS[@]}"; do
    b="$(basename "$f" .c)"
    $CLANG $CFLAGS "$REPO/$f" -o "$WORK/ll_fixed/$b.ll"
  done
  $LLVMLINK "$WORK"/ll_fixed/*.ll -S -o "$WORK/md4c_fixed.ll"
  $CLANG -g -O0 "$WORK/md4c_fixed.ll" -o "$WORK/md2html_fixed" -lm
  echo "[build] done -> $WORK/md2html_fixed"
  exit 0
fi

# --- compile every md2html TU to IR (buggy source) ---
mkdir -p "$WORK/ll"
for f in "${TUS[@]}"; do
  b="$(basename "$f" .c)"
  $CLANG $CFLAGS "$REPO/$f" -o "$WORK/ll/$b.ll"
done
$LLVMLINK "$WORK"/ll/*.ll -S -o "$WORK/md4c_core.ll"

# --- instrument + build behavioral graph ---
"$SEP" analyze "$WORK/md4c_core.ll" -o "$WORK/md4c_core"

# --- link instrumented module + trace runtime (md2html main is the harness) ---
$CLANG -g -O0 "$WORK/md4c_core.inst.ll" "$RT" -o "$WORK/md2html_inst" -lm

# --- vendored ground-truth bug sites (buggy-tree md4c.c line numbers) ---
cp "$HERE/bugs.json" "$WORK/bugs.json"
echo "[build] done -> $WORK/md2html_inst , $WORK/md4c_core.sepgraph.json , $WORK/bugs.json"
