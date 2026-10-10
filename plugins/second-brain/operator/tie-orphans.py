#!/usr/bin/env python3
"""tie-orphans.py — connect floating curated notes into the Obsidian graph.

The problem this fixes: skill machinery, agent definitions, build-state notes,
calibration fixtures, and references sidecars land in the vault with no inbound
wikilink, so they float as disconnected nodes in Obsidian's graph view. The
operator kept "fixing" the orphan COUNT by exempting them from the metric, which
never changed the graph. This tool changes the graph: it gives every floating
curated note a real inbound link from its natural hub.

How it works, and why it is safe to run on a schedule:
  - It finds every curated .md whose inbound wikilink count is zero (the same
    resolve logic vault-vitals.py uses).
  - It routes each to a hub file by a deterministic folder rule (see ROUTES).
  - In each hub it maintains ONE delimited, auto-generated block. Re-running
    REPLACES that block, never appends, so it is idempotent and picks up new
    files automatically. Hand-written content outside the block is untouched.
  - It only ever edits hub files and only inside the marker block. It never
    edits the floating notes themselves, never deletes, never moves.

Usage:
  python3 tie-orphans.py [--vault PATH] [--apply] [--json]
  Default is a DRY RUN (reports what it would link). Pass --apply to write.
"""
import argparse
import json
import os
import re
import sys

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
BLOCK_START = "<!-- tie-orphans:start (auto-generated, regenerated each run; do not edit inside) -->"
BLOCK_END = "<!-- tie-orphans:end -->"

# Folders whose files are intentionally unlinked (you link FROM them, not TO
# them) — never force a link on these.
SKIP_PREFIXES = (
    "Daily/", "Intelligence/", "Journal/", "_inbox/",
    "Resources/operator/reports/",
)


def find_md(vault):
    out = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in (".git", ".obsidian", ".trash")]
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return out


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def strip_code(s):
    s = re.sub(r"```.*?```", "", s, flags=re.DOTALL)
    return re.sub(r"`[^`]*`", "", s)


def is_skipped(rel):
    rp = rel.replace("\\", "/")
    if rp.startswith(SKIP_PREFIXES):
        return True
    base = os.path.basename(rp).lower()
    if base.endswith(".calendar.md"):
        return True
    return False


def route(rel):
    """Map a floating note to the hub file that should link it. Longest-specific
    rule wins. Returns a vault-relative hub path or None (report-only)."""
    rp = rel.replace("\\", "/")
    parts = rp.split("/")
    base = os.path.basename(rp).lower()

    # Skills/_agents/<plugin>/<file>: agent definitions have no natural hub;
    # report-only. Route them to a project hub here if your vault has one.
    if rp.startswith("Skills/_agents/") and len(parts) >= 4:
        return None

    # Skills/<skill>/...  A skill's own SKILL.md bridges from the skills index
    # Skills/CLAUDE.md (which sits on the mainland); every other file in the
    # skill folder bridges from that skill's SKILL.md.
    if rp.startswith("Skills/") and len(parts) >= 3:
        if base == "skill.md":
            return "Skills/CLAUDE.md"
        return f"Skills/{parts[1]}/SKILL.md"

    # Projects/<proj>/...  The project hub itself bridges from the board; every
    # other file in the project (notes, the folder CLAUDE.md, handoffs that got
    # parked here) bridges from that project's hub.
    if rp.startswith("Projects/") and len(parts) >= 3:
        proj = parts[1]
        hub = f"Projects/{proj}/{proj}.md"
        if os.path.normpath(rp) == os.path.normpath(hub):
            return "Projects/Projects.md"
        return hub

    # Context/voice-profile/...  -> the voice routing note.
    if rp.startswith("Context/voice-profile/"):
        return "Context/voice-and-writing.md"

    # Resources leaves (session handoffs, reviews, anything that floated) ->
    # the Resources folder index. Sub-folder CLAUDE.md indexes are not re-homed
    # here (they are their own routing nodes).
    if rp.startswith("Resources/") and len(parts) >= 2 and base != "claude.md":
        return "Resources/CLAUDE.md"

    # The Tasks folder index, if it floats, bridges from the live task list.
    if rp == "Tasks/CLAUDE.md":
        return "Tasks/todo.md"

    return None


def resolve_vault(arg=None):
    """--vault wins, then the SECOND_BRAIN_VAULT environment variable. Never guessed."""
    v = arg or os.environ.get("SECOND_BRAIN_VAULT")
    if not v:
        sys.exit("SECOND_BRAIN_VAULT is not set and no --vault was given. Set it to the "
                 "absolute path of your vault (see the plugin README).")
    v = os.path.abspath(os.path.expanduser(v))
    if not os.path.isdir(v):
        sys.exit("vault not found: %s (check SECOND_BRAIN_VAULT or --vault)" % v)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=None,
                    help="vault root; default: the SECOND_BRAIN_VAULT environment variable")
    ap.add_argument("--apply", action="store_true",
                    help="write the managed blocks (default is dry run)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vault = resolve_vault(args.vault)
    # Announce the TARGET before doing anything; see the same note in
    # normalize-wikilinks.py.
    origin = "explicit --vault" if args.vault else "SECOND_BRAIN_VAULT"
    mode = "APPLY — will write" if args.apply else "dry run"
    print(f"target vault: {vault}  [{origin}]  [{mode}]", file=sys.stderr)
    files = find_md(vault)
    rel_of = {p: os.path.relpath(p, vault) for p in files}
    # Do NOT cache every file's text. A capture layer can run past a gigabyte
    # of markdown (single transcripts reach tens of megabytes), so a whole-vault
    # contents dict gets the process OOM-killed before it links anything
    # (seen on a large vault). Each file is read once, scanned, and released below.

    basename_map = {}
    relpath_map = {}
    for p in files:
        r = rel_of[p]
        b = os.path.splitext(os.path.basename(r))[0].lower()
        basename_map.setdefault(b, set()).add(r)
        relpath_map[os.path.splitext(r)[0].lower().replace("\\", "/")] = r

    def resolve(target):
        t = target.split("|")[0].split("#")[0].strip()
        if not t or t.startswith(("#", "http://", "https://", ".")):
            return None
        tn = t.lower().replace("\\", "/")
        if tn.endswith(".md"):
            tn = tn[:-3]
        if "/" in tn:
            if tn in relpath_map:
                return relpath_map[tn]
            cands = [rp for k, rp in relpath_map.items()
                     if k == tn or k.endswith("/" + tn)]
            return sorted(cands)[0] if cands else None
        s = basename_map.get(tn)
        return sorted(s)[0] if s else None

    inbound = {rel_of[p]: 0 for p in files}
    for p in files:
        for m in WIKILINK_RE.finditer(strip_code(read(p))):
            tgt = resolve(m.group(1))
            if tgt and tgt != rel_of[p]:
                inbound[tgt] += 1

    # Floating curated notes we want to re-home.
    floats = sorted(r for r in inbound
                    if inbound[r] == 0 and not is_skipped(r)
                    and r.replace("\\", "/").startswith(
                        ("Skills/", "Projects/", "Context/", "Resources/", "Tasks/")))

    buckets = {}
    unrouted = []
    for r in floats:
        hub = route(r)
        if hub is None or not os.path.isfile(os.path.join(vault, hub)):
            unrouted.append(r)
            continue
        if os.path.normpath(hub) == os.path.normpath(r):
            continue  # never link a hub to itself
        buckets.setdefault(hub, []).append(r)

    def link_line(rel):
        rp = rel.replace("\\", "/")
        base = os.path.splitext(os.path.basename(rp))[0]
        # A bare "SKILL" link is unreadable in an index of many skills; name it
        # by the skill folder instead.
        if base.lower() == "skill":
            parts = rp.split("/")
            name = parts[-2] if len(parts) >= 2 else base
        else:
            name = base
        target = os.path.splitext(rp)[0]
        return f"- [[{target}|{name}]]"

    changed = []
    for hub, kids in sorted(buckets.items()):
        hub_abs = os.path.join(vault, hub)
        text = read(hub_abs)
        existing = re.search(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END),
                             text, flags=re.DOTALL)

        # CRITICAL: union the new floaters with whatever this managed block
        # already linked. The block IS the inbound link for these files, so a
        # file linked here on a prior run is no longer "floating" and would not
        # reappear in `kids`. Regenerating from `kids` alone would drop it and
        # re-orphan it (the oscillation bug). Union prevents that. Dead entries
        # (file no longer exists) are pruned so the block self-cleans.
        targets = set(kids)
        if existing:
            for m in WIKILINK_RE.finditer(existing.group(0)):
                t = m.group(1).split("|")[0].split("#")[0].strip()
                if not t:
                    continue
                cand = (t if t.lower().endswith(".md") else t + ".md").replace("\\", "/")
                if os.path.isfile(os.path.join(vault, cand)):
                    targets.add(cand)
        targets = sorted(targets)

        body = [BLOCK_START,
                "## Linked machinery and notes",
                "",
                ("Files in this area that would otherwise have no inbound link. "
                 "Auto-linked here by `tie-orphans.py` so they "
                 "stay connected in the graph. The list is additive: entries are "
                 "added as files appear, and pruned whenever a file no longer "
                 "exists at that path — which covers moves as well as deletions."),
                ""]
        body += [link_line(k) for k in targets]
        body += ["", BLOCK_END]
        block = "\n".join(body)

        if existing:
            new_text = text[:existing.start()] + block + text[existing.end():]
        else:
            sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
            new_text = text + sep + block + "\n"
        if new_text != text:
            changed.append((hub, len(targets)))
            if args.apply:
                with open(hub_abs, "w", encoding="utf-8") as fh:
                    fh.write(new_text)

    report = {
        "floating_curated": len(floats),
        "linked": sum(n for _, n in changed),
        "hubs_touched": [{"hub": h, "links": n} for h, n in sorted(changed)],
        "unrouted": unrouted,
        "applied": args.apply,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        mode = "APPLIED" if args.apply else "DRY RUN (use --apply to write)"
        print(f"tie-orphans {mode}")
        print(f"  floating curated notes : {len(floats)}")
        print(f"  linked into hubs       : {report['linked']}")
        for h, n in sorted(changed):
            print(f"    {h}: +{n}")
        if unrouted:
            print(f"  unrouted (report only) : {len(unrouted)}")
            for u in unrouted:
                print(f"    - {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
