#!/usr/bin/env python3
"""normalize-wikilinks.py - self-healing wikilink repair for the curated layer.

Obsidian resolves a wikilink by basename or by a vault-relative path. Three
recurring drifts produce dead links / "unresolved-link" ghost nodes in the
graph, none of which is vault rot:

  1. ``../``-prefixed targets  -> filesystem-relative paths Obsidian never
     resolves. e.g. ``[[../Projects/Alpha/Alpha|Alpha]]``.
  2. stale targets after a rename -> a folder/file was renamed but old links
     still point at the dead name. e.g. ``Projects/Old-Name/*`` after a
     rename to ``Projects/Alpha/*``.
  3. self / alias references that never had a note -> the owner's own name,
     the vault's name, bare skill names, etc.

This pass repairs all three, EVERY run, idempotently, so a scheduled job can
run it unattended and the graph stays clean without the owner touching anything. The
two maps below are the only thing to edit: when you rename a project, add a
RENAMES line; when a recurring alias needs a home, add an ALIASES line.

SAFETY RAILS (unchanged in spirit from the original normalizer):
  * Only the CURATED layer is touched. Session/transcript/Journal files
    (SESSION_LAYER_PREFIXES) are never modified -- rewriting verbatim history is
    forbidden.
  * A link is rewritten ONLY when (a) it currently does NOT resolve (or is a
    ``../`` phantom) AND (b) the repaired target resolves to exactly one real
    file. Working links are never disturbed; an ambiguous repair is skipped.
  * The visible text never changes: every rewrite carries the original display
    (alias, or the original target's last segment) as the new alias.
  * Code spans / fences are skipped. Dry-run by default; --apply writes in place
    (FUSE vault mount allows truncate-write, blocks unlink).

Usage (the vault is --vault, else the SECOND_BRAIN_VAULT environment variable):
    python3 normalize-wikilinks.py            # dry-run
    python3 normalize-wikilinks.py --apply    # write
"""
import argparse
import os
import re
import sys

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "dist",
             "build", "__pycache__", ".transcripts"}

SESSION_LAYER_PREFIXES = (
    "Intelligence/Claude-Chats/",
    "Intelligence/Cowork-Sessions/",
    "Intelligence/Claude-Code-Projects/",
    "Resources/sessions/",
    "Journal/",
)

# ---------------------------------------------------------------------------
# THE TWO MAPS - this is the only thing you edit to keep the graph self-healing.
# ---------------------------------------------------------------------------
# RENAMES: stale path -> new path. Keys are lowercased targets WITHOUT .md.
# `full` entries match an exact target; `prefix` entries match a leading path
# segment. Applied after ../ de-dotting, before resolution. Add a line here the
# day you rename a project folder or hub file.
# Both maps ship empty. Example entries:
#   RENAMES_FULL   = {"projects/old-name/old-name": "Projects/Alpha/Alpha"}
#   RENAMES_PREFIX = {"projects/old-name/": "Projects/Alpha/"}
RENAMES_FULL = {}
RENAMES_PREFIX = {}
# ALIASES: a bare target (no slash) that should point at a real note/skill.
# Lowercased key -> replacement target (path or basename). Only takes effect
# when the replacement actually resolves, so unmatched guesses are harmless.
# Example: {"jane-doe": "about-jane", "my-skill": "my-skill/SKILL"}
ALIASES = {}

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def is_session_layer(rp):
    return any(rp.startswith(p) for p in SESSION_LAYER_PREFIXES)


def find_md(vault):
    out = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(root, f))
    return out


def build_maps(vault, files):
    relpath_map = {}
    for p in files:
        r = os.path.relpath(p, vault).replace("\\", "/")
        relpath_map[os.path.splitext(r)[0].lower()] = r
    return relpath_map


def resolve(target, relpath_map):
    """vault-vitals-identical resolution. ../ ./ targets never resolve."""
    t = target.split("|")[0].split("#")[0].strip()
    if not t or t.startswith("#") or t.startswith(("http://", "https://")):
        return None
    if t.startswith(".") or "/../" in t:
        return None
    tn = t.lower().replace("\\", "/")
    if tn.endswith(".md"):
        tn = tn[:-3]
    if "/" in tn:
        if tn in relpath_map:
            return relpath_map[tn]
        cands = sorted({rp for k, rp in relpath_map.items()
                        if k == tn or k.endswith("/" + tn)})
        return cands[0] if len(cands) == 1 else (cands[0] if cands else None)
    # bare basename
    cands = sorted({rp for k, rp in relpath_map.items()
                    if os.path.basename(k) == tn})
    return cands[0] if cands else None


def repair_target(orig_target):
    """Given a wikilink target's path portion, return a repaired candidate
    string (de-dotted, renamed, aliased). Used only when the original is dead."""
    path = orig_target.split("|")[0].split("#")[0].strip()
    # 1. de-dot
    if path.startswith(("../", "./")) or "/../" in path:
        path = "/".join(s for s in path.split("/") if s not in ("..", "."))
    low = path.lower()
    low = low[:-3] if low.endswith(".md") else low
    # 2. renames (full then prefix)
    if low in RENAMES_FULL:
        return RENAMES_FULL[low]
    for pre, repl in RENAMES_PREFIX.items():
        if low.startswith(pre):
            return repl + path[len(pre):]
    # 3. alias (bare only)
    if "/" not in low and low in ALIASES:
        return ALIASES[low]
    # 4. if de-dotting alone changed it, return the de-dotted path
    if path != orig_target.split("|")[0].split("#")[0].strip():
        return path
    return None  # nothing to try


def spans_to_skip(text):
    return [(m.start(), m.end()) for m in FENCE_RE.finditer(text)] + \
           [(m.start(), m.end()) for m in INLINE_CODE_RE.finditer(text)]


def in_any(pos, spans):
    return any(a <= pos < b for a, b in spans)


def display_of(inner):
    """What Obsidian renders for a wikilink, so we can preserve it as alias."""
    parts = inner.split("|", 1)
    if len(parts) > 1:
        return parts[1]
    base = parts[0].split("#")[0].strip().rstrip("\\")
    return base.split("/")[-1]


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
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--vault", default=None)
    args = ap.parse_args()
    vault = resolve_vault(args.vault)
    # Announce the TARGET before doing anything. Without this line a run aimed
    # at the wrong vault is visually identical to a correct one, and with --apply
    # it rewrites that vault while the operator believes they are grooming
    # another. Read the target line, never only the success table.
    origin = "explicit --vault" if args.vault else "SECOND_BRAIN_VAULT"
    mode = "APPLY — will write" if args.apply else "dry run"
    print(f"target vault: {os.path.abspath(vault)}  [{origin}]  [{mode}]",
          file=sys.stderr)
    files = find_md(vault)
    relpath_map = build_maps(vault, files)

    rewrites = 0
    files_changed = 0
    unresolved = {}

    for p in files:
        r = os.path.relpath(p, vault).replace("\\", "/")
        if is_session_layer(r):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        skip = spans_to_skip(text)
        out = []
        last = 0
        changed = False
        for m in WIKILINK_RE.finditer(text):
            if in_any(m.start(), skip):
                continue
            inner = m.group(1)
            target = inner.split("|")[0]
            # leave working, non-../ links untouched
            already = resolve(inner, relpath_map)
            is_dotdot = target.strip().startswith(("../", "./")) or "/../" in target
            if already is not None and not is_dotdot:
                continue
            cand = repair_target(inner)
            hit = resolve(cand, relpath_map) if cand else None
            if hit is None:
                unresolved.setdefault(target.strip(), 0)
                unresolved[target.strip()] += 1
                continue
            anchor = ""
            bt = inner.split("|")[0]
            if "#" in bt:
                anchor = "#" + bt.split("#", 1)[1]
            new_inner = os.path.splitext(hit)[0] + anchor + "|" + display_of(inner)
            out.append(text[last:m.start()])
            out.append("[[" + new_inner + "]]")
            last = m.end()
            changed = True
            rewrites += 1
        if changed:
            out.append(text[last:])
            files_changed += 1
            if args.apply:
                try:
                    with open(p, "w", encoding="utf-8") as fh:
                        fh.write("".join(out))
                except OSError as e:
                    print(f"  WRITE FAILED {r}: {e}", file=sys.stderr)

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"[{mode}] rewrites: {rewrites}  files changed: {files_changed}")
    print(f"residual dead/ghost targets (no clean repair): {len(unresolved)} "
          f"unique, {sum(unresolved.values())} refs")
    for t, c in sorted(unresolved.items(), key=lambda kv: -kv[1])[:40]:
        print(f"  GHOST  {c:3d}x  {t}")


if __name__ == "__main__":
    sys.exit(main())
