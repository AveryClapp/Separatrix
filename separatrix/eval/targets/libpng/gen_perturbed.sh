#!/usr/bin/env bash
# Materialize a deterministic perturbed-PNG corpus from a seed image.
#
#   gen_perturbed.sh <seed.png> <corpus_dir> [N]
#
# Drives the chaos engine (engine/perturb.py) with the FULL 0-255 byte alphabet
# over the seed PNG, writing N same-length single-byte perturbations to
# <corpus_dir>/pert_*.png. This is the locked input strategy (Decision #2):
# byte-perturbation of a seed through a permissive harness, NOT a curated valid
# corpus (which would leave the Magma bugs unreached, F=0). Generation is
# deterministic (perturb.py has no RNG; order is position-major), so the SAME dir
# feeds both the feasibility probe and the campaign with no drift. Reproducibility
# knobs (seed, count, alphabet, CRC mode) are recorded in corpus/PROVENANCE.txt.
set -euo pipefail

SEED="${1:?usage: gen_perturbed.sh <seed.png> <corpus_dir> [N]}"
CORPUS="${2:?usage: gen_perturbed.sh <seed.png> <corpus_dir> [N]}"
N="${3:-250}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEPROOT="$(cd "$HERE/../../../.." && pwd)"

mkdir -p "$CORPUS"
rm -f "$CORPUS"/pert_*.png

python3 - "$SEED" "$CORPUS" "$N" "$SEPROOT" <<'PY'
import os, sys
seed_path, corpus, n, seproot = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
sys.path.insert(0, os.path.join(seproot, "separatrix", "engine"))
import perturb

seed = open(seed_path, "rb").read()
alphabet = bytes(range(256))               # full binary alphabet for an image target
perts = perturb.generate(seed, n, alphabet=alphabet)
for i, (_, buf) in enumerate(perts):
    with open(os.path.join(corpus, f"pert_{i:04d}.png"), "wb") as f:
        f.write(buf)

with open(os.path.join(corpus, "PROVENANCE.txt"), "w") as f:
    f.write("libpng perturbed-input corpus (Decision #2: byte-perturbation of a seed)\n")
    f.write(f"seed_source     : {os.path.abspath(seed_path)}\n")
    f.write(f"seed_bytes      : {len(seed)}\n")
    f.write(f"generator       : engine/perturb.py generate() (deterministic, no RNG)\n")
    f.write(f"alphabet        : full 0-255 binary\n")
    f.write(f"requested_count : {n}\n")
    f.write(f"materialized    : {len(perts)}\n")
    f.write(f"crc_mode        : PNG_CRC_QUIET_USE (permissive harness)\n")
print(f"[gen_perturbed] {len(perts)} perturbations -> {corpus} (requested {n})")
PY
