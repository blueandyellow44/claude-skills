#!/usr/bin/env python3
"""check_fetch.py - server-side request forgery from the code.

  check_fetch.py REPO

  fetch.request-url  a route handler that fetches a URL taken from the request
                     (query, params, body) FAILs high, unless the call goes
                     through a public-address guard.
  fetch.data-url     raw fetches of a non-constant URL (feeds, article links,
                     image URLs from data):
                       PASS     none, or every one goes through a guard
                       FAIL     some exist and the repo defines no guard at all
                       UNKNOWN  a guard exists but raw sites remain: read them
                     On a Cloudflare Worker the severity is low: Workers cannot
                     reach private addresses or cloud metadata, but the fetch
                     can still be an open proxy to the public internet.
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

GUARD_CALL = re.compile(r"\b(?:safeFetch|guardedFetch|publicFetch|fetchPublic|safeGet|ssrfSafeFetch)\s*\(")
GUARD_DEF = re.compile(r"169\.254|isPrivate(?:Ip|Address)?|isPublic(?:Ip|Address|Url)|assertPublic|privateRanges|BLOCKED_RANGES|ipaddr\.|net\.BlockList|blockList", re.I)
RAW_FETCH = re.compile(r"""(?<![.\w$])(?:fetch|axios(?:\.(?:get|post|request))?|got|https?\.get)\(\s*([A-Za-z_$][\w$.]*|`\$\{\s*[A-Za-z_$][\w$.]*\s*\}[^`]*`)\s*[,)]""")
ASSIGN = r"""(?:const|let|var)\s+{name}\s*=\s*([^;]{{1,400}})"""
ENV_URL = re.compile(r"^(?:c\.env|env|this\.env|ctx\.env|context\.env|process\.env|import\.meta\.env|Deno\.env)\b")


def const_origin(text, name, depth=0):
    """True when `name` holds a URL the owner controls: a literal with a fixed http(s)
    host, deployment config (env.X, process.env.X, import.meta.env.X), or a
    template whose first part is one of those (one level deep)."""
    if ENV_URL.match(name):
        return True
    base = name.split(".")[0]
    # the nearest assignment before the call (a file reuses names like `url`)
    ms = list(re.finditer(ASSIGN.format(name=re.escape(base)), text))
    if not ms:
        return False
    m = ms[-1]
    v = m.group(1).strip()
    if re.match(r"""^['"`](?:https?://[A-Za-z0-9.\-]+|/)""", v) or ENV_URL.match(v):
        return True  # a fixed host, or a same-origin path like "/api"
    if re.search(r"""['"`]https?://[A-Za-z0-9.\-]+""", v):
        return True  # an expression built around a fixed-host literal (new URL('https://..'), rewrite('https://..'))
    t = re.match(r"""^`\$\{\s*([A-Za-z_$][\w$.]*)\s*\}""", v) or re.match(r"""^([A-Za-z_$][\w$.]*)\s*(?:\?\?|\|\|)""", v)
    return bool(t) and depth < 2 and const_origin(text, t.group(1), depth + 1)


def from_request(body, name):
    base = name.split(".")[0].strip("`${} ")
    if not base:
        return False
    m = re.search(ASSIGN.format(name=re.escape(base)), body)
    if m and surface.REQ_INPUT_RX.search(m.group(1)):
        return True
    # destructured: const { url } = await c.req.json()  /  const { target: url } = ...
    for d in re.finditer(r"(?:const|let|var)\s*\{([^}]{1,300})\}\s*=\s*(?:await\s+)?([^;\n]{1,200})", body):
        names = {x.split(":")[-1].split("=")[0].strip() for x in d.group(1).split(",")}
        if base in names and (surface.REQ_INPUT_RX.search(d.group(2)) or re.match(r"(?:body|payload)\b", d.group(2))):
            return True
    return False


def main():
    repo = os.path.abspath(sys.argv[1])
    worker = bool(walk.exists_any(repo, "wrangler.toml", "wrangler.jsonc", "wrangler.json")) and not walk.exists_any(repo, "fly.toml", "railway.json", "railway.toml")
    res = []

    req_hits = []
    for h in surface.handlers(repo):
        for m in RAW_FETCH.finditer(h["body"]):
            arg = m.group(1)
            direct = surface.REQ_INPUT_RX.search(arg)
            name = re.sub(r"^`\$\{\s*|\s*\}.*$", "", arg)
            if (direct or from_request(h["body"], name)) and not GUARD_CALL.search(h["body"]):
                req_hits.append("%s:%d %s %s" % (h["file"], h["line"] + h["body"][:m.start()].count("\n"), h["method"], h["path"]))
    # direct request-to-fetch in one expression, e.g. fetch(c.req.query('url'))
    for r, ln, m in walk.find(repo, re.compile(r"\bfetch\(\s*(?:c\.req\.query|c\.req\.param|url\.searchParams\.get|req\.query)"), tests=False, served=True):
        tag = "%s:%d" % (r, ln)
        if not any(x.startswith(tag) for x in req_hits):
            req_hits.append(tag)
    if req_hits:
        res.append(result("fetch.request-url", "No fetch of a URL taken from the request", "FAIL", ledger.join_hits(sorted(set(req_hits)), 6, "; "),
                          severity="medium" if worker else "high",
                          fix="never fetch a caller-supplied URL; if required, allow-list hosts and route it through a public-address guard (outbound-fetch-guard)"))
    else:
        res.append(result("fetch.request-url", "No fetch of a URL taken from the request", "PASS", "route handlers: no request value reaches a fetch URL unguarded"))

    raw, guarded = [], 0
    for p in walk.files(repo, tests=False, served=True):
        t = walk.read_code(p)
        r = walk.rel(repo, p)
        for m in RAW_FETCH.finditer(t):
            arg = m.group(1)
            name = re.sub(r"^`\$\{\s*|\s*\}.*$", "", arg)
            if const_origin(t[:m.start()], name) or re.match(r"^(?:request|req|c\.req\.raw|event\.request|input|init)$", name):
                continue
            # inside the guard implementation itself, or a call wrapped by it
            line_start = t.rfind("\n", 0, m.start()) + 1
            line = t[line_start: t.find("\n", m.end())]
            if GUARD_CALL.search(line) or GUARD_DEF.search(t[max(0, m.start() - 1500): m.start()]):
                guarded += 1
                continue
            raw.append("%s:%d fetch(%s)" % (r, walk.line_of(t, m.start()), name[:40]))
    has_guard = any(GUARD_DEF.search(walk.read_code(p)) for p in walk.files(repo, tests=False, served=True))
    if not raw:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "PASS",
                          "%d guarded, 0 raw variable-URL fetches" % guarded if guarded else "no fetch of a non-constant URL in production code"))
    elif not has_guard:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "FAIL", ledger.join_hits(raw, 6, "; "),
                          severity="low" if worker else "high",
                          fix="route every data-URL fetch through one guard that checks URL, DNS, connect and each redirect (outbound-fetch-guard)",
                          detail="%d raw variable-URL fetch(es), no guard in the repo%s" % (len(raw), "; Worker runtime blocks private addresses" if worker else "")))
    else:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "UNKNOWN", ledger.join_hits(raw, 6, "; "),
                          reason="a guard exists but %d raw variable-URL fetch(es) do not visibly use it; read each" % len(raw)))
    blind = []
    if any(walk.files(repo, exts=(".py",), tests=False, served=True)):
        blind.append("Python request-to-fetch flows (requests/httpx/urlopen fed from FastAPI or Flask parameters) are not traced; read those handlers by hand")
    return ledger.emit(res, cannot_see=blind)


if __name__ == "__main__":
    sys.exit(main())
