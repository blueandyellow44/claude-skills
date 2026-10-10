"""Project-aware helpers for object-record and ruling-capture. Stdlib only.

Everything project-specific is RESOLVED, never written in:

- the vault: the SECOND_BRAIN_VAULT environment variable (required; never guessed);
- the project hub: the working folder resolved by project_resolver.py (beside
  this file), or --project NAME;
- project memory and transcripts: every ~/.claude/projects/<dir> whose folder
  resolves to that hub (a project worked from several folders has several);
- per-project data (object name aliases, a default path for a bare slug, standing
  notes) from an optional `Projects/<Hub>/object-record.json` in the vault.

The transcript reader (human_messages and its provenance rules) reads Claude
Code's .jsonl transcripts.
"""
import glob, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_resolver as pc

HOME = os.path.expanduser("~")
VAULT = ""               # set by configure() from SECOND_BRAIN_VAULT
LESSONS = ""
MEMORY_ROOT = os.environ.get("MEMORY_ROOT") or os.path.join(HOME, ".claude", "projects")

# Set by configure(); module globals so the ported transcript code reads them as before.
REPO = ""
HUB = ""
HUB_NAME = ""
MEMORY_DIRS = []
MEMORY_DIR = ""          # the primary one (the repo's own); kept for old call sites
TRANSCRIPT_GLOBS = []
CONFIG = {}
PIECE_ALIASES = {}
_ALIAS_RE = {}


def vault_root():
    """The vault, from SECOND_BRAIN_VAULT. Stops with a plain message when it is
    unset or not a folder; never guessed."""
    v = os.environ.get("SECOND_BRAIN_VAULT")
    if not v:
        raise SystemExit("SECOND_BRAIN_VAULT is not set. Set it to the absolute path of your vault "
                         "(see the plugin README).")
    v = os.path.abspath(os.path.expanduser(v))
    if not os.path.isdir(v):
        raise SystemExit("vault not found: %s (check SECOND_BRAIN_VAULT)" % v)
    return v


def git_root(cwd):
    out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True).stdout.strip()
    return out or os.path.abspath(cwd)


def configure(cwd=None, project=None):
    """Resolve the project for `cwd` (or by `project` name). Returns a dict with
    hub, hub_path, repo, memory_dirs, transcript_globs, config; raises
    SystemExit with a plain message when no hub can be resolved."""
    global VAULT, LESSONS, REPO, HUB, HUB_NAME, MEMORY_DIRS, MEMORY_DIR, TRANSCRIPT_GLOBS, CONFIG, PIECE_ALIASES, _ALIAS_RE
    VAULT = vault_root()
    LESSONS = os.path.join(VAULT, "Tasks", "lessons.md")
    cwd = os.path.abspath(cwd or os.getcwd())
    hubs = pc.load_hubs(VAULT)
    if project:
        hits = pc.match_name(hubs, project)
        hub = hits[0] if hits else None
        how = "named %r" % project
    else:
        hub, how = pc.match_cwd(hubs, cwd, VAULT)
        how = "working dir " + how if hub else how
    if not hub:
        raise SystemExit("No project hub resolved (%s). Pass --project <hub name>." % how)
    REPO = git_root(cwd)
    HUB_NAME = hub["name"]
    HUB = os.path.join(VAULT, hub["rel"])
    dirs = []
    for d in sorted(os.listdir(MEMORY_ROOT)) if os.path.isdir(MEMORY_ROOT) else []:
        if any(k in d for k in pc.SKIP_DIR_MARKERS):
            continue
        path = pc.decode_dir(d)
        if not path:
            continue
        h, _ = pc.match_cwd(hubs, path, VAULT)   # sessions run inside the vault belong to no hub
        if h and h["name"] == hub["name"]:
            dirs.append(os.path.join(MEMORY_ROOT, d))
    own = os.path.join(MEMORY_ROOT, pc.enc(REPO))
    dirs.sort(key=lambda d: d != own)          # the repo's own folder first
    MEMORY_DIRS = [os.path.join(d, "memory") for d in dirs if os.path.isdir(os.path.join(d, "memory"))]
    MEMORY_DIR = MEMORY_DIRS[0] if MEMORY_DIRS else os.path.join(own, "memory")
    TRANSCRIPT_GLOBS = [os.path.join(d, "*.jsonl") for d in dirs] or [os.path.join(own, "*.jsonl")]
    try:
        with open(os.path.join(os.path.dirname(HUB), "object-record.json"), encoding="utf-8") as fh:
            CONFIG = json.load(fh)
    except (OSError, ValueError):
        CONFIG = {}
    PIECE_ALIASES = CONFIG.get("aliases", {})
    _ALIAS_RE = {s: re.compile("|".join(re.escape(a) for a in [s] + al), re.I) for s, al in PIECE_ALIASES.items()}
    return {"hub": HUB_NAME, "hub_path": HUB, "how": how, "repo": REPO, "memory_dirs": MEMORY_DIRS,
            "transcript_globs": TRANSCRIPT_GLOBS, "config": CONFIG}


def memory_files(include_index=False):
    """Project-memory files across every folder that resolves to the hub.
    MEMORY.md (the index) only on request: the sweep reads it, records do not."""
    out = []
    for d in MEMORY_DIRS:
        out += [os.path.join(d, f) for f in sorted(os.listdir(d))
                if f.endswith(".md") and (include_index or f != "MEMORY.md")]
    return out


def transcripts():
    """Every transcript file for the project: the folders that resolve to the
    hub plus the config's extra_transcript_globs (relative to ~/.claude/projects),
    each file once."""
    globs = TRANSCRIPT_GLOBS + [os.path.join(MEMORY_ROOT, x) for x in CONFIG.get("extra_transcript_globs", [])]
    return sorted({f for g in globs for f in glob.glob(g)})


def rules_files():
    """(current, history) ruling files in project memory: an existing
    `*current-rules*.md` / `*rulings-history*.md` wins, whatever its prefix;
    otherwise `<hub>-current-rules.md` / `<hub>-rulings-history.md` in the
    primary memory dir, created by the caller on first ruling."""
    def find(pat):
        for d in MEMORY_DIRS:
            hit = sorted(glob.glob(os.path.join(d, pat)))
            if hit:
                return hit[0]
        return None
    slug = HUB_NAME.lower()
    return (find("*current-rules*.md") or os.path.join(MEMORY_DIR, slug + "-current-rules.md"),
            find("*rulings-history*.md") or os.path.join(MEMORY_DIR, slug + "-rulings-history.md"))


CONTEXT_ROWS = 8          # how far back "what was on the table" looks: the last assistant turn, not the last hour
PASTE_BLOCK = re.compile(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", re.S)
# A message that speaks ABOUT the owner in the third person is a relay, not the
# owner. OWNER_NAMES: names to treat that way besides "the owner", from the
# optional SECOND_BRAIN_OWNER environment variable (comma-separated first names).
OWNER_NAMES = [n.strip() for n in os.environ.get("SECOND_BRAIN_OWNER", "").split(",") if n.strip()]
_WHO = "(?:" + "|".join([r"the owner"] + [re.escape(n) for n in OWNER_NAMES]) + ")"
RELAY = re.compile(r"\b" + _WHO + r"(?:'s|’s)? (?:direct |verbatim )?(?:correction|reports?|says|said|ruled|wants|instruction)|\bper "
                   + _WHO + r"\b|\b" + _WHO + r":\s", re.I)


def spellings(slug, extra=()):
    """clock-tower -> several ways the object is named in prose and code."""
    words = slug.replace("_", "-").split("-")
    out = {slug, " ".join(words), "".join(words)}
    if len(words) > 1:
        out.update(w for w in words if len(w) >= 5 and w not in {"tower", "house", "building", "park", "saints", "bridge", "young", "honor", "flowers", "cathedral", "golden", "windmill"})
    out.update(e for e in extra if e)
    return sorted(out, key=len, reverse=True)


def pattern(names):
    return re.compile("|".join(re.escape(n) for n in names), re.I)


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[*`_>#]| ", " ", t)).strip().lower()


def _words(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def _shingles(words, n=5):
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def pieces_named(text):
    """{slug: count} of known pieces named in a stretch of text."""
    return {s: len(r.findall(text)) for s, r in _ALIAS_RE.items() if r.search(text)}


def human_messages(globs=None):
    """Yield one dict per message a human sent, with its provenance. Nothing is
    presented as the owner's words unless it is the part they typed.

      ts, sid, row      where it is (row is the 1-based line in the .jsonl)
      kind              'user' (a turn) or 'queued' (typed while the assistant worked;
                        stored as a queue-operation row, which a user-row search misses)
      typed             the text they typed: pasted blocks removed, and sentences that are
                        verbatim copies of earlier assistant text removed
      copied            [sentences pasted back that the ASSISTANT wrote]; never the owner's words
      had_paste         a <pasted_content> block was present (its content is not in `typed`)
      source            'typed' | 'scripted' (an SDK or `claude -p` prompt; not the owner live)
      relay             True when the text speaks ABOUT the owner in the third person: a
                        controller or agent relaying them. A claim about their words, not their words.
      context           {slug: count}: pieces named by the assistant in the turn just
                        before (last CONTEXT_ROWS rows). Evidence of what was on the
                        table, never proof of what was meant.
    A message delivered twice (queued, then as a turn) is yielded once; two different
    texts are never merged.
    """
    for g in globs or TRANSCRIPT_GLOBS:
        for path in sorted(glob.glob(g)):
            sid = os.path.basename(path)[:8]
            try:
                fh = open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                corpus = set()        # 5-word runs of all assistant text so far, for copy detection
                recent = []           # (row, text) of assistant text and tool calls since the last human message
                last_seen = {}        # normalised raw text -> row, for double-delivery
                for n, line in enumerate(fh, 1):
                    is_user = '"type":"user"' in line or '"type": "user"' in line
                    is_queue = '"queue-operation"' in line and '"enqueue"' in line
                    is_asst = '"type":"assistant"' in line or '"type": "assistant"' in line
                    if not (is_user or is_queue or is_asst):
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("isSidechain"):
                        continue
                    if row.get("type") == "assistant":
                        for b in (row.get("message") or {}).get("content", []) or []:
                            if not isinstance(b, dict):
                                continue
                            if b.get("type") == "text" and b.get("text", "").strip():
                                corpus |= _shingles(_words(b["text"]))
                                recent.append((n, b["text"]))
                            elif b.get("type") == "thinking" and b.get("thinking"):
                                corpus |= _shingles(_words(b["thinking"]))   # visible thinking can be copied back too
                            elif b.get("type") == "tool_use":
                                recent.append((n, json.dumps(b.get("input", ""))[:4000]))
                        recent = recent[-CONTEXT_ROWS:]
                        continue
                    texts, kind = [], "user"
                    if row.get("type") == "queue-operation":
                        if row.get("operation") == "enqueue" and isinstance(row.get("content"), str):
                            texts, kind = [row["content"]], "queued"
                    elif row.get("type") == "user" and not row.get("isMeta"):
                        content = (row.get("message") or {}).get("content")
                        if isinstance(content, str):
                            texts = [content]
                        elif isinstance(content, list):
                            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    for raw in texts:
                        raw = raw.strip()
                        had_paste = bool(PASTE_BLOCK.search(raw))
                        t = PASTE_BLOCK.sub(" ", raw).strip()
                        if not t or t.startswith("<") or "system-reminder" in t[:200]:
                            continue
                        if t.startswith("[Request interrupted") or t.startswith("Base directory for this skill"):
                            continue
                        key = _norm(raw)
                        if key in last_seen and n - last_seen[key] <= 60:
                            last_seen[key] = n
                            continue                    # the same message, delivered again
                        last_seen[key] = n
                        typed, copied = [], []
                        # Sentence by sentence (a lead-in ending in a colon is its own piece):
                        # one whose 5-word runs are mostly already in the assistant's own text
                        # was copied back, not written by the owner.
                        for sent in re.split(r"(?<=[.!?])\s+|(?<=:)\s+|\n+", t):
                            sh = _shingles(_words(sent))
                            is_copy = len(sh) >= 3 and sum(x in corpus for x in sh) / len(sh) >= 0.6
                            (copied if is_copy else typed).append(sent.strip())
                        # A lead-in such as "this too:" stays theirs; the pasted-back sentence does not.
                        ctx = {}
                        for _, txt in recent:
                            for s, c in pieces_named(txt).items():
                                ctx[s] = ctx.get(s, 0) + c
                        yield {"ts": row.get("timestamp", "")[:16], "sid": sid, "row": n, "kind": kind,
                               "typed": " ".join(x for x in typed if x).strip(), "copied": [c for c in copied if c],
                               "had_paste": had_paste,
                               "source": "scripted" if row.get("promptSource") == "sdk" or row.get("entrypoint") == "sdk-cli" else "typed",
                               "relay": bool(RELAY.search(t)), "context": ctx}
                        recent = []


def dominant(context, slug):
    """Was `slug` THE piece on the table? Named in the last assistant turn, and at
    least twice as often as any other piece. A set-wide discussion has no dominant piece."""
    mine = context.get(slug, 0)
    others = max([c for s, c in context.items() if s != slug], default=0)
    return mine >= 1 and mine >= 2 * others


def excerpt(text, match, width=220):
    a = max(0, match.start() - width // 2)
    b = min(len(text), match.end() + width // 2)
    s = " ".join(text[a:b].split())
    return ("..." if a else "") + s + ("..." if b < len(text) else "")
