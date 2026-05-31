#!/usr/bin/env bash
# Offline, deterministic reproduction of the agentic failure-attribution spike verdict.
# Re-scores the FROZEN manifest (manifest.json) from the committed LLM cache —
# no API key, no spend. The cache makes temp-0 replay byte-identical (see llm.py),
# so the 107-instance result reproduces bit-exact.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

# 1. Extract the committed LLM cache (one-time) -> fully offline, deterministic replay.
if [ ! -d .cache_llm ]; then
  echo "[1/3] extracting LLM cache (cache_llm.tar.gz)..."
  tar -xzf cache_llm.tar.gz
else
  echo "[1/3] .cache_llm present, skipping extract"
fi

# 2. Deps: offline scoring needs only numpy + scipy. (openai is imported lazily inside
#    llm._get_client, reached only on a cache MISS — full cache hit needs no API key.)
$PY -c "import numpy, scipy" 2>/dev/null || { echo "ERROR: need numpy + scipy (pip install numpy scipy)"; exit 1; }

# 3. Unit tests + re-score frozen manifest; assert bit-exact match to the committed verdict.
echo "[2/3] unit tests (scoring core)..."
$PY test_score.py
echo "[3/3] re-scoring frozen manifest from cache..."
$PY run_experiment.py
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git diff --quiet -- results.json; then
    echo "OK: results.json reproduced BIT-EXACT from cache (offline, no API key)."
  else
    echo "WARNING: results.json differs from the committed verdict — investigate."
    exit 1
  fi
fi
