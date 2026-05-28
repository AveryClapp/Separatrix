#!/usr/bin/env python3
"""Generate a corpus of valid lua programs for the Phase-4 eval campaign.

Naive byte-mutation of lua *source* overwhelmingly breaks parsing (>90% syntax
errors), so it never reaches the semantic bug regions. Instead we vary a set of
independent, behaviour-preserving-validity knobs that exercise lua's debug /
vararg / io / string / table subsystems. The Magma bugs (LUA001-004) live at
specific spots inside those subsystems; the eval asks whether trajectory
sensitivity localises those spots among the broadly-exercised code. Generation
is deterministic (seeded) so the campaign is reproducible.

  gen_corpus.py <out_dir> [n]
"""
import itertools, os, random, sys

# Each tuple is one independent knob; the cartesian product is sampled.
NARGS = [1, 2, 3, 4, 5]
GETLOCAL_IDX = [-3, -2, -1, 1, 2, 3]      # negative -> findvararg (LUA001)
HOOK_MASK = ['"l"', '"c"', '"r"', '"lc"', '"lcr"']   # line/call/return -> luaG_traceexec, changedline
HOOK_INSPECT = [False, True]              # hook calls debug.getlocal on its caller
LOOP = [1, 2, 3]
EXTRA = [
    "",
    "acc = acc + #string.rep('ab', i)",
    "local tt = {}; for k=1,i do tt[k]=k end; acc = acc + #tt",
    "acc = (acc * 3 + 1) % 97",
    "acc = acc + (tostring(i)):byte(1)",
]


def program(nargs, gidx, mask, inspect, loop, extra):
    args = ", ".join(str(10 + k) for k in range(nargs))
    inspect_body = (f"local nm = debug.getlocal(2, {gidx}); "
                    "if nm then seen = seen + 1 end") if inspect else "seen = seen + 1"
    return f"""local seen = 0
local function va(...)
  local probe = debug.getlocal(1, {gidx})
  local t = {{...}}
  return #t + (probe and 1 or 0)
end
debug.sethook(function(ev) {inspect_body} end, {mask})
local acc = 0
for i = 1, {loop} do
  acc = acc + va({args})
  {extra}
end
debug.sethook()
return tostring(acc) .. ":" .. seen
"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "corpus"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    os.makedirs(out, exist_ok=True)

    combos = list(itertools.product(NARGS, GETLOCAL_IDX, HOOK_MASK, HOOK_INSPECT, LOOP, EXTRA))
    rng = random.Random(0x5EED)  # deterministic sample
    rng.shuffle(combos)
    combos = combos[:n]

    for i, c in enumerate(combos):
        with open(os.path.join(out, f"v{i:04d}.lua"), "w") as f:
            f.write(program(*c))
    print(f"generated {len(combos)} valid lua variants -> {out}")


if __name__ == "__main__":
    main()
