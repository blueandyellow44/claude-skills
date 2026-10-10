"""Resolve a working folder or a name to a project hub in the vault. Stdlib only.

A hub is `Projects/<Name>/<Name>.md`. Its frontmatter may carry:

    title: "Readable Name"
    aliases: [other name, another]
    workspaces: [~/code/alpha, ~/Alpha Site]    # folders this project owns
    last_touched: YYYY-MM-DD

How a working folder is matched, deepest ancestor first:
1. a hub that declares the folder in `workspaces:` owns it;
2. else a hub whose name, title or alias equals the folder's name owns it;
3. else the hub whose text mentions the folder as `~/path` owns it, but only
   with a clear margin (alone, or at least twice the runner-up's mentions).
No match returns (None, reason). It never guesses: a wrong hub delivered with
confidence is worse than none. Declare `workspaces:` to settle a close call.

Used by project_record.py (object-record and ruling-capture).
"""
import os
import re

HOME = os.path.expanduser("~")

# A folder directly under one of these is shared ground, not a project workspace:
# many hubs mention `~/Downloads/...`, so matching on it would crown a random hub.
SHARED_DIRS = {"Downloads", "Documents", "Desktop", "code", "Movies", "Pictures", "Music"}
# Never a project workspace at any depth.
NEVER_DIRS = {".claude", "Library"}
MIN_NAME_LEN = 4
MIN_MENTIONS = 1     # a hub that is the only one citing a workspace owns it
MENTION_MARGIN = 2   # otherwise it needs at least twice the runner-up's mentions
# Claude Code project folders that are scratch space, never a project.
SKIP_DIR_MARKERS = ("tmp-claude", "scratchpad", "Library-Application-Support")


def _read(path, cap=600_000):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(cap)
    except OSError:
        return ""


def parse_hub(text):
    """(frontmatter dict, body). Hand-rolled on purpose: no PyYAML needed, and
    hubs use only scalars, `|-` block scalars, inline lists and dash lists."""
    fm, body = {}, text
    if not text.startswith("---"):
        return fm, body
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return fm, body
    body = "\n".join(lines[end + 1:])
    key = None
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val in ("|", "|-", ">", ">-", ""):
                fm[key] = []
            elif val.startswith("[") and val.endswith("]"):
                fm[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            else:
                fm[key] = re.sub(r"\s+#.*$", "", val).strip("\"'")   # drop a YAML comment
            continue
        if key is not None and isinstance(fm.get(key), list):
            s = ln.strip()
            fm[key].append(s[2:].strip().strip("\"'") if s.startswith("- ") else s)
    return fm, body


def _scalar(v):
    return "\n".join(v) if isinstance(v, list) else (v or "")


def load_hubs(vault):
    """Every `Projects/<Name>/<Name>.md`, parsed. A hub that fails to read is
    skipped, not fatal."""
    hubs = []
    root = os.path.join(vault, "Projects")
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return hubs
    for name in names:
        path = os.path.join(root, name, name + ".md")
        if not os.path.isfile(path):
            continue
        text = _read(path)
        if not text.strip():
            continue
        fm, _ = parse_hub(text)
        aliases = fm.get("aliases") if isinstance(fm.get("aliases"), list) else []
        spaces = fm.get("workspaces") if isinstance(fm.get("workspaces"), list) else []
        hubs.append({
            "name": name,
            "title": _scalar(fm.get("title")) or name.replace("-", " "),
            "aliases": [a for a in aliases if a],
            "workspaces": [w.strip().rstrip("/") for w in spaces if w.strip()],
            "last_touched": _scalar(fm.get("last_touched")),
            "text": text,
            "rel": os.path.join("Projects", name, name + ".md"),
        })
    return hubs


def _names(hub):
    out = {hub["name"], hub["name"].replace("-", " "), hub["title"]}
    out.update(hub["aliases"])
    return {n.strip() for n in out if len(n.strip()) >= MIN_NAME_LEN}


def _norm(name):
    """'My-Project', 'my project' and 'My_Project' all compare equal, and
    apostrophes are ignored."""
    return re.sub(r"[\s_-]+", " ", re.sub(r"['’]", "", name)).strip().lower()


def match_name(hubs, name):
    """Hubs whose folder name, title or alias equals `name` (spacing, case and
    hyphens ignored). The folder name itself always counts, however short."""
    want = _norm(name)
    return [h for h in hubs if want == _norm(h["name"]) or want in {_norm(n) for n in _names(h)}]


def match_cwd(hubs, cwd, vault):
    """(hub, '~/workspace') for the hub that owns the working directory, or
    (None, reason)."""
    if not cwd:
        return None, "no working directory given"
    cwd = os.path.abspath(cwd)
    real_vault = os.path.realpath(vault)
    if (os.path.realpath(cwd) + os.sep).startswith(real_vault + os.sep):
        return None, "working dir is the vault"
    if not (cwd + os.sep).startswith(HOME + os.sep) or cwd == HOME:
        return None, "working dir is outside the home folder"
    rel_parts = os.path.relpath(cwd, HOME).split(os.sep)
    if rel_parts[0] in NEVER_DIRS:
        return None, "working dir is tooling, not a project workspace"
    unowned = []
    for depth in range(len(rel_parts), 0, -1):       # deepest ancestor first
        if depth == 1 and rel_parts[0] in SHARED_DIRS:
            break
        needle = "~/" + "/".join(rel_parts[:depth])
        declared = [h for h in hubs if needle in h["workspaces"]]
        if declared:
            return declared[0], needle
        folder = _norm(rel_parts[depth - 1])
        named = [h for h in hubs if folder in {_norm(n) for n in _names(h)}]
        if named:
            named.sort(key=lambda h: h["last_touched"], reverse=True)
            return named[0], needle
        pat = re.compile(re.escape(needle) + r"(?![\w.-])")
        scored = [(len(pat.findall(h["text"])), h["last_touched"], h) for h in hubs]
        scored = [s for s in scored if s[0]]
        if scored:
            scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
            top = scored[0][0]
            runner = scored[1][0] if len(scored) > 1 else 0
            if top >= MIN_MENTIONS and top >= MENTION_MARGIN * runner:
                return scored[0][2], needle
            weak = ", ".join("%s %d" % (s[2]["name"], s[0]) for s in scored[:3])
            unowned.append("%s (passing mentions: %s)" % (needle, weak))
    if unowned:
        return None, "no hub owns this working dir; " + "; ".join(unowned[:2]) + \
            ". Declare it in a hub's `workspaces:` if it belongs to one"
    return None, "no hub names this working dir"


def enc(path):
    """Claude Code's project-dir encoding: every non-alphanumeric becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def decode_dir(encoded, root="/"):
    """Real path for an encoded project-dir name, found by walking the
    filesystem along the encoding (the encoding is lossy, so it cannot be
    reversed by string replacement). None when the folder no longer exists."""
    rest = encoded[1:] if encoded.startswith("-") else encoded

    def walk(d, r):
        try:
            kids = os.listdir(d)
        except OSError:
            return None
        for c in kids:
            e = enc(c)
            p = os.path.join(d, c)
            if r == e and os.path.isdir(p):
                return p
            if r.startswith(e + "-") and os.path.isdir(p):
                hit = walk(p, r[len(e) + 1:])
                if hit:
                    return hit
        return None

    return walk(root, rest)
