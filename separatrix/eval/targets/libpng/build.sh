#!/usr/bin/env bash
# Build the libpng Phase-4 eval target (first multi-library competitiveness target)
# with Magma bugs applied.
#
#   build.sh <magma_repo> <work_dir>
#   ORACLE_PROBE=1 build.sh <magma_repo> <work_dir>   # CHEAP pre-probe (Task 3)
#
# ORACLE_PROBE=1 builds ONLY the two uninstrumented binaries needed to measure the
# differential oracle's feasibility before the multi-day instrumented pipeline:
#   libpng_buggy  — Magma bugs live  (-DMAGMA_ENABLE_CANARIES)
#   libpng_fixed  — historical fixes (-DMAGMA_ENABLE_FIXES)
# plus bugs.json. No IR-emit, no `separatrix analyze`, no trace runtime. A run
# "fails" iff the two binaries' stdout digests differ on the same input.
#
# The default (non-ORACLE_PROBE) instrumented pipeline is added in Task 4.
#
# Input strategy (Decision #2): the corpus is byte-perturbations of a seed PNG
# (gen_perturbed.sh), decoded through a PERMISSIVE harness (png_harness.c, CRC
# tolerance) — NOT a curated valid-image corpus.
set -euo pipefail

MAGMA="$(cd "${1:?usage: build.sh <magma_repo> <work_dir>}" && pwd)"
mkdir -p "${2:?usage: build.sh <magma_repo> <work_dir>}"
WORK="$(cd "$2" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEPROOT="$(cd "$HERE/../../../.." && pwd)"
LUATGT="$HERE/../lua"                         # reuse canary header + stub + extractor

CLANG="${CLANG:-/opt/homebrew/opt/llvm/bin/clang}"
ZLIB_PREFIX="${ZLIB_PREFIX:-/opt/homebrew/opt/zlib}"
LIBPNG_COMMIT="a37d4836519517bdce6cb9d956092321eca3e73b"
PATCHDIR="$MAGMA/targets/libpng/patches/bugs"

REPO="$WORK/repo"

# --- fetch pinned libpng source ---
if [ ! -d "$REPO" ]; then
  echo "[build] cloning libpng @ $LIBPNG_COMMIT"
  git clone --no-checkout --quiet https://github.com/glennrp/libpng.git "$REPO"
  git -C "$REPO" checkout --quiet "$LIBPNG_COMMIT"
fi

# --- apply Magma bug patches (clean tree first for idempotency) ---
git -C "$REPO" checkout --quiet -- .
git -C "$REPO" clean -fdq
for p in "$PATCHDIR"/PNG*.patch; do
  echo "[build] applying $(basename "$p")"
  git -C "$REPO" apply "$p"
done

# --- pnglibconf.h without autotools: use libpng's official prebuilt config, then
# raise the dimension caps to match Magma's setup patch (USER_WIDTH/HEIGHT_MAX ->
# 0x7fffffff) so a perturbed IHDR is not rejected before reaching the deeper bugs.
# (The read decode path embeds no timestamps, so no determinism pinning is needed,
# unlike the lua port.) ---
cp "$REPO/scripts/pnglibconf.h.prebuilt" "$REPO/pnglibconf.h"
sed -i '' 's/#define PNG_USER_WIDTH_MAX 1000000/#define PNG_USER_WIDTH_MAX 0x7fffffff/' "$REPO/pnglibconf.h"
sed -i '' 's/#define PNG_USER_HEIGHT_MAX 1000000/#define PNG_USER_HEIGHT_MAX 0x7fffffff/' "$REPO/pnglibconf.h"

# --- extract ground-truth bug sites from the patched tree ---
python3 "$LUATGT/extract_bugs.py" "$PATCHDIR" "$REPO" --glob 'PNG*.patch' -o "$WORK/bugs.json"

# libpng library sources (read + write); exclude the files that carry their own
# main() (pngtest.c, example.c).
LIBSRC=()
for f in "$REPO"/png*.c; do
  case "$(basename "$f")" in pngtest.c) continue ;; esac
  LIBSRC+=("$f")
done

# PNG_ARM_NEON_OPT=0: force libpng's portable C path on arm64 (the NEON
# intrinsic sources live under arm/ and we compile only the top-level TUs; the C
# path is also the deterministic, instrumentation-friendly one for Task 4+).
INCS="-I $REPO -I $ZLIB_PREFIX/include -DPNG_ARM_NEON_OPT=0"
LIBS="-L $ZLIB_PREFIX/lib -lz -lm"

build_one() {  # <out> <bug-mode-define> <extra-srcs...>
  local out="$1"; local mode="$2"; shift 2
  # -include math.h: libpng's pngpriv.h takes a legacy <fp.h> path under
  # TARGET_OS_MAC unless <math.h> (guard __MATH_H__) is already included.
  $CLANG -g -O0 $INCS -include math.h -include "$LUATGT/magma_canary.h" "$mode" \
    "${LIBSRC[@]}" "$HERE/png_harness.c" "$@" $LIBS -o "$out"
}

if [ "${ORACLE_PROBE:-0}" = "1" ]; then
  echo "[build] ORACLE_PROBE: uninstrumented buggy + fixed binaries"
  # buggy: canaries live (magma_stub.c provides the magma_log sink).
  build_one "$WORK/libpng_buggy" "-DMAGMA_ENABLE_CANARIES" "$LUATGT/magma_stub.c"
  # fixed: historical fixes, no canaries (no magma_log references -> no stub).
  build_one "$WORK/libpng_fixed" "-DMAGMA_ENABLE_FIXES"
  echo "[build] done -> $WORK/libpng_buggy , $WORK/libpng_fixed , $WORK/bugs.json"
  exit 0
fi

echo "[build] instrumented pipeline not implemented yet (Task 4); use ORACLE_PROBE=1 for the pre-probe."
exit 1
