#!/usr/bin/env python3
"""
Build the decision record of ONE object (a file, a feature, an image asset) before it is edited.

The project, its hub, memory and transcripts are resolved from the working folder by
project_record.configure(); per-project data lives in Projects/<Hub>/object-record.json.
The vault is the SECOND_BRAIN_VAULT environment variable.

Cause it fixes: the project record is read once at session start and never per
object, so a thing gets redone while the version its owner approved sits one
`git log` away.

Usage: object_record.py <slug-or-repo-path> [--alias "other name"] [--repo DIR] [--project HUB] [--no-images]
Writes .agents/object-records/<slug>-<YYYYMMDD>.md (and versions/ + a contact sheet)
inside the repo, and prints the brief's path. Read only everywhere else.
"""
import argparse, datetime, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_record as cw

# Fast typing: "peerfect", "perfct". Match the skeleton, not the spelling.
APPROVE = re.compile(r"p\w{0,2}r+\w{0,2}f\w{0,3}ct|dead on|looks? good|love (it|this)|that'?s it|nailed|great|approved|keep (it|this)|yes[,. ]", re.I)
REJECT = re.compile(r"huge|too (big|small|heavy)|wrong|off\b|mess|slant|floaty|kill it|tumbling|not (right|good)|still|again|fix", re.I)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--alias", action="append", default=[])
    ap.add_argument("--repo", default=None, help="default: the git root of the working folder")
    ap.add_argument("--project", default=None, help="hub name, when the folder does not resolve to one")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    info = cw.configure(cwd=a.repo or os.getcwd(), project=a.project)
    repo = info["repo"]
    print(f"project: {info['hub']} ({info['how']}); repo: {repo}; memory dirs: {len(info['memory_dirs'])}")

    if "/" in a.target or "." in a.target:
        rel = os.path.relpath(os.path.abspath(a.target), repo) if os.path.isabs(a.target) else a.target
        slug = os.path.splitext(os.path.basename(rel))[0]
        paths = [rel]
    else:
        slug = a.target
        tmpl = cw.CONFIG.get("default_path")
        if tmpl:
            paths = [tmpl.format(slug=slug)]
        else:   # any tracked file whose name stem is the slug
            tracked = git(repo, "ls-files").splitlines()
            paths = [p for p in tracked if os.path.splitext(os.path.basename(p))[0].lower() == slug.lower()][:6]
            if not paths:
                paths = [slug]   # no file: the record is commits, hub, memory and words only
    names = cw.spellings(slug, a.alias)
    pat = cw.pattern(names)
    today = datetime.date.today().strftime("%Y%m%d")
    outdir = os.path.join(repo, ".agents", "object-records")
    os.makedirs(outdir, exist_ok=True)
    L = [f"# Object record: {slug} ({today})", "",
         "generated: " + datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "",
         f"Searched as: {', '.join(repr(n) for n in names)}", ""]

    # 1. History of its own files, every branch, commit bodies included (they carry the owner's words).
    L += ["## 1. git history of its files (`git log --all --follow`)", ""]
    shas = []
    for p in paths:
        log = git(repo, "log", "--all", "--follow", "--date=short", "--format=%h%x09%ad%x09%s", "--", p)
        L.append(f"`{p}`: {len(log.splitlines())} commit(s)")
        for row in log.splitlines():
            h, d, s = row.split("\t", 2)
            shas.append((h, d, p))
            L.append(f"- `{h}` {d} {s}")
        dirty = git(repo, "status", "--porcelain", "--", p).strip()
        if dirty:
            L.append(f"- WORKING TREE differs from HEAD: `{dirty}` (uncommitted work exists; do not overwrite it blind)")
        L.append("")
    # Commits that NAME the object anywhere in their message, even if they touched other files.
    named_commits = git(repo, "log", "--all", "-i", "-E", "--date=short", "--format=%h%x09%ad%x09%s",
                "--grep=" + "|".join(re.escape(n) for n in names))
    L += ["## 2. commits whose message names it", ""]
    seen = {h for h, _, _ in shas}
    for row in named_commits.splitlines():
        h, d, s = row.split("\t", 2)
        L.append(f"- `{h}` {d} {s}" + ("" if h in seen else "  (touches other files)"))
    L.append("")
    L += ["### Commit bodies that name it (read these; rulings are quoted there)", ""]
    for row in named_commits.splitlines()[:12]:
        h = row.split("\t", 1)[0]
        body = git(repo, "show", "-s", "--format=%b", h).strip()
        hits = [ln.strip() for ln in body.splitlines() if pat.search(ln) or cw.RELAY.search(ln)]
        if hits:
            L.append(f"`{h}`:")
            L += [f"> {ln}" for ln in hits[:8]]
            L.append("")

    # 3. Every prior version, viewable.
    if not a.no_images and paths[0].lower().endswith(".png") and shas:
        vdir = os.path.join(outdir, slug, "versions")
        os.makedirs(vdir, exist_ok=True)
        tiles = []
        for h, d, p in shas:
            dest = os.path.join(vdir, f"{d}-{h}.png")
            blob = subprocess.run(["git", "-C", repo, "show", f"{h}:{p}"], capture_output=True).stdout
            if blob:
                open(dest, "wb").write(blob)
                tiles.append((f"{d} {h}", dest))
        cur = os.path.join(repo, paths[0])
        if os.path.exists(cur):
            tiles.insert(0, ("WORKING TREE", cur))
        sheet = os.path.join(outdir, slug, f"contact-sheet-{today}.png")
        try:
            from PIL import Image, ImageDraw
            cell, pad = 300, 26
            cols = min(4, len(tiles))
            rows = -(-len(tiles) // cols)
            im = Image.new("RGB", (cols * cell, rows * (cell + pad)), (244, 240, 232))
            dr = ImageDraw.Draw(im)
            for i, (label, f) in enumerate(tiles):
                t = Image.open(f).convert("RGBA")
                t.thumbnail((cell - 16, cell - 16))
                x, y = (i % cols) * cell, (i // cols) * (cell + pad)
                im.paste(t, (x + (cell - t.width) // 2, y + pad + (cell - t.height) // 2), t)
                dr.text((x + 8, y + 6), label, fill=(30, 30, 30))
            im.save(sheet)
            L += ["## 3. prior versions", "", f"Contact sheet (LOOK at it with the Read tool): `{sheet}`",
                  f"Individual versions: `{vdir}/`", ""]
        except ImportError:
            L += ["## 3. prior versions", "", f"Pillow missing; versions exported to `{vdir}/`, no contact sheet.", ""]

    # 4. Hub rules, project memory, lessons.
    def grep_file(path, title, heading_only=False):
        out = []
        try:
            lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            return [f"{title}: NOT READABLE at {path}", ""]
        last_heading = ""
        for i, ln in enumerate(lines, 1):
            if ln.startswith("#"):
                last_heading = ln.strip("# ").strip()
            if pat.search(ln):
                if heading_only:
                    out.append((last_heading, i))
                else:
                    out.append((f"L{i}", " ".join(ln.split())[:700]))
        res = [f"### {title} ({len(out)} hit(s))", ""]
        if heading_only:
            seen_h = {}
            for h, i in out:
                seen_h.setdefault(h, i)
            res += [f"- line {i}: {h}" for h, i in seen_h.items()]
        else:
            res += [f"- {k}: {v}" for k, v in out]
        return res + [""]

    L += ["## 4. written rulings and lessons that name it", ""]
    L += grep_file(cw.HUB, "Project hub")
    for f in cw.memory_files():
        L += grep_file(f, f"Project memory: {os.path.basename(f)}")
    L += grep_file(cw.LESSONS, "lessons.md entries (read each named entry in full)", heading_only=True)
    for note in cw.CONFIG.get("standing", []):
        need = note.get("require_file")
        if paths[0].startswith(note.get("when_path_prefix", "")) and (not need or os.path.exists(os.path.join(repo, need))):
            L += [f"### {note.get('title', 'Standing notes')}", ""] + [f"- {x}" for x in note.get("lines", [])] + [""]

    # 5. The owner's own words, with provenance. Three tiers, never mixed:
    #    NAMED      they typed the object's name. Their words about it.
    #    CONTEXT    they did not name it; the assistant's turn just before was about this
    #               piece and no other. UNCERTAIN: open the transcript row before relying on it.
    #    not shown  everything else. A remark made while several pieces were on the table
    #               is not attributed to any of them.
    named, context = [], []
    for m in cw.human_messages(cw.transcripts()):
        text = m["typed"]
        if not text or m["source"] != "typed":
            continue
        where = f"{m['ts']} UTC [{m['sid']} row {m['row']}{', queued mid-turn' if m['kind'] == 'queued' else ''}]"
        flags = "".join([" RELAY (speaks about the owner in the third person; a claim about their words)" if m["relay"] else "",
                         " +pasted block not shown" if m["had_paste"] else "",
                         " +assistant text copied back, not shown" if m["copied"] else ""])
        hit = pat.search(text)
        if hit:
            ex = cw.excerpt(text, hit)
            tone = "approval?" if APPROVE.search(ex) else ("rejection?" if REJECT.search(ex) else "")
            named.append((m["ts"], where, tone, ex, flags))
        elif (slug in cw.PIECE_ALIASES and cw.dominant(m["context"], slug) and not cw.pieces_named(text)
              and len(text) < 400 and (APPROVE.search(text) or REJECT.search(text))):
            tone = "approval?" if APPROVE.search(text) else "rejection?"
            context.append((m["ts"], where, tone, " ".join(text.split())[:300], flags))
    L += ["## 5. The owner's own words (transcripts on this machine; times UTC)", "",
          f"### NAMED: they typed its name ({len(named)})", ""]
    CAP = 150
    keep = sorted(named)
    if len(keep) > CAP:   # never drop an approval or rejection to make room; say what was dropped
        tagged = [q for q in keep if q[2]]
        rest = [q for q in keep if not q[2]][-(max(0, CAP - len(tagged))):]
        L.append(f"(TRUNCATED: {len(keep) - len(tagged) - len(rest)} older untagged mention(s) omitted; every approval/rejection is kept)")
        keep = sorted(tagged + rest)
    L += [f"- {where} {tone} \"{ex}\"{flags}" for _, where, tone, ex, flags in keep] or ["- none"]
    L += ["", f"### CONTEXT ONLY, UNCERTAIN: they did not name it; the assistant's previous turn was about this piece alone ({len(context)})", "",
          "Each line is a lead, not a finding. Open the row and read what was being answered before quoting it as about this piece.", ""]
    L += [f"- {where} {tone} \"{ex}\"{flags}" for _, where, tone, ex, flags in sorted(context)] or ["- none"]
    if not named and not context:
        L.append("\nNothing found here is NOT proof there was never a ruling (sessions on other machines, chat surfaces, phone).")
    quotes = named + context
    L += ["", "## 6. Brief (the session fills this in BEFORE editing; evidence above, no recall)", "",
          "- Decided, by whom, when:", "- Rejected (do not repeat):", "- Approved version (sha, date, the owner's words):",
          "- What my planned change touches, and which ruling covers it:", ""]

    brief = os.path.join(outdir, f"{slug}-{today}.md")
    open(brief, "w").write("\n".join(L))
    print(brief)
    print(f"commits on its files: {len(shas)}; commits naming it: {len(named_commits.splitlines())}; owner named it: {len(named)}; context-only leads: {len(context)}")


if __name__ == "__main__":
    main()
