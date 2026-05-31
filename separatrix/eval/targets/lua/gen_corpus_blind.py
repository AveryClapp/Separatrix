#!/usr/bin/env python3
"""BUG-BLIND lua corpus — the control for the divergence-localization win.

Structurally identical to gen_corpus.py (same program skeleton, same knob layout,
same deterministic sampling) so the ONLY difference is that the knob VALUES are
NOT set to the LUA001-004 trigger boundary conditions:

  gen_corpus.py (bug-aware)        gen_corpus_blind.py (bug-blind)
  GETLOCAL_IDX includes -3,-2,-1   GETLOCAL_IDX positive only [1,2,3]
   (negative -> findvararg/LUA001)  (normal local introspection; no LUA001 trigger)
  HOOK_INSPECT in {False,True}     HOOK_INSPECT = {False}
   (True -> getlocal(2,..) on caller, the LUA004-adjacent path)

The debug/vararg/hook subsystems are STILL exercised (so the bug regions remain
reachable and in the executed universe — verified post-hoc), but the inputs are
not engineered to sit on each bug's trigger. If divergence still ranks the bug
regions above coverage here, the win is genuine localization; if it collapses to
coverage, the 0.93 was the corpus targeting the bug sites.

  gen_corpus_blind.py <out_dir> [n]
"""
import itertools, os, random, sys

NARGS = [1, 2, 3, 4, 5]
GETLOCAL_IDX = [1, 2, 3]                  # positive only: no negative findvararg (LUA001) targeting
HOOK_MASK = ['"l"', '"c"', '"r"', '"lc"', '"lcr"']   # normal hook usage (line/call/return)
HOOK_INSPECT = [False]                    # no caller-inspection (drops the LUA004-adjacent path)
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
    out = sys.argv[1] if len(sys.argv) > 1 else "corpus_blind"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    os.makedirs(out, exist_ok=True)

    combos = list(itertools.product(NARGS, GETLOCAL_IDX, HOOK_MASK, HOOK_INSPECT, LOOP, EXTRA))
    rng = random.Random(0x5EED)  # same seed as bug-aware for comparability
    rng.shuffle(combos)
    combos = combos[:n]

    for i, c in enumerate(combos):
        with open(os.path.join(out, f"v{i:04d}.lua"), "w") as f:
            f.write(program(*c))
    print(f"generated {len(combos)} BUG-BLIND lua variants -> {out}")


if __name__ == "__main__":
    main()
