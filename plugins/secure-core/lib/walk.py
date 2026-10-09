"""walk.py - read a repo's own source the same way in every check.

Skips dependencies, build output, VCS and snapshot folders. `tests=False`
also skips test files and fixtures, so a check about production behavior is
not tripped by a test that deliberately exercises the bad case.
"""
import os
import re

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", ".next", ".open-next", ".wrangler",
    ".backups", "coverage", "vendor", ".venv", "venv", "__pycache__", ".turbo", ".vercel",
    ".svelte-kit", ".cache", ".parcel-cache", ".output",
}
# Only at the repo root: the suite's own output folders (a src/security/ module is still read).
ROOT_SKIP = {"security", "validation"}
CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".gs", ".html", ".vue", ".svelte")
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|__mocks__|fixtures?|e2e|spec|cypress|playwright)(/|$)|\.(test|spec)\.[a-z]+$"
                       r"|(^|/)(fakes?|mocks?|stubs?)[A-Z_.\-][^/]*$")
# Local tooling a stranger cannot reach: one-off scripts, evals, notebooks, docs.
# Excluded from the app-layer checks (who can make the app spend or leak),
# still read by the inventory and the secret scan.
NOT_SERVED = re.compile(r"^(scripts|tools|bin|evals?|notebooks|docs|examples|bench|benchmarks)/")


_GIT_CACHE = {}


def git_files(repo):
    """Tracked plus untracked-but-not-ignored files, or None outside git.
    The repo's own source is what git would ship; ignored folders (build
    output, agent scratch copies) are not the repo's code."""
    key = os.path.abspath(repo)
    if key not in _GIT_CACHE:
        import subprocess
        r = subprocess.run(["git", "-C", key, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, text=True)
        top = subprocess.run(["git", "-C", key, "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
        if r.returncode != 0 or os.path.realpath(top) != os.path.realpath(key):
            _GIT_CACHE[key] = None  # not a repo root (a sub-folder or no git): walk the tree
        else:
            _GIT_CACHE[key] = {f for f in r.stdout.split("\0") if f}
    return _GIT_CACHE[key]


def files(repo, exts=CODE_EXT, tests=True, extra_skip=(), served=False):
    """Source files of the repo. Skips dependency, build, VCS and snapshot
    folders and every dot-folder (.agents, .claude, .vscode: scratch copies
    and tooling, not the app). Inside a git repo, only files git tracks or
    would track are read."""
    skip = SKIP_DIRS | set(extra_skip)
    allowed = git_files(repo)
    for root, dirs, names in os.walk(repo):
        at_root = os.path.abspath(root) == os.path.abspath(repo)
        dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith(".")
                         and not (at_root and d in ROOT_SKIP))
        for n in sorted(names):
            if exts and not n.endswith(exts):
                continue
            p = os.path.join(root, n)
            r = rel(repo, p)
            if allowed is not None and r not in allowed:
                continue
            if not tests and TEST_PATH.search(r):
                continue
            if served and NOT_SERVED.search(r):
                continue
            yield p


def rel(repo, path):
    return os.path.relpath(path, repo).replace(os.sep, "/")


def read(path, limit=2_000_000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def find(repo, pattern, exts=CODE_EXT, tests=True, flags=0, served=False):
    """Yield (relpath, line, match) for every regex match in the repo's source."""
    rx = re.compile(pattern, flags) if isinstance(pattern, str) else pattern
    for p in files(repo, exts, tests, served=served):
        t = read_code(p)
        for m in rx.finditer(t):
            yield rel(repo, p), line_of(t, m.start()), m


def exists_any(repo, *relpaths):
    return [r for r in relpaths if os.path.exists(os.path.join(repo, r))]


def package_json(repo):
    import json
    p = os.path.join(repo, "package.json")
    try:
        data = json.load(open(p, encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def deps(pkg):
    if not isinstance(pkg, dict):
        return {}  # a malformed package.json ([] or a string) has no dependencies to read
    d = {}
    for k in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        d.update(pkg.get(k) or {})
    return d


def all_package_jsons(repo):
    """Root plus workspace package.json files (monorepos keep the app in a subfolder)."""
    for p in files(repo, exts=("package.json",), tests=False):
        yield p


def strip_comments(text, path="", strings=True):
    """Blank out comments, keeping every newline (so line numbers hold) and
    every string literal (so 'https://x' survives). A comment saying
    '// TODO: add a rate limit' must never satisfy a check (Phase 5 audit)."""
    py = path.endswith(".py")
    out, i, n = [], 0, len(text)
    quote = None
    while i < n:
        ch = text[i]
        if quote:
            if ch == "\\" and i + 1 < n:
                out.append(text[i:i + 2] if strings else "  ")
                i += 2
                continue
            if ch == quote:
                quote = None
                out.append(ch)
            else:
                out.append(ch if strings or ch == "\n" else " ")
            i += 1
            continue
        if py and text.startswith(('"""', "'''"), i):  # docstrings and triple-quoted strings
            q3 = text[i:i + 3]
            j = text.find(q3, i + 3)
            j = n if j < 0 else j + 3
            seg = text[i:j]
            out.append(seg if strings else "".join(c if c == "\n" else " " for c in seg))
            i = j
            continue
        if ch in "'\"`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if not py and ch == "/" and not text.startswith(("//", "/*"), i) and _regex_context(out):
            j = _regex_end(text, i)  # a regex literal (/'/g) is not a quote or a comment start
            out.append(text[i:j] if strings else "/" + " " * max(0, j - i - 1))
            i = j
            continue
        if py and ch == "#":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        if not py and text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        if not py and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(c if c == "\n" else " " for c in text[i:j]))
            i = j
            continue
        if path.endswith((".html", ".vue", ".svelte")) and text.startswith("<!--", i):
            j = text.find("-->", i + 4)
            j = n if j < 0 else j + 3
            out.append("".join(c if c == "\n" else " " for c in text[i:j]))
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _regex_context(out):
    """True when a '/' here starts a regex literal: after ( , = : [ ! & | ? { } ; or return."""
    k = len(out) - 1
    while k >= 0 and out[k] in " \t\n":
        k -= 1
    if k < 0:
        return True
    if out[k] in "(,=:[!&|?{};":
        return True
    tail = "".join(out[max(0, k - 5):k + 1])
    return tail.endswith("return")


def _regex_end(text, i):
    j, n, in_class = i + 1, len(text), False
    while j < n and text[j] != "\n":
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            j += 1
            while j < n and text[j].isalpha():
                j += 1
            return j
        j += 1
    return i + 1  # not a regex after all: treat as a plain slash


def read_code(path, strings=True):
    """The file's text with comments blanked, for every check that judges code.
    strings=False also blanks string contents: for evidence that must be an
    identifier or a call (a cap, a limiter), never prose in a prompt."""
    t = read(path)
    if path.endswith(CODE_EXT):
        return strip_comments(t, path, strings)
    return t
