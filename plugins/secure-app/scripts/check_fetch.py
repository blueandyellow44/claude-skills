#!/usr/bin/env python3
"""check_fetch.py - server-side request forgery from the code.

  check_fetch.py REPO

  fetch.request-url  a route handler that fetches a URL taken from the request
                     (query, params, body) FAILs high, unless the call goes
                     through a public-address guard. The value is followed
                     into a local, into `new Request(url)` / `new URL(url)`, into
                     the host of a template (`https://${host}/x`), and into a
                     helper the handler calls with it (two hops, any file).
                     A request value used only as a KEY into a constant map of
                     owner-written URLs is not a request URL.
  fetch.data-url     raw fetches of a non-constant URL (feeds, article links,
                     image URLs from data):
                       PASS     none, or every one goes through a guard
                       FAIL     some exist and the repo defines no guard, or the
                                guard is a function these sites plainly do not
                                call
                       UNKNOWN  raw sites remain and the repo installs a guard
                                below the call sites (a global undici dispatcher,
                                an https Agent with its own lookup): read them
                     Files that run in the visitor's browser (React hooks,
                     'use client') are not server fetch sites.
                     On a Cloudflare Worker the severity is low: Workers cannot
                     reach private addresses or cloud metadata, but the fetch
                     can still be an open proxy to the public internet.
  Clients read: fetch, axios, got, ky, https.get/request, undici request() and
  fetch() (request() counts where undici, superagent or request is imported).
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
# a guard installed below the call sites, where a raw fetch( still goes through it
GLOBAL_GUARD = re.compile(r"setGlobalDispatcher\(|\.globalAgent\b|connect\s*:\s*\{[^}]*\blookup\b|new\s+https?\.Agent\(")
# the URL argument: an identifier, a template starting with ${var}, or a template whose HOST holds a ${var}
_ARG = r"""[A-Za-z_$][\w$.]*|`\$\{\s*[A-Za-z_$][\w$.]*\s*\}[^`]*`|`https?://[^/`\s]*\$\{[^}`]*\}[^`]*`"""
RAW_FETCH = re.compile(r"""(?<![.\w$])(?:fetch|axios(?:\.(?:get|post|put|patch|delete|head|request))?|got(?:\.(?:get|post|put|patch|delete|head))?"""
                       r"""|ky(?:\.(?:get|post|put|patch|delete|head))?|https?\.(?:get|request)|undici\.(?:request|fetch)|request)\(\s*(%s)\s*[,)]""" % _ARG)
# request(url) is an outbound client only where one is imported (undici, superagent, request)
CLIENT_IMPORT = re.compile(r"""from\s+['"](?:undici|superagent|request|request-promise\w*)['"]|require\(\s*['"](?:undici|superagent|request)['"]\s*\)""")
ASSIGN = r"""(?:const|let|var)\s+{name}\s*=\s*([^;]{{1,400}})"""
ENV_URL = re.compile(r"^(?:c\.env|env|this\.env|ctx\.env|context\.env|process\.env|import\.meta\.env|Deno\.env)\b")
INCOMING = re.compile(r"^(?:request|req|c\.req\.raw|event\.request|input|init)$")
# code that runs in the visitor's browser: React hooks, or a Next client component
BROWSER_FILE = re.compile(r"""(?:^|\n)\s*['"]use client['"]|from\s+['"]react['"]""")
HOOK_USE = re.compile(r"\buse(?:Effect|LayoutEffect|State|Ref|Callback|Memo|Reducer)\s*\(")
# helper definitions a request value can flow into: function f(a, b) / const f = async (a, b) =>
FUNC_DEF = re.compile(r"""(?:^|\n)[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"""
                      r"""|(?:^|\n)[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=\n]{0,80})?=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=\n]{0,80})?=>""")
CALL_RX = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\(([^()]*)\)")
HELPER_LINES = 80  # a helper's body is read this far past its signature
HELPER_DEPTH = 2


def _arg_name(arg):
    """The variable inside a fetch argument: `x`, `${x}...`, `https://${x}/...` all give x."""
    if arg.startswith("`"):
        m = re.search(r"\$\{\s*([A-Za-z_$][\w$.]*)", arg)
        return m.group(1) if m else ""
    return arg


def _resolve_ctor(text, name):
    """`const request = new Request(hook.url, ...)` / `const u = new URL(input)`: the URL is the first argument."""
    base = name.split(".")[0]
    if not re.match(r"^[A-Za-z_$][\w$]*$", base):
        return name
    ms = list(re.finditer(ASSIGN.format(name=re.escape(base)), text))
    if not ms:
        return name
    m = re.match(r"^new\s+(?:Request|URL)\(\s*(%s)\s*[,)]" % _ARG, ms[-1].group(1).strip())
    return _arg_name(m.group(1)) if m else name


def _balanced(text, start, open_ch, close_ch):
    depth = 0
    for i in range(start, min(len(text), start + 6000)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _const_map(text, name):
    """True when `name` is a literal map/array of owner-written fixed-host URLs (an allowlist)."""
    m = re.search(r"(?:const|let|var)\s+%s\b[^=;\n]*=\s*(?:new\s+Map\(\s*)?([\[{])" % re.escape(name), text)
    if not m:
        return False
    lit = _balanced(text, m.end() - 1, m.group(1), "}" if m.group(1) == "{" else "]")
    return bool(lit) and bool(re.search(r"""['"`]https?://[A-Za-z0-9.\-]+""", lit)) and "${" not in lit \
        and not surface.REQ_INPUT_RX.search(lit)


def _lookup_in(v):
    """`SOURCES[key]` / `SOURCES.get(key)`: the map's name, or None."""
    m = re.match(r"^([A-Za-z_$][\w$]*)\s*(?:\[|\.get\()", v)
    return m.group(1) if m else None


def const_origin(text, name, depth=0):
    """True when `name` holds a URL the owner controls: a literal with a fixed http(s)
    host, deployment config (env.X, process.env.X, import.meta.env.X), a
    template whose first part is one of those (one level deep), or a member of a
    constant map of fixed-host URLs (SOURCES[key].url)."""
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
    mapname = _lookup_in(v)
    if mapname and _const_map(text, mapname):
        return True  # one of the owner's allowlisted URLs, picked by key
    t = re.match(r"""^`\$\{\s*([A-Za-z_$][\w$.]*)\s*\}""", v) or re.match(r"""^([A-Za-z_$][\w$.]*)\s*(?:\?\?|\|\|)""", v)
    return bool(t) and depth < 2 and const_origin(text, t.group(1), depth + 1)


def from_request(body, name, text=None):
    """True when `name` (in this handler body) carries a request value. A request value used as a
    key into a constant allowlist map (SOURCES[c.req.query('feed')]) is not one; `text` is the
    whole file, where the map is defined."""
    base = name.split(".")[0].strip("`${} ")
    if not re.match(r"^[A-Za-z_$][\w$]*$", base):
        return False
    m = re.search(ASSIGN.format(name=re.escape(base)), body)
    if m and surface.REQ_INPUT_RX.search(m.group(1)):
        mapname = _lookup_in(m.group(1).strip())
        if not (mapname and _const_map(text or body, mapname)):
            return True
    # destructured: const { url } = await c.req.json()  /  const { target: url } = ...
    for d in re.finditer(r"(?:const|let|var)\s*\{([^}]{1,300})\}\s*=\s*(?:await\s+)?([^;\n]{1,200})", body):
        names = {x.split(":")[-1].split("=")[0].strip() for x in d.group(1).split(",")}
        if base in names and (surface.REQ_INPUT_RX.search(d.group(2)) or re.match(r"(?:body|payload)\b", d.group(2))):
            return True
    return False


def _params(sig):
    out = []
    for p in sig.split(","):
        p = re.sub(r"[:=].*$", "", p.strip().lstrip(".")).strip()
        out.append(p if re.match(r"^[A-Za-z_$][\w$]*$", p) else "")
    return out


def _is_client_call(match, client_ok):
    """request(x) is an outbound call only where a client that exports request is imported."""
    return client_ok or not match.group(0).startswith("request(")


class Helpers:
    """Function definitions across the served tree, for following a request value into a fetch
    in another function or file."""

    def __init__(self, repo):
        self.repo = repo
        self.defs = None

    def _build(self):
        self.defs = {}
        for p in walk.files(self.repo, tests=False, served=True):
            t = walk.read_code(p)
            r = walk.rel(self.repo, p)
            client_ok = bool(CLIENT_IMPORT.search(t))
            for m in FUNC_DEF.finditer(t):
                name = m.group(1) or m.group(3)
                sig = m.group(2) if m.group(1) else m.group(4)
                body = "\n".join(t[m.end():].split("\n")[:HELPER_LINES])
                self.defs.setdefault(name, []).append({"file": r, "line": walk.line_of(t, m.end()), "params": _params(sig),
                                                       "body": body, "client": client_ok})

    def flows_to_fetch(self, fname, argpos, depth=0):
        """(file, line) of a raw fetch inside helper `fname` whose URL is its argument number `argpos`,
        followed up to HELPER_DEPTH calls deep; None when the value never reaches a fetch or the helper
        is (or calls) a guard."""
        if self.defs is None:
            self._build()
        if GUARD_CALL.match(fname + "(") or depth > HELPER_DEPTH:
            return None
        for d in self.defs.get(fname, []):
            if argpos >= len(d["params"]) or not d["params"][argpos]:
                continue
            pname, body = d["params"][argpos], d["body"]
            if GUARD_DEF.search(body) or GUARD_CALL.search(body):
                continue  # this helper is the guard, or goes through it
            for m in RAW_FETCH.finditer(body):
                if not _is_client_call(m, d["client"]):
                    continue
                name = _resolve_ctor(body[:m.start()], _arg_name(m.group(1)))
                if _derived(body[:m.start()], name, pname):
                    return d["file"], d["line"] + body[:m.start()].count("\n")
            for c in CALL_RX.finditer(body):
                if c.group(1) in (fname, "fetch"):
                    continue
                for i, a in enumerate(c.group(2).split(",")):
                    if _derived(body[:c.start()], _arg_name(a.strip()), pname):
                        hit = self.flows_to_fetch(c.group(1), i, depth + 1)
                        if hit:
                            return hit
        return None


def _derived(text, name, pname):
    """`name` is the parameter itself, or a local assigned from an expression that uses it (new URL(p), String(p), p.trim())."""
    base = name.split(".")[0]
    if not base or not re.match(r"^[A-Za-z_$][\w$]*$", base):
        return False
    if base == pname:
        return True
    ms = list(re.finditer(ASSIGN.format(name=re.escape(base)), text))
    return bool(ms) and bool(re.search(r"\b%s\b" % re.escape(pname), ms[-1].group(1)))


def main():
    repo = os.path.abspath(sys.argv[1])
    worker = bool(walk.exists_any(repo, "wrangler.toml", "wrangler.jsonc", "wrangler.json")) and not walk.exists_any(repo, "fly.toml", "railway.json", "railway.toml")
    res = []
    texts = {}

    def ftext(rel):
        if rel not in texts:
            texts[rel] = walk.read_code(os.path.join(repo, rel))
        return texts[rel]

    helpers = Helpers(repo)
    req_hits = []
    for h in surface.handlers(repo):
        body, t = h["body"], ftext(h["file"])
        client_ok = bool(CLIENT_IMPORT.search(t))
        at = "%s:%d %s %s" % (h["file"], h["line"], h["method"], h["path"])
        if GUARD_CALL.search(body):
            continue
        for m in RAW_FETCH.finditer(body):
            if not _is_client_call(m, client_ok):
                continue
            arg = m.group(1)
            name = _resolve_ctor(body[:m.start()], _arg_name(arg))
            if surface.REQ_INPUT_RX.search(arg) or from_request(body, name, t):
                req_hits.append("%s:%d %s %s" % (h["file"], h["line"] + body[:m.start()].count("\n"), h["method"], h["path"]))
        # the request value handed to a helper that fetches it, in this file or another
        for c in CALL_RX.finditer(body):
            callee = c.group(1)
            if callee == "fetch" or GUARD_CALL.match(callee + "("):
                continue
            for i, a in enumerate(c.group(2).split(",")):
                a = a.strip()
                if not a:
                    continue
                if surface.REQ_INPUT_RX.search(a) or from_request(body, _arg_name(a), t):
                    hit = helpers.flows_to_fetch(callee, i)
                    if hit:
                        req_hits.append("%s via %s() at %s:%d" % (at, callee, hit[0], hit[1]))
                        break
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
        res.append(result("fetch.request-url", "No fetch of a URL taken from the request", "PASS", "route handlers: no request value reaches a fetch URL unguarded, directly or through a helper"))

    raw, guarded, browser = [], 0, 0
    for p in walk.files(repo, tests=False, served=True):
        t = walk.read_code(p)
        r = walk.rel(repo, p)
        if BROWSER_FILE.search(t) and (HOOK_USE.search(t) or "use client" in t[:200]):
            browser += 1  # runs in the visitor's browser: there is no server here to forge from
            continue
        client_ok = bool(CLIENT_IMPORT.search(t))
        for m in RAW_FETCH.finditer(t):
            if not _is_client_call(m, client_ok):
                continue
            before = t[:m.start()]
            name = _resolve_ctor(before, _arg_name(m.group(1)))
            if const_origin(before, name) or INCOMING.match(name):
                continue
            # inside the guard implementation itself, or a call wrapped by it
            line_start = t.rfind("\n", 0, m.start()) + 1
            line = t[line_start: t.find("\n", m.end())]
            if GUARD_CALL.search(line) or GUARD_DEF.search(t[max(0, m.start() - 1500): m.start()]):
                guarded += 1
                continue
            raw.append("%s:%d fetch(%s)" % (r, walk.line_of(t, m.start()), name[:40]))
    served_texts = [walk.read_code(p) for p in walk.files(repo, tests=False, served=True)]
    has_guard = any(GUARD_DEF.search(t) for t in served_texts)
    below = any(GLOBAL_GUARD.search(t) for t in served_texts)
    note = "; %d browser-only file(s) skipped" % browser if browser else ""
    if not raw:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "PASS",
                          ("%d guarded, 0 raw variable-URL fetches" % guarded if guarded else "no fetch of a non-constant URL in production code") + note))
    elif not has_guard:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "FAIL", ledger.join_hits(raw, 6, "; "),
                          severity="low" if worker else "high",
                          fix="route every data-URL fetch through one guard that checks URL, DNS, connect and each redirect (outbound-fetch-guard)",
                          detail="%d raw variable-URL fetch(es), no guard in the repo%s%s" % (len(raw), "; Worker runtime blocks private addresses" if worker else "", note)))
    elif below:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "UNKNOWN", ledger.join_hits(raw, 6, "; "),
                          reason="a guard is installed below the call sites (global dispatcher or agent); %d raw variable-URL fetch(es) may or may not go through it; read each" % len(raw)))
    else:
        res.append(result("fetch.data-url", "Data-supplied URLs go through a public-address guard", "FAIL", ledger.join_hits(raw, 6, "; "),
                          severity="low" if worker else "high",
                          fix="call the repo's own guard at every data-URL fetch site; a raw fetch( next to a guard function is outside it (outbound-fetch-guard)",
                          detail="a guard function exists but %d raw variable-URL fetch(es) do not call it (%d do)%s" % (len(raw), guarded, note)))
    blind = []
    if any(walk.files(repo, exts=(".py",), tests=False, served=True)):
        blind.append("Python request-to-fetch flows (requests/httpx/urlopen fed from FastAPI or Flask parameters) are not traced; read those handlers by hand")
    return ledger.emit(res, cannot_see=blind)


if __name__ == "__main__":
    sys.exit(main())
