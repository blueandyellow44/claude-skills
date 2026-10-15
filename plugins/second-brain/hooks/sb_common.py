"""Shared plumbing for the second-brain session hooks.

Every hook in this folder imports this file. It owns four things:

  vault()      where the vault is (SECOND_BRAIN_VAULT), or why it cannot be used
  manifest     a per-session record of what reached the session, file by file
  claim()      first-copy-wins, so a plugin installed twice fires once
  emit()       the JSON a Claude Code hook prints

Nothing here raises into Claude Code: a hook that fails must exit 0 and say so,
never block a session. Standard library only.

Environment:
  SECOND_BRAIN_VAULT          absolute path of the vault (required for delivery)
  SECOND_BRAIN_HOOKS=off      every hook exits silently (use when you run your own)
  SECOND_BRAIN_STATE_DIR      where session state lives (default ~/.claude/session-state)
  SECOND_BRAIN_STARTUP_CHARS  startup payload budget in characters (default 9000)
  SECOND_BRAIN_DEDUPE_OFF=1   disable first-copy-wins (tests only)
"""
import hashlib
import json
import os
import re
import sys
import time

STATE = os.path.expanduser(os.environ.get("SECOND_BRAIN_STATE_DIR") or "~/.claude/session-state")
PREFIX = "second-brain"


def hooks_off():
    return os.environ.get("SECOND_BRAIN_HOOKS", "").strip().lower() in ("off", "0", "false", "no")


def read_input():
    """The hook's JSON from stdin, or {} when it is missing or malformed."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def vault():
    """(path, None) when usable, else (None, one-line reason)."""
    raw = os.environ.get("SECOND_BRAIN_VAULT", "").strip()
    if not raw:
        return None, ("SECOND_BRAIN_VAULT is not set, so nothing from a vault was delivered. "
                      "Run the vault-setup skill, or set the variable to your vault's path.")
    path = os.path.abspath(os.path.expanduser(raw))
    if not os.path.isdir(path):
        return None, "SECOND_BRAIN_VAULT points at %s, which is not a folder." % path
    return path, None


def emit(event, context="", message=""):
    """Print the hook result. additionalContext reaches the model; systemMessage the person."""
    out = {}
    if context and event in ("SessionStart", "UserPromptSubmit", "PostToolUse"):
        out["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": context}
    if message:
        out["systemMessage"] = message
    if out:
        sys.stdout.write(json.dumps(out))


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _stat(path):
    try:
        st = os.stat(path)
        return st.st_mtime, st.st_size
    except OSError:
        return None, None


# ---------------------------------------------------------------- manifest
# One JSON line per event, each a single O_APPEND write, because hooks of the
# same event run in parallel and a shared read-modify-write file would race.

def _manifest_path(sid):
    return os.path.join(STATE, "%s.sb-manifest.jsonl" % _safe(sid))


def _safe(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(sid))[:120]


def record(sid, rec):
    if not sid:
        return False
    try:
        os.makedirs(STATE, exist_ok=True)
        line = (json.dumps(dict(rec, ts=time.time()), ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(_manifest_path(sid), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def delivered(sid, hook, kind, path, text):
    """Record one source with the bytes and hash of ITS OWN slice, not the payload's."""
    mtime, size = _stat(path)
    return record(sid, {"rec": "delivered", "hook": hook, "kind": kind, "path": path,
                        "mtime": mtime, "size": size, "bytes": len(text.encode("utf-8")),
                        "sha": sha(text) if text else ""})


def touched(sid, path, action):
    mtime, size = _stat(path)
    return record(sid, {"rec": "touched", "path": path, "action": action,
                        "mtime": mtime, "size": size})


def records(sid):
    out = []
    try:
        with open(_manifest_path(sid), encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def baseline(sid):
    """{path: (mtime, size, kind)}: the newest state this session knows for each file.
    A file this session wrote is baselined after its own write, so its edits are not drift."""
    base = {}
    for r in records(sid):
        if r.get("rec") in ("delivered", "touched", "seen") and r.get("path"):
            base[r["path"]] = (r.get("mtime"), r.get("size"), r.get("kind") or r.get("action"))
    return base


def changed(sid):
    """[(path, kind, now_mtime_or_None)] for files that moved since the baseline."""
    out = []
    for path, (mtime, size, kind) in baseline(sid).items():
        if mtime is None:
            continue
        now_m, now_s = _stat(path)
        if now_m is None or abs(now_m - mtime) > 1e-6 or now_s != size:
            out.append((path, kind, now_m))
    return out


def seen(sid, path):
    """Re-baseline a file after its change has been reported, so it is named once."""
    mtime, size = _stat(path)
    return record(sid, {"rec": "seen", "path": path, "mtime": mtime, "size": size})


# ------------------------------------------------------------- first copy wins

def claim(sid, event, key):
    """True for the first copy of this hook to handle (session, event, key); False for
    any duplicate (the plugin installed from two marketplaces, or wired twice)."""
    if os.environ.get("SECOND_BRAIN_DEDUPE_OFF") == "1":
        return True
    if not sid:
        return True
    d = os.path.join(STATE, "sb-claims", _safe(sid))
    try:
        os.makedirs(d, exist_ok=True)
        name = "%s-%s" % (event, sha(str(key)))
        fd = os.open(os.path.join(d, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        record(sid, {"rec": "duplicate_suppressed", "event": event})
        return False
    except OSError:
        return True  # cannot claim: running twice beats not running


def event_key(data, *parts):
    """A key two copies of the plugin share and two real events do not: the transcript's
    size at the moment the event fires (it grows between any two real events)."""
    try:
        size = os.path.getsize(data.get("transcript_path") or "")
    except (OSError, TypeError):
        size = -1
    return "-".join([str(p) for p in parts] + [str(size)])


# ------------------------------------------------------------------ vault reads

def read_text(path, limit=2_000_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return None


def clip(text, limit, path_hint=""):
    text = text.rstrip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit("\n", 1)[0]
    more = " (open %s for the rest)" % path_hint if path_hint else ""
    return cut + "\n  [... %d more characters not shown%s]" % (len(text) - len(cut), more)


def frontmatter(text):
    """Flat `key: value` pairs from YAML frontmatter, enough for status, last_touched,
    next_step and workspace lists. A block scalar (`key: |-`) keeps its indented lines."""
    if not text or not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out, key = {}, None
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            out[key] = [] if val in ("", "|", "|-", ">", ">-") else val.strip("'\"")
            if val in ("|", "|-", ">", ">-"):
                out[key] = ""
        elif key is not None:
            item = line.strip()
            if isinstance(out[key], list):
                out[key].append(item[2:].strip("'\"") if item.startswith("- ") else item)
            else:
                out[key] = (out[key] + " " + item).strip()
    return out


def section(text, heading):
    """The body under `## heading` up to the next `## `, or ''."""
    m = re.search(r"^##\s+%s\s*$" % re.escape(heading), text, re.M | re.I)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s+\S", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def hubs(vault_path):
    """Every project hub: Projects/<Name>/<Name>.md, skipping templates."""
    root = os.path.join(vault_path, "Projects")
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for name in names:
        path = os.path.join(root, name, name + ".md")
        if name.startswith(("_", ".")) or not os.path.isfile(path):
            continue
        text = read_text(path) or ""
        fm = frontmatter(text)
        if fm.get("status") == "template":
            continue
        out.append({"name": name, "path": path, "text": text, "fm": fm,
                    "workspaces": workspaces(fm, text)})
    return out


def workspaces(fm, text):
    """Folders a hub claims: frontmatter `workspace:`/`workspaces:` (string or list), and the
    template's `- **Workspace**: <path>` line. Only absolute or ~ paths count."""
    found = []
    for key in ("workspace", "workspaces", "folders"):
        val = fm.get(key)
        found += val if isinstance(val, list) else ([val] if val else [])
    for m in re.finditer(r"\*\*Workspace\*\*:\s*`?([^`\n]+)`?", text):
        found.append(m.group(1).strip())
    out = []
    for f in found:
        f = f.strip().strip("`'\"")
        if f.startswith(("/", "~")):
            out.append(os.path.realpath(os.path.expanduser(f)).rstrip("/"))
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def hub_for_path(vault_path, path):
    """The hub whose declared workspace contains `path` (longest wins), else the hub whose
    name equals the folder's name. Never a guess from prose: two equal claims return None."""
    real = os.path.realpath(path).rstrip("/")
    best, best_len, tie = None, -1, False
    for hub in hubs(vault_path):
        for ws in hub["workspaces"]:
            if real == ws or real.startswith(ws + os.sep):
                if len(ws) > best_len:
                    best, best_len, tie = hub, len(ws), False
                elif len(ws) == best_len and hub is not best:
                    tie = True
    if best and not tie:
        return best
    if best_len < 0:
        base = _norm(os.path.basename(real))
        named = [h for h in hubs(vault_path) if base and _norm(h["name"]) == base]
        if len(named) == 1:
            return named[0]
    return None


def hub_slice(hub, why, limit=3000):
    """Status, next step, rules, gotchas and the newest log entries of one hub."""
    fm, text = hub["fm"], hub["text"]
    lines = ["PROJECT: %s (%s)" % (hub["name"], why),
             "Hub: %s" % hub["path"],
             "Status: %s | last_touched: %s" % (fm.get("status", "?"), fm.get("last_touched", "?"))]
    if fm.get("next_step"):
        lines.append("Next step: %s" % fm["next_step"])
    for head in ("Rules", "Known gotchas", "Open questions"):
        body = section(text, head).strip()
        if body:
            lines.append("%s:\n%s" % (head.upper(), clip(body, 900)))
    log = [l for l in section(text, "Log").splitlines() if l.startswith("- ")]
    if log:
        dated = [(re.search(r"\d{4}-\d{2}-\d{2}", l), i, l) for i, l in enumerate(log)]
        newest = sorted(dated, key=lambda t: (t[0].group(0) if t[0] else "", t[1]), reverse=True)[:3]
        lines.append("LOG, the 3 most recent by date:\n" + "\n".join(clip(l, 300) for _, _, l in newest))
    return clip("\n".join(lines), limit, hub["path"])


def ledger_open(sid):
    """Open items from the session-ledger skill's file, or ''."""
    ledger_dir = os.path.expanduser(os.environ.get("SESSION_MANIFEST_DIR") or STATE)
    path = os.path.join(ledger_dir, "%s.ledger.json" % sid)
    try:
        led = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return "", path
    out = []
    if led.get("request"):
        out.append("Request: %s" % led["request"])
    for kind, label in (("requirements", "req"), ("done_when", "done-when")):
        for n, item in enumerate(led.get(kind) or [], 1):
            if isinstance(item, dict) and not item.get("done"):
                out.append("open %s %d: %s" % (label, n, item.get("text", "")))
    for item in (led.get("decisions") or [])[-5:]:
        if isinstance(item, dict):
            out.append("decided: %s (why: %s)" % (item.get("text", ""), item.get("why", "")))
    return "\n".join(out), path
