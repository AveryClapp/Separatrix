#!/usr/bin/env python3
"""Extract ground-truth bug sites from applied Magma bug patches.

For each matching patch, find the added `MAGMA_LOG(...)` canary line and the file
it lands in, then locate that exact line in the *patched* source tree to get its
final line number. Emits bugs.json: [{bug_id, file, line, condition}].

  extract_bugs.py <patches/bugs dir> <patched repo dir> -o bugs.json [--glob 'PNG*.patch']

--glob selects which patches to read (default 'LUA*.patch'); the canary format is
identical across Magma targets, so the same extractor serves every per-target port.
"""
import argparse, glob, json, os, re


def canary_from_patch(patch_path):
    """Return (file, canary_line_text) for the MAGMA_LOG canary in a patch."""
    cur_file = None
    with open(patch_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("+++ "):
                # '+++ b/ldebug.c' -> 'ldebug.c'
                cur_file = re.sub(r"^\+\+\+ b/", "", line.strip())
            elif line.startswith("+") and "MAGMA_LOG" in line:
                return cur_file, line[1:].rstrip("\n")
    return None, None


def find_line(repo, rel_file, canary_text):
    """Line number (1-based) of the canary in the patched source."""
    path = os.path.join(repo, rel_file)
    want = canary_text.strip()
    cond = want.split("%MAGMA_BUG%", 1)[-1]  # the part unique to this bug
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i, ln in enumerate(lines, start=1):
        if ln.strip() == want:
            return i
    # fallback: match on the (unique) condition tail
    for i, ln in enumerate(lines, start=1):
        if "MAGMA_LOG" in ln and cond.strip(' ,;)') in ln:
            return i
    raise RuntimeError(f"canary not found in {path}: {want!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("patchdir")
    ap.add_argument("repo")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--glob", default="LUA*.patch",
                    help="patch filename glob (default LUA*.patch; e.g. 'PNG*.patch')")
    args = ap.parse_args()

    bugs = []
    for patch in sorted(glob.glob(os.path.join(args.patchdir, args.glob))):
        bug_id = os.path.splitext(os.path.basename(patch))[0]
        rel_file, canary = canary_from_patch(patch)
        if not canary:
            print(f"  warn: no canary in {bug_id}")
            continue
        line = find_line(args.repo, rel_file, canary)
        bugs.append({"bug_id": bug_id, "file": rel_file, "line": line,
                     "condition": canary.strip()})

    json.dump(bugs, open(args.out, "w"), indent=2)
    print(f"extracted {len(bugs)} bug sites -> {args.out}")
    for b in bugs:
        print(f"  {b['bug_id']}: {b['file']}:{b['line']}")


if __name__ == "__main__":
    main()
