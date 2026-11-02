#!/usr/bin/env python3
"""check_railway.py - Railway adapter.

  check_railway.py REPO

Railway keeps variables and networking in the dashboard, so most of what
matters is under cannot_see with the count-only command to read it.

  railway.env-dump  code that logs or returns the whole environment FAILs high:
                    every variable lands in Railway's logs or a response. The
                    whole environment is process.env, os.environ, c.env,
                    Deno.env.toObject(), dict(os.environ), {...process.env} or
                    JSON.stringify(process.env) appearing as ANY argument of a
                    log, print or response call (`console.log('prefix',
                    process.env)` counts) or as a return value (`return
                    dict(os.environ)`). Object.keys(process.env),
                    len(os.environ), `in os.environ` and process.env.NAME are
                    not the whole environment. Strings and comments never match.
  railway.config    railway.json/railway.toml parses; a start command that
                    runs a dev server (npm run dev, next dev, --reload, nodemon)
                    FAILs low. `npm start`, `npm run X`, `yarn X`, `pnpm X` and
                    `bun run X` are resolved through the nearest package.json
                    scripts (two levels), so a start script of `next dev` is
                    caught. Every railway config in the repo is read (one
                    service per folder); with several, the id carries the folder.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

SINK = re.compile(r"\b(?:console\.(?:log|info|debug|warn|error|table|dir)|logger\.\w+|log\.(?:info|debug|warn|error)|print|pprint|JSON\.stringify|"
                  r"c\.json|res\.json|res\.send|reply\.send|Response\.json|jsonify|ctx\.json)\s*\(")
RETURN = re.compile(r"\breturn\s+([^\n;]+)")
# the whole environment as a value: not followed by a member access or a call
WHOLE_ENV = re.compile(r"(?:(?<![\w$])(?:process\.env|os\.environ|Deno\.env\.toObject\(\)|os\.environ\.copy\(\))|(?<![\w.$])(?:c\.env|env))(?![\w.\[(])")
# a returned value: only the unmistakable forms (a helper that returns its own `env` object is not a dump)
WHOLE_ENV_STRICT = re.compile(r"(?<![\w$])(?:process\.env|os\.environ|Deno\.env\.toObject\(\)|os\.environ\.copy\(\))(?![\w.\[(])")
# wrappers that read names or counts only, never values
SAFE_WRAP = re.compile(r"(?:Object\.keys|Object\.getOwnPropertyNames|Reflect\.ownKeys|len|sorted|list|set|keys|tuple)\s*\(\s*$|\bin\s+$|\bnot\s+in\s+$")
DEV = re.compile(r"npm run dev|next dev|vite(?:\s|$)|nodemon|--reload|--watch|uvicorn[^\n]*--reload|flask run|ts-node-dev|tsx watch")
SCRIPT_CALL = re.compile(r"^\s*(?:npm\s+(?:run(?:-script)?\s+)?|yarn\s+(?:run\s+)?|pnpm\s+(?:run\s+)?|bun\s+(?:run\s+)?|npx\s+)?([\w:.-]+)")


def _args(text, open_idx):
    """The text inside the parentheses opening at open_idx (balanced), or None."""
    depth = 0
    for j in range(open_idx, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:j]
    return None


def dumps_env(expr, strict=False):
    """True when EXPR (an argument list or a returned value) carries the whole environment."""
    for m in (WHOLE_ENV_STRICT if strict else WHOLE_ENV).finditer(expr):
        if not SAFE_WRAP.search(expr[max(0, m.start() - 40):m.start()]):
            return True
    return False


def env_dumps(repo):
    hits = []
    for p in walk.files(repo, tests=False):
        t = walk.read_code(p, strings=False)
        rel = walk.rel(repo, p)
        for m in SINK.finditer(t):
            a = _args(t, m.end() - 1)
            if a is not None and dumps_env(a):
                hits.append("%s:%d" % (rel, walk.line_of(t, m.start())))
        for m in RETURN.finditer(t):
            if dumps_env(m.group(1), strict=True):
                hits.append("%s:%d" % (rel, walk.line_of(t, m.start())))
    return sorted(set(hits))


def resolve_start(cmd, cfg_dir, repo, depth=0):
    """Follow `npm start` / `npm run X` / `yarn X` / `pnpm X` / `bun run X` into the nearest
    package.json scripts, two levels deep. Returns (command_text, via) where via names the script."""
    m = SCRIPT_CALL.match(cmd or "")
    if not m or depth > 2:
        return cmd, None
    head = cmd.strip().split()[0] if cmd.strip() else ""
    if head not in ("npm", "yarn", "pnpm", "bun", "npx"):
        return cmd, None
    name = m.group(1)
    if head == "npx" or name in ("install", "ci", "i", "exec", "x", "dlx", "--version"):
        return cmd, None
    d = cfg_dir
    while True:
        pj = os.path.join(d, "package.json")
        if os.path.isfile(pj):
            try:
                scripts = (json.load(open(pj, encoding="utf-8")) or {}).get("scripts") or {}
            except (OSError, ValueError):
                return cmd, None
            target = scripts.get(name)
            if target is None:
                return cmd, None
            via = "%s script %r" % (walk.rel(repo, pj), name)
            deeper, via2 = resolve_start(target, cfg_dir, repo, depth + 1)
            return deeper, via if via2 is None else "%s -> %s" % (via, via2)
        if os.path.abspath(d) == os.path.abspath(repo) or not d.startswith(repo):
            return cmd, None
        d = os.path.dirname(d)


def config_checks(repo, cfgs):
    res = []
    for cp in cfgs:
        rel = walk.rel(repo, cp)
        tag = "" if len(cfgs) == 1 else "." + re.sub(r"[^A-Za-z0-9]+", "_", os.path.dirname(rel) or "root")
        t = walk.read(cp)
        start = ""
        if cp.endswith(".json"):
            try:
                d = json.loads(t)
                start = (d.get("deploy") or {}).get("startCommand", "") or ""
            except ValueError:
                res.append(result("railway.config" + tag, "Railway config runs a production server", "UNKNOWN", rel, reason="unparseable JSON"))
                continue
        else:
            m = re.search(r"""startCommand\s*=\s*(?:"([^"]*)"|'([^']*)')""", t)
            start = (m.group(1) if m and m.group(1) is not None else (m.group(2) if m else "")) or ""
        resolved, via = resolve_start(start, os.path.dirname(cp), repo)
        dev = DEV.search(resolved or "")
        if start and dev:
            res.append(result("railway.config" + tag, "Railway config runs a production server", "FAIL",
                              "%s startCommand runs a dev server (%s)%s" % (rel, dev.group(0), " via %s" % via if via else ""), severity="low",
                              fix="start the built production server (node dist/..., next start, gunicorn), not a dev server; if startCommand is `npm start`, the start script must not run one either"))
        else:
            res.append(result("railway.config" + tag, "Railway config runs a production server", "PASS",
                              "%s startCommand: no dev server%s" % (rel, "" if start else " (builder default)") + (" (resolved via %s)" % via if via else "")))
    return res


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    dumps = env_dumps(repo)
    if dumps:
        res.append(result("railway.env-dump", "The environment is never logged or returned whole", "FAIL", ledger.join_hits(dumps, 6, ", "), severity="high",
                          fix="log or return only the names you need (Object.keys(process.env) at most); rotate anything already in the logs"))
    else:
        res.append(result("railway.env-dump", "The environment is never logged or returned whole", "PASS", "production source: no whole-environment log, response or return"))
    cfgs = sorted(walk.files(repo, exts=("railway.json", "railway.toml")))
    for f in ("railway.json", "railway.toml"):
        p = os.path.join(repo, f)
        if os.path.isfile(p) and p not in cfgs:
            cfgs.append(p)
    res += config_checks(repo, cfgs)
    return ledger.emit(res, cannot_see=[
        "Railway variables: read count-only, `railway variables --kv | grep -c .` and names with `railway variables --kv | cut -d= -f1`; never plain `railway variables`",
        "Public networking (generated domain, TCP proxy) on or off: service Settings, Networking",
    ])


if __name__ == "__main__":
    sys.exit(main())
