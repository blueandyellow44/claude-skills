#!/usr/bin/env python3
"""
Two gates for map pieces in the map repo named by CITY_WALKS_REPO. Silent
everywhere else, and silent everywhere when CITY_WALKS_REPO is unset.

  piece_gate.py pre    (PreToolUse: Bash|Edit|Write|MultiEdit|NotebookEdit)
        A command or edit that can change a piece's sprite is blocked until a
        recent object record for that piece exists with its brief written.
  piece_gate.py stop   (Stop)
        A reply that calls a piece fixed is blocked until the review evidence
        for that piece is complete AND bound to the sprite on disk.

MEASURED LIMITS (2026-10-04; cases in the plugin's tests/). These gates are
tripwires on the common paths, not containment:
  - `pre` reads the command text. It sees a sprite path, a sprite script, a
    whole-set command, or a git command that restores sprites. It CANNOT see a
    write made by a script that names no sprite path (any program can open any
    file). Scripts under scripts/sprites/ are gated by name; every other
    arbitrary script is outside coverage.
  - `stop` matches English phrasing. It will miss claims it has no pattern for
    and can block a sentence that only sounds like a claim. A blocked reply can
    always be released by taking the claim back in plain words.
  - Neither gate proves that a record was read or a capture was looked at.

Reads the hook JSON on stdin. Blocks with exit 2 and the reason on stderr.
"""
import datetime, glob, json, os, re, shlex, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "piece-review", "scripts"))
import review_gate

REPO = review_gate.REPO
FOOT = os.path.join(HERE, "..", "skills", "landmark-piece", "references", "footprints.json")
RECORD_WINDOW_H = 12
MAX_STOP_BLOCKS = 2   # per session: after this the gate warns instead of blocking, so it cannot trap a session

# ---------------------------------------------------------------- scope

def inside(path, root=None):
    """True only when path is the repo or under it. A sibling such as
    '<repo>-2' shares the prefix and is NOT inside. No repo configured: never inside."""
    if not (root or REPO):
        return False
    root = os.path.realpath(root or REPO)
    try:
        return os.path.commonpath([os.path.realpath(path or "/nonexistent"), root]) == root
    except ValueError:
        return False

# ---------------------------------------------------------------- pre

SPRITE_DIRS = ("public/images/sprites/sf", ".tmp/sprites/sf-poster/raw-sf", "out/images/sprites/sf")
PATHISH = re.compile(r"""[^\s'"`;|&<>()=,]+""")
SPRITE_SCRIPT = re.compile(r"scripts/sprites/([\w.-]+)")
WHOLE_SET = re.compile(r"sprites:key|key-poster-pieces\.mjs|gen-poster-pieces\.mjs")
PLUGIN_READERS = ("object_record.py", "camera_check.py", "weight_table.py", "review_gate.py", "sweep_rulings.py")
# A segment is read-only ONLY if its first word is here and it has no output redirect into the repo.
READ_VERBS = {"ls", "file", "stat", "wc", "shasum", "sha256sum", "md5", "identify", "sips", "head", "tail",
              "cat", "grep", "rg", "find", "du", "diff", "cmp", "echo", "printf", "open", "xxd", "cd", "pwd", "test", "["}
GIT_READ = {"log", "show", "diff", "status", "blame", "ls-files", "ls-tree", "cat-file", "rev-parse", "describe", "branch", "shortlog", "grep"}


def norm_sprite(token, cwd):
    """slug if the token is a path to a sprite (keyed, raw or exported) in the repo, else None."""
    token = token.strip("'\"")
    if not token.endswith(".png") and "sprites" not in token:
        return None
    full = os.path.normpath(token if os.path.isabs(token) else os.path.join(cwd or REPO, os.path.expanduser(token)))
    full = os.path.expanduser(full)
    for d in SPRITE_DIRS:
        base = os.path.join(os.path.realpath(REPO), d)
        real = os.path.join(os.path.realpath(os.path.dirname(full)), os.path.basename(full)) if os.path.isdir(os.path.dirname(full)) else full
        for cand in (full, real):
            if os.path.dirname(cand) == base or os.path.dirname(cand) == os.path.join(REPO, d):
                return os.path.splitext(os.path.basename(cand))[0]
            if cand.rstrip("/") in (base, os.path.join(REPO, d)):
                return "*"          # the directory itself
    return None


def segments(cmd):
    """Split on shell separators. A heredoc body is its own segment, never 'read-only'."""
    cmd = re.sub(r"(?m)(^|\s)#.*$", r"\1", cmd)            # comments cannot vouch for a command
    parts, bodies = [], []
    m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", cmd)
    if m:
        head, _, rest = cmd.partition("\n")
        bodies.append(rest)
        cmd = head
    for seg in re.split(r"\s*(?:;|&&|\|\||\||\n)\s*", cmd):
        if seg.strip():
            parts.append(seg.strip())
    return parts, bodies


def git_touched(seg, cwd):
    """Sprite slugs a git command would rewrite. Runs read-only git only."""
    try:
        w = shlex.split(seg)
    except ValueError:
        w = seg.split()
    w = [x for x in w if not re.match(r"^\w+=", x)]
    if len(w) < 2 or w[0] != "git":
        return None
    i = 1
    while i < len(w) and w[i].startswith("-"):
        i += 2 if w[i] in ("-C", "-c") else 1
    sub = w[i] if i < len(w) else ""
    rest = w[i + 1:]
    if sub in GIT_READ:
        return set()
    run = lambda *a: subprocess.run(["git", "-C", REPO, *a], capture_output=True, text=True, timeout=8).stdout.split("\n")
    sprite_of = lambda paths: {os.path.splitext(os.path.basename(p))[0] for p in paths if p.startswith(SPRITE_DIRS[0] + "/") and p.endswith(".png")}
    try:
        if sub == "stash" and rest[:1] and rest[0] in ("pop", "apply"):
            return sprite_of(run("stash", "show", "--name-only", *(rest[1:2] or ["stash@{0}"])))
        if sub in ("checkout", "restore", "reset", "apply", "am", "cherry-pick", "revert", "merge", "rebase", "pull", "clean", "rm", "mv"):
            named = {s for s in (norm_sprite(x, cwd) for x in rest) if s}
            if "*" in named or (sub in ("checkout", "restore") and any(x in (".", ":/", "public", "public/images", "public/images/sprites") for x in rest)) \
               or (sub == "reset" and "--hard" in rest) or sub in ("clean",):
                # everything dirty under the sprite dir would be rewritten
                dirty = sprite_of([ln[3:] for ln in run("status", "--porcelain", "--", SPRITE_DIRS[0]) if ln])
                named = (named - {"*"}) | dirty | ({"*"} if not dirty and "*" in named else set())
            if sub in ("apply", "am", "cherry-pick", "revert", "merge", "rebase", "pull") and not named:
                return {"?"}        # cannot tell which files it rewrites
            return named
    except (subprocess.SubprocessError, OSError):
        return {"?"}
    return set()


def analyse(cmd, cwd):
    """-> (slugs to gate, whole_set: bool, unknown: [reasons])"""
    slugs, unknown, whole = set(), [], False
    segs, bodies = segments(cmd)
    if WHOLE_SET.search(cmd):
        whole = True
    for body in bodies:                         # a heredoc is code: any sprite path in it is a write
        for tok in PATHISH.findall(body):
            s = norm_sprite(tok, cwd)
            if s:
                slugs.add(s)
    for seg in segs:
        g = git_touched(seg, cwd)
        if g is not None:
            slugs |= {s for s in g if s not in ("?",)}
            if "?" in g:
                unknown.append(f"`{seg[:60]}` can rewrite files it does not name")
            continue
        words = seg.split()
        verb = os.path.basename(words[0]) if words else ""
        named = {s for s in (norm_sprite(t, cwd) for t in PATHISH.findall(seg)) if s}
        redirect_into_sprite = any(norm_sprite(t, cwd) for t in re.findall(r">>?\s*([^\s;|&]+)", seg))
        m = SPRITE_SCRIPT.search(seg)
        if m:                                   # a script from scripts/sprites/
            arg = re.search(re.escape(m.group(1)) + r"\s+([a-z][a-z0-9-]+)\b", seg)
            if arg and not arg.group(1).startswith("-"):
                slugs.add(arg.group(1))
            else:
                unknown.append(f"`{m.group(0)}` was run without naming a piece")
            slugs |= named
            continue
        if any(r in seg for r in PLUGIN_READERS) and not redirect_into_sprite:
            continue
        if verb in READ_VERBS and not redirect_into_sprite:
            continue
        slugs |= named                          # any other program that names a sprite path may write it
    return slugs, whole, unknown


def record_ok(slug):
    now = datetime.datetime.now().astimezone()
    files = sorted(glob.glob(os.path.join(REPO, ".agents", "object-records", f"{slug}-2*.md")))
    if not files:
        return False, f"no object record for {slug}"
    path = files[-1]
    text = open(path, errors="replace").read()
    gen = re.search(r"^generated: (\S+)", text, re.M)
    try:
        age_h = (now - datetime.datetime.fromisoformat(gen.group(1))).total_seconds() / 3600
    except (AttributeError, ValueError):
        return False, f"{path} has no 'generated:' line, so it was not written by a record generator (README, 'Object records'); regenerate it"
    if age_h > RECORD_WINDOW_H or age_h < -0.1:
        return False, f"the newest record for {slug} is {age_h:.0f} h old; regenerate it (records lapse after {RECORD_WINDOW_H} h)"
    if not (all(h in text for h in ("## 1. git history", "## 4. written rulings", "## 6. Brief"))
            and re.search(r"^## 5\. .*own words", text, re.M)):
        return False, f"{path} lacks the evidence sections a record carries (README, 'Object records')"
    fields = [ln.split(":", 1)[1].strip() for ln in text.split("## 6. Brief", 1)[1].splitlines() if ln.startswith("- ") and ":" in ln]
    if len(fields) < 4 or any(len(f) < 12 for f in fields[:4]) or len(set(fields[:4])) < 4:
        return False, f"the brief in {path} is not written (four distinct written answers: decided, rejected, approved version, what the change touches)"
    return True, ""


def pre(data):
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd") or ""
    slugs, whole, unknown = set(), False, []
    if data.get("tool_name") == "Bash":
        cmd = ti.get("command", "")
        if not REPO:
            return 0
        name = os.path.basename(os.path.normpath(REPO))
        if not (inside(cwd) or os.path.realpath(REPO) in cmd or REPO in cmd or name in cmd):
            return 0
        if not inside(cwd) and name + "-" in cmd and REPO + "/" not in cmd and REPO + '"' not in cmd:
            return 0
        slugs, whole, unknown = analyse(cmd, cwd if inside(cwd) else REPO)
    else:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not inside(path):
            return 0
        s = norm_sprite(path, cwd)
        if s:
            slugs.add(s)
    slugs.discard("walker")
    out = []
    if whole or "*" in slugs:
        marker = glob.glob(os.path.join(REPO, ".agents", "object-records", "WHOLE-SET-2*.md"))
        fresh = [m for m in marker if (datetime.datetime.now().timestamp() - os.path.getmtime(m)) < RECORD_WINDOW_H * 3600]
        if not fresh:
            out.append("this rewrites the WHOLE sprite set, including the pieces approved by name (landmark-piece/references/protected.json). "
                       "Work on one piece (scripts/sprites/key-piece.py <slug>), or get the owner's word and quote it in "
                       f"{os.path.join(REPO, '.agents', 'object-records', 'WHOLE-SET-' + datetime.date.today().strftime('%Y%m%d') + '.md')}.")
        slugs.discard("*")
    for why in unknown:
        out.append(why + "; name the piece, or run the piece's own script with its slug.")
    out += [why for ok, why in (record_ok(s) for s in sorted(slugs)) if not ok]
    if out:
        # The record format is in this plugin's README ("Object records").
        sys.stderr.write("piece-gate: read the object's record before changing it (README, 'Object records').\n  - "
                         + "\n  - ".join(out)
                         + "\n  Write or regenerate the record for <slug> in .agents/object-records/, read it, write its brief.\n")
        return 2
    return 0

# ---------------------------------------------------------------- stop

# Full names only. 'oracle', 'grace', 'ferry', 'palace' alone match unrelated things (Oracle docs, a person named Grace).
NAMES = {
    "ferry-building": ["ferry building"], "de-young": ["de young", "deyoung"],
    "legion-of-honor": ["legion of honor"], "saints-peter-paul": ["saints peter and paul", "saints peter & paul", "sts. peter and paul"],
    "palace-of-fine-arts": ["palace of fine arts"], "conservatory-of-flowers": ["conservatory of flowers"],
    "golden-gate-bridge": ["golden gate bridge"], "salesforce-tower": ["salesforce tower"],
    "coit-tower": ["coit tower"], "sutro-tower": ["sutro tower"], "city-hall": ["city hall"],
    "grace-cathedral": ["grace cathedral"], "cliff-house": ["cliff house"], "dutch-windmill": ["dutch windmill"],
    "columbus-tower": ["columbus tower"], "oracle-park": ["oracle park"], "alcatraz": ["alcatraz"],
    "transamerica": ["transamerica"],
}
CLAIM = re.compile(r"\b(fixed|is done|are done|is ready|are ready|ready to (ship|deploy|go)|all set|sorted|now (sits|lies|faces|reads|matches|looks)"
                   r"|restored|corrected|resolved|verified|looks (right|good|correct)|good to go|nailed)\b", re.I)
HEDGE = re.compile(r"\b(not (yet )?(fixed|verified|reviewed|done|ready|looked)|unverified|un-?reviewed|still (wrong|open|needs|off)|cannot call|can't call"
                   r"|review (is )?incomplete|not calling|have not (looked|reviewed|verified)|haven't (looked|reviewed|verified)|needs? (a )?review|pending review|if (it|this))\b", re.I)
# A sentence about the PAST or about what a document says is a report, not a claim about now.
HISTORY = re.compile(r"\b(20\d\d-\d\d-\d\d|\d\d-\d\d\b|yesterday|earlier|previously|at the time|back then|had been|was (restored|fixed|corrected|redrawn)"
                     r"|(hub|record|log|memory|lesson|commit|transcript|daily)\w* (says|said|records?|recorded|shows?|describes?|notes?)|according to|in commit|described in)\b", re.I)
PRONOUN = re.compile(r"\b(it|its|it's|they|them|this one|that one|the piece|the sprite|the building|both)\b", re.I)
CLAUSE = re.compile(r"\s*(?:;|,? but |,? though |,? although |,? while |,? whereas | \u2014 | - )\s*", re.I)


def slugs():
    try:
        return [k for k in json.load(open(FOOT)) if not k.startswith("_")]
    except (OSError, ValueError):
        return list(NAMES)


def pieces_in(text):
    low = text.lower()
    return [s for s in slugs() if re.search(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])", low) or any(n in low for n in NAMES.get(s, []))]


def last_assistant_text(data):
    if data.get("last_assistant_message"):
        return data["last_assistant_message"]
    text = ""
    try:
        for line in open(data.get("transcript_path", ""), encoding="utf-8", errors="replace"):
            if '"type":"assistant"' not in line and '"type": "assistant"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            parts = [b.get("text", "") for b in (row.get("message") or {}).get("content", []) if isinstance(b, dict) and b.get("type") == "text"]
            if any(p.strip() for p in parts):
                text = "\n".join(parts)
    except OSError:
        pass
    return text


def claimed_pieces(text):
    """[(slug, clause)]. Quoted and code text is someone else's words and is dropped."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"(?m)^\s*>.*$", " ", text)
    text = re.sub(r"\"[^\"\n]{3,}\"|“[^”\n]{3,}”", " ", text)
    out, recent = [], []      # recent: pieces named in the previous two sentences
    for sentence in re.split(r"(?<=[.!?:\n])\s+", text):
        named_here = pieces_in(sentence)
        if HISTORY.search(sentence):
            recent = (recent + [named_here])[-2:]
            continue
        for clause in CLAUSE.split(sentence):
            if not CLAIM.search(clause) or HEDGE.search(clause):
                continue
            subjects = pieces_in(clause) or (named_here if PRONOUN.search(clause) or not pieces_in(sentence) else [])
            if not subjects and PRONOUN.search(clause):
                subjects = [s for group in recent for s in group]
            for s in subjects:
                out.append((s, " ".join(clause.split())[:160]))
        recent = (recent + [named_here])[-2:]
    seen, uniq = set(), []
    for s, c in out:
        if s not in seen:
            seen.add(s); uniq.append((s, c))
    return uniq


def stop(data):
    if not inside(data.get("cwd")):
        return 0
    problems = []
    for slug, clause in claimed_pieces(last_assistant_text(data)):
        state, d, why = review_gate.check(slug)
        if state != "complete":
            problems.append(f'"{clause}"\n    {slug}: review {state.upper()}: ' + "; ".join(why[:6]))
    if not problems:
        return 0
    # Bound re-entry: never trap a session. Count blocks per session; then warn and let go.
    sid = re.sub(r"[^\w-]", "", str(data.get("session_id", "nosession")))[:64]
    counter = os.path.join(tempfile.gettempdir(), f"piece-gate-stop-{sid}.count")
    try:
        n = int(open(counter).read().strip() or 0)
    except (OSError, ValueError):
        n = 0
    if data.get("stop_hook_active") and n >= MAX_STOP_BLOCKS:
        print(json.dumps({"systemMessage": "piece-gate: NOT RESOLVED. A piece was called fixed without complete review evidence and the gate has "
                          f"stopped blocking after {n} attempts so the session can end. Treat the claim as unverified: " + problems[0].splitlines()[0]}))
        return 0
    try:
        open(counter, "w").write(str(n + 1))
    except OSError:
        pass
    sys.stderr.write(
        "piece-gate: a piece was called fixed without complete review evidence bound to its current sprite (city-walks-workflow:piece-review).\n  "
        + "\n  ".join(problems)
        + "\nEither do the review and write its files, or take the claim back in plain words: say the piece is NOT YET VERIFIED and what was and was not looked at. "
          "Taking it back releases this gate.\n")
    return 2


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        sys.exit(0)  # never break a session on a malformed payload
    sys.exit({"stop": stop, "pre": pre}.get(mode, lambda d: 0)(data))
