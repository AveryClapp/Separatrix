#!/usr/bin/env bash
# Build the sqlite3 Phase-4 eval target (FIRST competitiveness target: logic bugs,
# output-differential oracle, no sanitizer, runs on macOS).
#
#   build.sh <magma_repo> <work_dir>
#   ORACLE_PROBE=1 build.sh <magma_repo> <work_dir>   # CHEAP pre-probe
#
# ORACLE_PROBE=1 builds ONLY the two uninstrumented binaries + bugs.json:
#   sqlite3_buggy  — Magma bugs live  (-DMAGMA_ENABLE_CANARIES)
#   sqlite3_fixed  — historical fixes (-DMAGMA_ENABLE_FIXES)
# A run "fails" iff the two binaries' result-row digests differ on the same SQL.
# The instrumented pipeline is added later (Task 4 analog).
#
# Input strategy: a corpus of VALID SQL scripts (gen_corpus.py) — byte-mutation
# breaks SQL (as with lua source), so perturbations are behaviour-validity-
# preserving variants that broadly exercise the bug subsystems.
set -euo pipefail

MAGMA="$(cd "${1:?usage: build.sh <magma_repo> <work_dir>}" && pwd)"
mkdir -p "${2:?usage: build.sh <magma_repo> <work_dir>}"
WORK="$(cd "$2" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEPROOT="$(cd "$HERE/../../../.." && pwd)"
LUATGT="$HERE/../lua"                         # reuse canary header + stub + extractor

CLANG="${CLANG:-/opt/homebrew/opt/llvm/bin/clang}"
PATCHDIR="$MAGMA/targets/sqlite3/patches/bugs"
TARBALL="$WORK/sqlite.tar.gz"
REPO="$WORK/repo"

# Magma's sqlite3 build flags (limits + SQLITE_DEBUG asserts catch logic bugs) and
# the feature-enable flags so the bug subsystems (fts5, rtree, ...) are compiled in.
SQLITE_FLAGS="-DSQLITE_MAX_LENGTH=128000000 -DSQLITE_MAX_SQL_LENGTH=128000000 \
-DSQLITE_MAX_MEMORY=25000000 -DSQLITE_PRINTF_PRECISION_LIMIT=1048576 -DSQLITE_DEBUG=1 \
-DSQLITE_MAX_PAGE_COUNT=16384 -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_RTREE \
-DSQLITE_ENABLE_GEOPOLY -DSQLITE_ENABLE_DBSTAT_VTAB -DSQLITE_ENABLE_JSON1"

# --- fetch pinned sqlite source (cached tarball) ---
if [ ! -f "$TARBALL" ]; then
  echo "[build] fetching sqlite tarball"
  curl -sL "https://www.sqlite.org/src/tarball/sqlite.tar.gz?r=8c432642572c8c4b" -o "$TARBALL"
fi

# --- fresh tree each build (idempotent clean slate; the tarball is not a git repo) ---
rm -rf "$REPO"
mkdir -p "$REPO"
tar -C "$REPO" --strip-components=1 -xzf "$TARBALL"

# --- apply Magma bug patches with plain `patch`. NOT `git apply`: the tarball
# tree has no .git, so git would discover Separatrix's parent repo and silently
# SKIP every patch (rc=0). `patch -p1` ignores git context and the diff --git
# header, applying off the ---/+++ paths. ---
for p in "$PATCHDIR"/SQL*.patch; do
  echo "[build] applying $(basename "$p")"
  patch -p1 -d "$REPO" -i "$p" >/dev/null
done

# --- extract ground-truth bug sites from the patched tree ---
python3 "$LUATGT/extract_bugs.py" "$PATCHDIR" "$REPO" --glob 'SQL*.patch' -o "$WORK/bugs.json"

# --- generate the amalgamation (canary calls live behind #ifdef in the source, so
# ONE amalgamation serves both buggy and fixed; the -D toggles the branch). ---
AMALG="$WORK/amalg"
rm -rf "$AMALG"; mkdir -p "$AMALG"
( cd "$AMALG" && "$REPO/configure" >/dev/null && make sqlite3.c >/dev/null 2>&1 )
test -f "$AMALG/sqlite3.c" || { echo "[build] amalgamation generation failed"; exit 1; }

build_one() {  # <out> <bug-mode-define> <extra-srcs...>
  local out="$1"; local mode="$2"; shift 2
  $CLANG -g -O0 $SQLITE_FLAGS -I "$AMALG" -include "$LUATGT/magma_canary.h" "$mode" \
    "$AMALG/sqlite3.c" "$HERE/sql_harness.c" "$@" -lpthread -ldl -lm -o "$out"
}

if [ "${ORACLE_PROBE:-0}" = "1" ]; then
  echo "[build] ORACLE_PROBE: uninstrumented buggy + fixed binaries"
  build_one "$WORK/sqlite3_buggy" "-DMAGMA_ENABLE_CANARIES" "$LUATGT/magma_stub.c"
  build_one "$WORK/sqlite3_fixed" "-DMAGMA_ENABLE_FIXES"
  echo "[build] done -> $WORK/sqlite3_buggy , $WORK/sqlite3_fixed , $WORK/bugs.json"
  exit 0
fi

echo "[build] instrumented pipeline not implemented yet; use ORACLE_PROBE=1 for the pre-probe."
exit 1
