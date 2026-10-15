#!/usr/bin/env python3
"""SessionStart: deliver the vault's orientation into the session, as content.

On a new session (source=startup or clear) it delivers, each piece bounded:
  rules       Rules-of-Engagement.md, the short always-read file
  daily       the newest Daily/YYYY-MM-DD.md: its entry titles, the last entry in full
  todo        the open items under "## Active" in Tasks/todo.md
  lessons     the newest headings in Tasks/lessons.md (headings only; never the file)
  project     the hub whose declared workspace holds the working folder, else a board
  unwrapped   how many recent sessions wrote files and ended without a wrap

After compaction or a resume (source=compact or resume) it re-delivers what the
summary may have lost: the project hub and this session's ledger.

Every source is recorded in the session manifest with its own byte count and hash,
and the person sees a one-line receipt. A missing vault says so in one line;
the session still starts.
"""
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sb_common as c  # noqa: E402

HOOK = "startup"
BUDGET = int(os.environ.get("SECOND_BRAIN_STARTUP_CHARS") or 9000)
SHARE = {"rules": 0.30, "daily": 0.17, "todo": 0.15, "lessons": 0.08, "project": 0.30}


def newest_daily(vault):
    files = sorted(glob.glob(os.path.join(vault, "Daily", "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md")))
    return files[-1] if files else None


def daily_piece(path, limit):
    text = c.read_text(path) or ""
    entries = re.split(r"^(?=### )", c.section(text, "Log") or text, flags=re.M)
    entries = [e.strip() for e in entries if e.startswith("### ")]
    name = os.path.basename(path)
    if not entries:
        return "DAILY (%s): no session entries yet." % name
    titles = "\n".join("  - " + e.splitlines()[0][4:] for e in entries[-8:])
    body = "DAILY (%s), %d session entries. Newest titles:\n%s\n\nNewest entry in full:\n%s" % (
        name, len(entries), titles, entries[-1])
    return c.clip(body, limit, path)


def todo_piece(path, limit):
    text = c.read_text(path)
    if text is None:
        return None
    active = c.section(text, "Active") or text
    items = [l.rstrip() for l in active.splitlines() if re.match(r"^(- |\* |\d+\. )", l)]
    if not items:
        return "TODO: nothing open under Active."
    shown = "\n".join("  " + c.clip(i, 160) for i in items[:15])
    more = "\n  ... %d more open items (open the file)" % (len(items) - 15) if len(items) > 15 else ""
    return c.clip("TODO, %d open:\n%s%s" % (len(items), shown, more), limit, path)


def lessons_piece(path, limit):
    heads, date = [], ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"^##\s+(\d{4}-\d{2}-\d{2})(.*)$", line)
                if m:
                    date = m.group(1)
                    rest = m.group(2).strip(" -:")
                    if rest:
                        heads.append("%s %s" % (date, rest))
                elif line.startswith("### ") and date:
                    heads.append("%s %s" % (date, line[4:].strip()))
    except OSError:
        return None
    if not heads:
        return "LESSONS: none recorded yet."
    body = "LESSONS, newest headings (search the file for the full rule):\n" + "\n".join(
        "  - " + h for h in heads[-7:])
    return c.clip(body, limit, path)


def board_piece(vault, limit):
    rows = sorted(c.hubs(vault), key=lambda h: str(h["fm"].get("last_touched", "")), reverse=True)
    rows = [h for h in rows if h["fm"].get("status", "active") in ("active", "paused")][:6]
    if not rows:
        return "PROJECT: none resolved from the working folder, and no project hubs yet."
    lines = ["PROJECT: none resolved from the working folder. Most recently touched hubs:"]
    for h in rows:
        lines.append("  - %s | %s | %s | next: %s" % (h["name"], h["fm"].get("status", "?"),
                                                   h["fm"].get("last_touched", "?"),
                                                   c.clip(str(h["fm"].get("next_step", "")), 140)))
    lines.append("A hub owns a folder when its frontmatter lists it under `workspace:` "
                 "or its body has a `- **Workspace**: <path>` line.")
    return c.clip("\n".join(lines), limit)


def unwrapped_count(days=7):
    path = os.path.join(c.STATE, "sb-sessions.jsonl")
    cutoff = datetime.datetime.now().timestamp() - days * 86400
    latest = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("ended", 0) >= cutoff and r.get("sid"):
                    latest[r["sid"]] = r  # a resumed session ends more than once; its last end counts
    except OSError:
        pass
    return sum(1 for r in latest.values() if r.get("wrote") and not r.get("wrapped"))


def build(sid, source, cwd, vault):
    """[(kind, path, text)] in delivery order."""
    pieces = []
    project = c.hub_for_path(vault, cwd) if cwd else None
    if source in ("compact", "resume"):
        moved = [m for m in c.changed(sid) if not (project and m[0] == project["path"])]
        hub_moved = project and any(m[0] == project["path"] for m in c.changed(sid))
        if moved:
            names = "\n".join("  - %s (%s)%s" % (p, k, "" if m else ": deleted or moved") for p, k, m in moved)
            pieces.append(("drift", "", "DRIFT: changed since this session last saw them, not by this "
                           "session. Re-read before editing:\n" + names))
            for p, _, _ in moved:
                c.seen(sid, p)
        if project:
            why = "re-delivered after %s%s" % (source, "; CHANGED since this session loaded it" if hub_moved else "")
            pieces.append(("project", project["path"], c.hub_slice(project, why, int(BUDGET * SHARE["project"]))))
        led, led_path = c.ledger_open(sid)
        if led:
            pieces.append(("ledger", led_path, "SESSION LEDGER, re-delivered after %s:\n%s" % (source, c.clip(led, 2500))))
        return pieces

    rules = os.path.join(vault, "Rules-of-Engagement.md")
    text = c.read_text(rules)
    if text is not None:
        pieces.append(("rules", rules, "RULES (Rules-of-Engagement.md):\n" +
                       c.clip(text, int(BUDGET * SHARE["rules"]), rules)))
    daily = newest_daily(vault)
    if daily:
        pieces.append(("daily", daily, daily_piece(daily, int(BUDGET * SHARE["daily"]))))
    for kind, rel, fn in (("todo", "Tasks/todo.md", todo_piece), ("lessons", "Tasks/lessons.md", lessons_piece)):
        path = os.path.join(vault, rel)
        piece = fn(path, int(BUDGET * SHARE[kind]))
        if piece is not None:
            pieces.append((kind, path, piece))
    if project:
        pieces.append(("project", project["path"],
                       c.hub_slice(project, "the working folder is its workspace", int(BUDGET * SHARE["project"]))))
    else:
        pieces.append(("board", os.path.join(vault, "Projects"), board_piece(vault, int(BUDGET * SHARE["project"]))))
    return pieces


def main():
    if c.hooks_off():
        return
    data = c.read_input()
    sid = data.get("session_id", "")
    source = data.get("source") or "startup"
    cwd = data.get("cwd") or os.getcwd()
    if not c.claim(sid, "SessionStart", c.event_key(data, source)):
        return
    vault, why = c.vault()
    if not vault:
        c.emit("SessionStart", "%s: %s" % (c.PREFIX, why), "%s: %s" % (c.PREFIX, why))
        return

    pieces = build(sid, source, cwd, vault)
    missing = []
    for kind, rel in (("rules", "Rules-of-Engagement.md"), ("todo", "Tasks/todo.md"), ("lessons", "Tasks/lessons.md")):
        if source not in ("compact", "resume") and not any(p[0] == kind for p in pieces):
            missing.append(rel)
    for kind, path, text in pieces:
        if path:
            c.delivered(sid, HOOK, kind, path, text)

    now = datetime.datetime.now().astimezone()
    head = ["=" * 60,
            "SECOND BRAIN: delivered by the second-brain plugin's SessionStart hook (%s)." % source,
            "Vault: %s" % vault,
            "Clock: %s" % now.strftime("%A %Y-%m-%d %H:%M %Z"),
            "These slices are already in context; open a file only when you need more than its slice.",
            "=" * 60]
    body = "\n\n".join(t for _, _, t in pieces)
    tail = []
    if source not in ("compact", "resume"):
        n = unwrapped_count()
        if n:
            tail.append("%d recent session(s) wrote files and ended without a wrap. Offer the session-wrap skill." % n)
    if missing:
        tail.append("MISSING (not delivered): %s" % ", ".join(missing))
    context = "\n".join(head) + "\n" + body + ("\n\n" + "\n".join(tail) if tail else "")

    total = sum(len(t) for _, _, t in pieces)
    receipt = "%s: delivered %d source(s), %s characters (%s)%s" % (
        c.PREFIX, len(pieces), format(total, ","), ", ".join(k for k, _, _ in pieces),
        "; missing " + ", ".join(missing) if missing else "")
    c.emit("SessionStart", context, receipt)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        sys.stdout.write(json.dumps({"systemMessage": "%s: startup hook failed (%s: %s); the session "
                                     "started without vault context." % (c.PREFIX, type(exc).__name__, exc)}))
