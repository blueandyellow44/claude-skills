#!/usr/bin/env python3
"""
The public scrub for the city-walks-workflow export, as line patches that carry
no private text.

The private source is not a git repo, and a list of (old, new) string pairs would
publish the very text being removed. So each change is stored as the sha256 of
the source lines it replaces (plus a few unchanged lines around them, until that
run of lines is unique in the file) and the public lines that replace them.

  scrub.py apply <tree>               rewrite an exported tree in place, then scan it
  scrub.py make <src-tree> <pub-tree> write patches.json from a raw export and the
                                      hand-edited public copy of it

`apply` fails loudly, changing nothing, when the source has moved under a patch:
a run of lines that is gone or no longer unique, a file that is new, or a file
that has gone. Then re-derive the public copy and run `make` again.

After patching it scans every file and fails if any of these remain: the
patterns in scripts/check-public.sh, a few wording markers below, wikilinks and
em dashes in Markdown, and a list of private names and paths held only as hashes
(given at `make` time in CITY_WALKS_BANNED, so they are never written here).
"""
import difflib, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCHES = os.path.join(HERE, "patches.json")
CHECK_PUBLIC = os.path.join(HERE, "..", "check-public.sh")
MAX_CONTEXT = 12
# Wording the scrub removes; none of it is private on its own.
MARKERS = [r"\bMax's\b", r"\bMax:", r"Wally['’]s", r"\bgift", r"change-tracker"]
WIKILINK = re.compile(r"\[\[[A-Za-z][^]]*\]\]")


def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def files_in(root):
    out = []
    for d, _, fs in os.walk(root):
        for f in fs:
            out.append(os.path.relpath(os.path.join(d, f), root))
    return sorted(out)


def lines_of(path):
    return open(path, encoding="utf-8").read().splitlines(keepends=True)


def unique_at(hashes, key):
    n, k, hits = len(hashes), len(key), []
    for p in range(n - k + 1):
        if hashes[p:p + k] == key:
            hits.append(p)
            if len(hits) > 1:
                break
    return hits


def banned_from_env():
    """Strings to refuse, kept as (length, hash) so the strings themselves never
    land in this repo. Given at `make` time: CITY_WALKS_BANNED="a|b|c", case-insensitive."""
    words = [w.strip() for w in os.environ.get("CITY_WALKS_BANNED", "").split("|") if w.strip()]
    if not words:
        sys.exit("set CITY_WALKS_BANNED (strings separated by |) when running make")
    return sorted({(len(w), h(w.lower())) for w in words})


def make(src, pub):
    sf, pf = set(files_in(src)), set(files_in(pub))
    out = {"version": 1, "source_files": sorted(sf), "deleted": sorted(sf - pf),
           "added": {f: open(os.path.join(pub, f), encoding="utf-8").read() for f in sorted(pf - sf)},
           "banned": banned_from_env(), "files": {}}
    for f in sorted(sf & pf):
        a, b = lines_of(os.path.join(src, f)), lines_of(os.path.join(pub, f))
        if a == b:
            continue
        ah = [h(x) for x in a]
        hunks = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            for cb, ca in ((cb, ca) for t in range(MAX_CONTEXT + 1) for cb, ca in ((t, t), (t + 1, t), (t, t + 1))):
                lo, hi = i1 - cb, i2 + ca
                if lo < 0 or hi > len(a) or hi - lo == 0:
                    continue
                if len(unique_at(ah, ah[lo:hi])) == 1:
                    break
            else:
                sys.exit(f"{f}: no unique context for lines {i1 + 1}-{i2}")
            hunks.append({"key": ah[lo:hi], "ctx": cb, "old": i2 - i1, "new": b[j1:j2]})
        out["files"][f] = hunks
    with open(PATCHES, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {PATCHES}: {sum(len(v) for v in out['files'].values())} hunks in {len(out['files'])} files, "
          f"{len(out['added'])} added, {len(out['deleted'])} deleted")


def apply(tree):
    p = json.load(open(PATCHES, encoding="utf-8"))
    have = files_in(tree)
    new, gone = sorted(set(have) - set(p["source_files"])), sorted(set(p["source_files"]) - set(have))
    if new or gone:
        sys.exit("SOURCE CHANGED: " + (f"new files {new} (review them for private detail, then re-run make)" if new else "")
                 + (f" files gone {gone}" if gone else ""))
    problems, writes = [], {}
    for f, hunks in p["files"].items():
        a = lines_of(os.path.join(tree, f))
        ah = [h(x) for x in a]
        spans = []
        for n, hk in enumerate(hunks):
            hits = unique_at(ah, hk["key"])
            if len(hits) != 1:
                problems.append(f"{f} hunk {n + 1}: the lines it replaces are {'gone' if not hits else 'no longer unique'}")
                continue
            start = hits[0] + hk["ctx"]
            spans.append((start, start + hk["old"], hk["new"]))
        spans.sort(key=lambda x: x[:2])
        if any(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1)):
            problems.append(f"{f}: hunks overlap")
        for s, e, nl in reversed(spans):
            a[s:e] = nl
        writes[f] = "".join(a)
    if problems:
        sys.exit("SOURCE CHANGED under the scrub; nothing was written:\n  " + "\n  ".join(problems))
    for f, text in writes.items():
        open(os.path.join(tree, f), "w", encoding="utf-8").write(text)
    for f in p["deleted"]:
        os.remove(os.path.join(tree, f))
    for f, text in p["added"].items():
        os.makedirs(os.path.dirname(os.path.join(tree, f)), exist_ok=True)
        open(os.path.join(tree, f), "w", encoding="utf-8").write(text)
    scan(tree, p["banned"])
    print(f"scrub applied: {sum(len(v) for v in p['files'].values())} hunks in {len(p['files'])} files; scan clean")


def check_public_pattern():
    for line in open(CHECK_PUBLIC, encoding="utf-8"):
        if line.startswith("pattern='") and line.rstrip().endswith("'"):
            return line.rstrip()[len("pattern='"):-1]
    sys.exit(f"no pattern='...' line in {CHECK_PUBLIC}; the scan cannot run")


def scan(tree, banned):
    hits = []
    rx = re.compile("|".join([check_public_pattern()] + MARKERS))
    lengths = sorted({n for n, _ in banned})
    shas = {s for _, s in banned}
    for f in files_in(tree):
        text = open(os.path.join(tree, f), encoding="utf-8", errors="replace").read()
        for n, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            if rx.search(line) or (f.endswith(".md") and (WIKILINK.search(line) or "—" in line)):
                hits.append(f"{f}:{n}: {line.strip()[:120]}")
            elif any(h(low[i:i + k]) in shas for k in lengths for i in range(len(low) - k + 1)):
                hits.append(f"{f}:{n}: a private name or path (one of CITY_WALKS_BANNED)")
    if hits:
        sys.exit("PRIVATE DETAIL LEFT AFTER THE SCRUB:\n  " + "\n  ".join(hits))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "apply":
        apply(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "make":
        make(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
