#!/usr/bin/env python3
"""check_app.py - ASVS-lite static checks on a repo's production code.

  check_app.py REPO

  app.cors           V3/V4: a wildcard or reflected origin together with
                     credentials FAILs high.
  app.error-leak     V16: a stack trace sent in a response FAILs medium.
  app.debug-routes   V13: a debug/seed/reset/test route with neither an
                     environment guard nor an auth reference FAILs high.
  app.signout        V7 (7.4.1): a sign-out route that only clears the browser
                     cookie, touching no server-side state, FAILs medium.
                     Emitted only when a sign-out route exists.
  app.object-writes  V8: a write route on an object id (:id, [id]) with no auth
                     or ownership reference in its handler and no auth
                     middleware over its path FAILs high. A PASS here means a
                     reference exists, not that ownership holds: that is proven
                     only by mutation-proven-tests.
Test files are excluded. Every FAIL names file:line.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import surface  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

# origin: '*', true, or a function that hands back its first argument unchanged ((o) => o, (o, c) => o, o => o)
# origin: '*', true, /.*/, or a function handing back its first argument unchanged (types and async allowed),
# or a callback that approves everything: function (o, cb) { cb(null, true) }
_REFLECT = (r"(?:['\"]\*['\"]|true|/\.\*/|(?:async\s*)?\(\s*(\w+)\s*(?::\s*[\w|<>\[\] ]+)?\s*(?:,[^)]*)?\)\s*(?::\s*[\w|<>\[\] ]+)?\s*=>\s*\1\b(?!\s*[.?(\[])"
            r"|(?:async\s+)?(\w+)\s*=>\s*\2\b(?!\s*[.?(\[])|function\s*\([^)]*\)\s*\{[^}]*\(\s*null\s*,\s*true\s*\)\s*;?\s*\})")
CORS_BAD = [
    re.compile(r"cors\(\s*\{[^}]*origin\s*:\s*" + _REFLECT + r"[^}]*credentials\s*:\s*true", re.S),
    re.compile(r"cors\(\s*\{[^}]*credentials\s*:\s*true[^}]*origin\s*:\s*" + _REFLECT, re.S),
]
ACAO_STAR = re.compile(r"""Access-Control-Allow-Origin['"]?\s*[,:]\s*['"]\*['"]""", re.I)
ACAO_REFLECT = re.compile(r"""(?:Access-Control-Allow-Origin['"]?|\.(?:setHeader|header|set)\(\s*\w+)\s*[,:]\s*(?:(?:req|request|c\.req)[\w.]*(?:headers?\.get\(|header\(|get\()\s*['"]origin['"]|req(?:uest)?\.headers(?:\.origin\b|\[\s*['"]origin['"]\s*\]))""", re.I)
STARLETTE_STAR = re.compile(r"""allow_origins\s*=\s*\[\s*['"]\*['"]\s*\][^)]*allow_credentials\s*=\s*True|allow_credentials\s*=\s*True[^)]*allow_origins\s*=\s*\[\s*['"]\*['"]\s*\]""", re.S)
ORIGIN_VAR = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*(?:req|request|c\.req)[\w.]*(?:headers?\.get\(|header\()\s*['"]origin['"]""", re.I)
ACAC_TRUE = re.compile(r"""Access-Control-Allow-Credentials['"]?\s*[,:]\s*['"]?true""", re.I)
PY_STACK_LEAK = re.compile(r"""(?:return|JSONResponse|jsonify|HTTPException)\b[^\n]{0,160}(?:traceback\.format_exc\(\)|format_exception\()""")
STACK_LEAK = re.compile(r"""(?:c\.(?:json|text|html)|res\.(?:send|json|status\(\d+\)\.(?:send|json))|new\s+Response|Response\.json|NextResponse\.json)\s*\(\s*(?:\{[^{}]{0,300}?|[^;\n)]{0,200}?)\b\w*(?:err|error|e|ex|exception)\.stack\b""")
DEBUG_PATH = re.compile(r"(?:^|/)(?:_*debug|__\w+__|phpinfo|_internal|seed|reset-?db|dev-only|test-only|dump|env)(?:/|$)", re.I)
ENV_GUARD = re.compile(r"ENVIRONMENT|NODE_ENV|import\.meta\.env\.DEV|isDev|IS_DEV|DEBUG_ROUTES|ALLOW_DEBUG|env\.DEV\b", re.I)
SIGNOUT_PATH = re.compile(r"(?:log-?out|sign-?out)", re.I)
# Server-side state: a database write, a KV/session-store delete, a revocation call. A cookie
# delete (cookies().delete, deleteCookie, Max-Age=0) only clears the browser (Phase 5 audit #9).
SERVER_STATE = re.compile(r"\.prepare\(|DELETE FROM|INSERT INTO|\b(?:KV|SESSIONS?|kv|sessionStore|store|redis|db)\w*\.(?:delete|del|put|set|destroy)\(|revoke\w*\(|invalidate\w*\(|destroySession\(|deleteSession\(|auth\.api\.signOut\(|signOut\(\s*\{[^}]*headers", re.I)
OBJ_PATH = re.compile(r"/:[A-Za-z_]*id\b|\[[A-Za-z_]*id\]|/:[A-Za-z_]+(?:/|$)|/\{[A-Za-z_]+\}", re.I)
# Identity taken from a request header the caller sets (a classroom app's authStub: X-Teacher-Id)
HEADER_IDENTITY = re.compile(r"""(?:header|headers\.get|get)\(\s*['"]x-(?:user|teacher|account|tenant|member|owner|student|admin)[-_]?(?:id|email)?['"]""", re.I)
ACCESS_HEADER = re.compile(r"Cf-Access-Jwt-Assertion|CF_Authorization")


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []

    cors_hits = []
    for p in walk.files(repo, tests=False, served=True):
        t = walk.read_code(p)
        r = walk.rel(repo, p)
        for rx in CORS_BAD + [STARLETTE_STAR]:
            for m in rx.finditer(t):
                cors_hits.append("%s:%d" % (r, walk.line_of(t, m.start())))
        if ACAC_TRUE.search(t) or re.search(r"credentials\s*:\s*true", t):
            for rx in (ACAO_STAR, ACAO_REFLECT):
                for m in rx.finditer(t):
                    cors_hits.append("%s:%d" % (r, walk.line_of(t, m.start())))
            for v in ORIGIN_VAR.finditer(t):  # origin read into a variable, then echoed back
                for m in re.finditer(r"""Access-Control-Allow-Origin['"]?\s*[,:]\s*%s\b""" % re.escape(v.group(1)), t, re.I):
                    if not re.search(r"(?:allowed|allowlist|ALLOWED|includes|has)\w*\s*\(?[^\n]{0,80}%s" % re.escape(v.group(1)), t):
                        cors_hits.append("%s:%d" % (r, walk.line_of(t, m.start())))
    if cors_hits:
        res.append(result("app.cors", "No wildcard or reflected origin with credentials", "FAIL", ledger.join_hits(sorted(set(cors_hits)), 6, ", "), severity="high",
                          fix="list the exact allowed origins; never combine * or a reflected Origin with credentials"))
    else:
        res.append(result("app.cors", "No wildcard or reflected origin with credentials", "PASS", "production source: no credentialed wildcard/reflected CORS"))

    leaks = ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, STACK_LEAK, tests=False, served=True)]
    leaks += ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, PY_STACK_LEAK, exts=(".py",), tests=False, served=True)]
    if leaks:
        res.append(result("app.error-leak", "No stack traces in responses", "FAIL", ledger.join_hits(leaks, 6, ", "), severity="medium",
                          fix="log the stack server-side; answer with a generic message and an id"))
    else:
        res.append(result("app.error-leak", "No stack traces in responses", "PASS", "production source: no .stack sent in a response"))

    hs = list(surface.handlers(repo))
    mw = surface.middleware_auth(repo)
    # environment-gated middleware (for example app.use('/api/dev/*', devOnly, ...)) guards debug routes
    env_mw = [(m.group(1).rstrip("*").rstrip("/") or "/", "%s:%d" % (r, ln)) for r, ln, m in walk.find(repo, surface.MW_RX, tests=False, served=True)
              if re.search(r"dev\w*only|only\w*dev|require\w*dev|isDev|ENVIRONMENT|NODE_ENV", m.group(2), re.I)]
    debug, objw, signout_seen, signout_bad = [], [], [], []
    for h in hs:
        at = "%s:%d %s %s" % (h["file"], h["line"], h["method"], h["path"])
        # judged on code with comments AND strings blanked: a docstring or prose saying requireAuth gates nothing
        gated = surface.AUTH_RX.search(h["code"]) or ACCESS_HEADER.search(h["body"]) or surface.covered(h["path"], mw)
        dev_gated = surface.covered(h["path"], env_mw) or any(surface.covered(p, env_mw) for p in surface.mount_paths(repo, h["file"], h["path"]))
        if DEBUG_PATH.search(h["path"]) and not ENV_GUARD.search(h["code"]) and not gated and not dev_gated:
            debug.append(at)
        if SIGNOUT_PATH.search(h["path"]):
            signout_seen.append(at)
            if not SERVER_STATE.search(h["code"]):
                signout_bad.append(at)
        if h["method"] in ("POST", "PUT", "PATCH", "DELETE", "ALL") and OBJ_PATH.search(h["path"]) and not gated:
            objw.append(at)
    routing = bool(surface.ROUTING_DEPS & set(_deps(repo)))
    if not hs and routing:
        for cid, title in (("app.debug-routes", "No unguarded debug or seed routes"), ("app.object-writes", "Write routes on objects check sign-in and ownership")):
            res.append(result(cid, title, "UNKNOWN", "0 routes recognised", reason="the repo has a routing framework but no route definition was recognised; list the routes by hand"))
        return ledger.emit(res + header_identity(repo))
    if debug:
        res.append(result("app.debug-routes", "No unguarded debug or seed routes", "FAIL", ledger.join_hits(debug, 6, "; "), severity="high",
                          fix="remove the route from production builds or guard it with an environment check AND auth"))
    else:
        res.append(result("app.debug-routes", "No unguarded debug or seed routes", "PASS",
                          "%d routes read; none debug-named without a guard" % len(hs) if hs else "the repo defines no route handlers"))
    if signout_seen:
        if signout_bad:
            res.append(result("app.signout", "Sign-out ends the session on the server", "FAIL", ledger.join_hits(signout_bad, 4, "; "), severity="medium",
                              fix="record the session as revoked server-side (hash of the cookie with its expiry) and refuse it after sign-out (ASVS 7.4.1)"))
        else:
            res.append(result("app.signout", "Sign-out ends the session on the server", "PASS", ledger.join_hits(signout_seen, 4, "; ") + ": handler touches server-side state"))
    access = [walk.rel(repo, p) for p in walk.files(repo, exts=(".md", ".sh", ".toml", ".jsonc"), tests=False)
              if re.search(r"Cloudflare Access|Zero Trust", walk.read_code(p))]
    if objw and access:
        res.append(result("app.object-writes", "Write routes on objects check sign-in and ownership", "FAIL", ledger.join_hits(objw, 8, "; "), severity="medium",
                          fix="validate the Cf-Access-Jwt-Assertion header in the Worker, so a policy change or a second hostname cannot expose these routes",
                          detail="no gate in code; the repo says Cloudflare Access fronts it (%s), which this scan cannot see" % ledger.join_hits(access, 2, ", ")))
    elif objw:
        res.append(result("app.object-writes", "Write routes on objects check sign-in and ownership", "FAIL", ledger.join_hits(objw, 8, "; "), severity="high",
                          fix="check the signed-in user owns the object before writing; prove it with mutation-proven-tests",
                          detail="no auth or ownership reference in the handler and no auth middleware over the path (read the router before reporting)"))
    else:
        n = sum(1 for h in hs if h["method"] in ("POST", "PUT", "PATCH", "DELETE", "ALL") and OBJ_PATH.search(h["path"]))
        res.append(result("app.object-writes", "Write routes on objects check sign-in and ownership", "PASS",
                          ("%d object write route(s), each with an auth/ownership reference or auth middleware (proof of ownership needs mutation-proven-tests)" % n)
                          if n else "no write route on an object id in %d route(s) read" % len(hs) if hs else "the repo defines no route handlers"))
    return ledger.emit(res + header_identity(repo))


def _deps(repo):
    import json
    d = {}
    for p in walk.all_package_jsons(repo):
        try:
            d.update(walk.deps(json.load(open(p))))
        except (OSError, ValueError):
            pass
    for f in ("requirements.txt", "pyproject.toml"):
        for name in ("fastapi", "flask", "starlette", "django"):
            if re.search(r"(?im)^\s*['\"]?%s\b" % name, walk.read(os.path.join(repo, f))):
                d[name] = "*"
    return d


def header_identity(repo):
    hits = ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, HEADER_IDENTITY, tests=False, served=True)]
    if hits:
        return [result("app.header-identity", "Identity never comes from a header the caller sets", "FAIL", ledger.join_hits(hits, 6), severity="high",
                       fix="derive the user from a verified session or signed token; a plain X-*-Id header lets anyone act as anyone",
                       detail="who the caller is must be proven, not stated")]
    return [result("app.header-identity", "Identity never comes from a header the caller sets", "PASS", "no X-User/Teacher/Account-Id header read as identity")]


if __name__ == "__main__":
    sys.exit(main())
