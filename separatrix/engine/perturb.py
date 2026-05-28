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


def generate(seed: bytes, max_perturbations: int = 4000, alphabet: bytes = _ALPHABET):
    """Deterministic minimal perturbations of `seed` (same length).

    `alphabet` is the replacement byte set for inc/dec admission and structural
    swaps; defaults to the tinyexpr-oriented set so Phase 1-3 maps are unchanged.
    Pass a broader set (e.g. printable ASCII) for text targets like lua."""
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
            if nb in alphabet:
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
        for nb in alphabet:
            if nb != b:
                add(f"alpha{i}", seed[:i] + bytes([nb]) + seed[i + 1:])
                break  # one structural swap per position keeps the set bounded

    # Deterministic order already (position-major); cap for tractability.
    return out[:max_perturbations]


def _variants_at(seed, i):
    """All distinct minimal single-byte perturbations at position i."""
    b = seed[i]
    cands = set(_ALPHABET) | {(b + 1) & 0xFF, (b - 1) & 0xFF, b ^ 1}
    out = []
    for nb in sorted(cands):
        if nb != b and 0x20 <= nb < 0x7F:
            out.append(seed[:i] + bytes([nb]) + seed[i + 1:])
    return out


def generate_at(seed: bytes, positions, cap: int):
    """Distinct minimal perturbations concentrated at the given input positions,
    in the order positions are listed (highest-priority first), up to `cap`."""
    out, seen = [], {seed}
    for i in positions:
        if not (0 <= i < len(seed)):
            continue
        for buf in _variants_at(seed, i):
            if buf not in seen:
                seen.add(buf)
                out.append((f"at{i}", buf))
                if len(out) >= cap:
                    return out
    return out


def probe_once(seed: bytes):
    """Exactly one deterministic perturbation per input position (cost = len),
    so a guided strategy can map every position to the code region it reaches."""
    out = []
    for i in range(len(seed)):
        variants = _variants_at(seed, i)
        if variants:
            out.append((i, variants[0]))
    return out


def sample_random(seed: bytes, n: int, rng):
    """n random same-length single-byte perturbations (the naive baseline).
    Draws may repeat — that is realistic for unguided random perturbation."""
    out = []
    if not seed:
        return out
    for _ in range(n):
        i = rng.randrange(len(seed))
        nb = rng.choice(_ALPHABET)
        while nb == seed[i]:
            nb = rng.choice(_ALPHABET)
        out.append((f"rand{i}", seed[:i] + bytes([nb]) + seed[i + 1:]))
    return out
