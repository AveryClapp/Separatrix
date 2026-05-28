"""Chaos Engine v1 — unguided minimal input perturbations.

Given a seed input (bytes), enumerate *minimal* same-length perturbations:
single-byte mutations and +-1 on digit runs, plus boundary swaps on numeric
tokens. Same length keeps perturbations minimal and avoids trivial divergence
from length changes. Generation is deterministic (fixed position/alphabet
order), so the resulting sensitivity map is reproducible.

v1 is uniform over positions — structural targeting is Phase 3. The output is a
list of (label, bytes) perturbations, deduplicated, excluding the seed itself.
"""

# Printable, argv-safe replacement alphabet (no NUL, no whitespace surprises).
_ALPHABET = b"0123456789()+-*/. "


def _is_digit(b):
    return 0x30 <= b <= 0x39


def generate(seed: bytes, max_perturbations: int = 4000):
    """Deterministic minimal perturbations of `seed` (same length)."""
    out = []
    seen = {seed}

    def add(label, buf):
        if buf in seen:
            return
        seen.add(buf)
        out.append((label, buf))

    n = len(seed)
    for i in range(n):
        b = seed[i]
        # +-1 and low-bit flip on the raw byte.
        for delta, tag in ((1, "inc"), (-1, "dec")):
            nb = (b + delta) & 0xFF
            if nb in _ALPHABET:
                add(f"byte{i}:{tag}", seed[:i] + bytes([nb]) + seed[i + 1:])
        # digit-specific: +-1 within 0..9, and boundary values.
        if _is_digit(b):
            for nb in (b - 1, b + 1):
                if 0x30 <= nb <= 0x39:
                    add(f"digit{i}", seed[:i] + bytes([nb]) + seed[i + 1:])
            for bound in (b"0", b"9"):
                if bound[0] != b:
                    add(f"bound{i}", seed[:i] + bound + seed[i + 1:])
        # structural swaps from the alphabet (a few, deterministic).
        for nb in _ALPHABET:
            if nb != b:
                add(f"alpha{i}", seed[:i] + bytes([nb]) + seed[i + 1:])
                break  # one structural swap per position keeps the set bounded

    # Deterministic order already (position-major); cap for tractability.
    return out[:max_perturbations]
