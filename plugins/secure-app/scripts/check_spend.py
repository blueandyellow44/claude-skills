#!/usr/bin/env python3
"""check_spend.py - abuse and spend: who can make this app spend money or
forward traffic, and what stops them.

  check_spend.py REPO

  spend.cap.<provider>  a paid API called with no spend-cap reference in the
                        calling file or a file it imports FAILs high.
  spend.unset-cap       a cap read from config that falls back to unlimited
                        when unset (|| Infinity, ?? 1e9, "if (!cap) proceed")
                        FAILs high. An unset cap must mean paused.
  spend.open-proxy      a route that takes request input and forwards it to a
                        third-party host with no bounds check in the handler
                        FAILs medium (a map app's /api/route and
                        /api/reverse before its service-area bounds).
  spend.per-client      forwarding or paid routes exist and nothing in the repo
                        limits a single client (no limiter, no 429) FAILs medium.
  spend.llm-params      max_tokens, n or model taken straight from the request
                        FAILs medium (a caller sets your bill).
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

CAP_FALSY_SKIP = re.compile(r"""if\s*\(\s*[\w.]*(?:cap|limit|budget|ceiling)\w*\s*&&""", re.I)
UNLIMITED_VALUE = re.compile(r"""\b\w*(?:cap|limit|budget|ceiling|max)\w*\s*[:=]\s*(?:Number\.MAX_SAFE_INTEGER|Number\.POSITIVE_INFINITY|Infinity|1e\d{2,}|float\(['"]inf['"]\)|math\.inf)""", re.I)
UNLIMITED = re.compile(r"""(?:(?:cap|limit|budget|ceiling|max)\w*\s*(?:\)|\b)\s*(?:\|\||\?\?)\s*(?:Infinity|Number\.(?:MAX_SAFE_INTEGER|POSITIVE_INFINITY)|1e\d+|9{4,}))|if\s*\(\s*!\s*[\w.]*(?:cap|limit|budget|ceiling)\w*\s*\)\s*(?:return\s+(?:await\s+)?next\(\)|\{\s*//\s*no\s+cap)""", re.I)
BOUNDS = re.compile(r"bounds|bbox|within|inBounds|isIn[A-Z]\w*|clamp|validate|schema|zod|\.parse\(|safeParse|MAX_|maxLength|\.slice\(0|allowlist|allowed|isFinite|Math\.(?:min|max)\(|> ?\d{2,}|< ?-?\d{2,}|too (?:far|long|many)", re.I)
# A limiter is code that refuses: a limiter object or binding, or a 429 the app itself RETURNS.
# Reading an upstream's 429 (`if (r.status === 429)`) limits nothing.
# A limiter is code that refuses: a limiter object used or built, a rate-limit binding, or a 429 the app
# itself RETURNS. Not an upstream's 429 (isThrottled(res.status), KalshiRateLimitError), not an error class
# named *LimitError, not a test helper that resets one (Phase 5 audit, second pass).
LIMITER = re.compile(r"\b\w*[Ll]imiter\b\s*\.(?:hit|check|take|consume|limit|allow|tryAcquire|acquire|increment)\s*\(|\bnew\s+\w*[Ll]imiter\s*\(|\b(?:const|let|var)\s+\w*[Ll]imiter\s*="
                     r"|\benv\.\w*RATE_?LIMIT\w*\.limit\s*\(|\[\[unsafe\.bindings\]\]|\[\[ratelimits\]\]|\bratelimits\s*[=:]"
                     r"|\b(?:return|c\.json|c\.text|new\s+Response|Response\.json|HTTPException)\b[^;\n]{0,160}\b429\b|\bres\.status\(\s*429|\bstatus(?:_code)?\s*:\s*429\b|\bstatus_code\s*=\s*429\b|@limiter\.limit|slowapi")
# Per CLIENT: the limiter's neighbourhood names who is being limited (an IP, a user, a session, an account).
CLIENT_KEY = re.compile(r"cf-connecting-ip|x-forwarded-for|x-real-ip|\bip\b|clientIp|remoteAddr|userId|user\.id|user_id|accountId|account_id|teacherId|session|sub\b|perClient|per_client|keyFor|clientKey", re.I)
LLM_PARAMS = re.compile(r"""\b(max_tokens|maxTokens|max_output_tokens|\bn)\s*:\s*(?:body|req\.body|req\.query|payload|c\.req|reqBody|requestBody)\b[\w.\[\]'"]*""")
LLM_MODEL = re.compile(r"""\bmodel\s*:\s*(?:body|req\.body|req\.query|payload|reqBody|requestBody)\.\w+""")
# A cap that guards: compared against, or a cap function called. Not an import, a type, or a value
# echoed back to the client (a coaching app's index.ts returns DAILY_OUTPUT_BUDGET for display only).
GUARD_SHAPE = re.compile(r"\s(?:<=?|>=?)\s|\bif\s*\(.*\b\w*(?:cap|limit|budget|quota|max)\w*|\b\w*(?:[Cc]ap|[Ll]imit|[Bb]udget|[Qq]uota)\w*\s*\(|\bthrow\b|raise\b|Math\.min\(", re.I)
CAP_MW_NAME = re.compile(r"(?:require|enforce|check|with)\w*(?:[Cc]aps?|[Bb]udget|[Ss]pend|[Qq]uota)|(?:[Cc]aps?|[Bb]udget|[Ss]pend|[Qq]uota)\w*(?:[Gg]uard|[Gg]ate|[Mm]iddleware)")
CAP_CALL = re.compile(r"\bnew\s+\w*(?:Spend|Budget|Quota|Cost)\w*\s*\(|\b(?:await\s+)?[\w.]*(?:[Ss]pend|[Bb]udget|[Qq]uota|[Cc]aps?|[Ll]imits?|[Mm]eter)\w*\s*\.\s*(?:reserve|check|assert|enforce|consume|begin|charge|allow)\w*\s*\(|\b(?:check|assert|enforce|over|within|reserve|charge|consume|guard)\w*(?:[Ss]pend|[Bb]udget|[Qq]uota|[Cc]aps?|[Ll]imits?)\w*\s*\(")
CLIENT_CODE = re.compile(r"(?:^|/)(?:components|hooks|public|client|frontend)/|\.(?:tsx|jsx|vue|svelte|html)$")
# `import type` brings no code: it is not a call path (a coaching app's prose.ts imports a TYPE from coach.ts)
IMPORT_REL = re.compile(r"""(?:^|[;\n])\s*(?:import\s+(?!type\b)(?:[^'";]*?\s+from\s+)?|export\s+(?!type\b)[^'";]*?\s+from\s+|[^\n]*?\brequire\(\s*)['"](\.{1,2}/[^'"]+)['"]""")
EXTS = ("", ".ts", ".tsx", ".js", ".mjs", "/index.ts", "/index.js")
JS_TO_TS = re.compile(r"\.(?:js|mjs)$")


DESTRUCT = re.compile(r"""(?:const|let|var)\s*\{([^}]{1,300})\}\s*=\s*(?:await\s+)?([^;\n]{1,200})""")
LLM_KEYS = re.compile(r"""\b(model|max_tokens|maxTokens|max_output_tokens|n)\s*(?::\s*([A-Za-z_$][\w$]*))?\s*[,}\n]""")


def _destructured_llm(repo):
    """`const { model, max_tokens } = await c.req.json()` then `{ model, max_tokens: max_tokens }` in the provider call."""
    out = []
    for p in walk.files(repo, tests=False, served=True):
        t = walk.read_code(p)
        if not re.search(r"messages\.create|chat\.completions\.create|generateContent|max_tokens|maxTokens", t):
            continue
        names = set()
        for m in DESTRUCT.finditer(t):
            if surface.REQ_INPUT_RX.search(m.group(2)) or re.match(r"(?:body|payload|reqBody|requestBody)\b", m.group(2)):
                names |= {x.split(":")[-1].split("=")[0].strip() for x in m.group(1).split(",")}
        if not names:
            continue
        for call in re.finditer(r"(?:messages\.create|chat\.completions\.create|generateContent)\s*\(\s*\{([^}]{1,600})\}|body:\s*JSON\.stringify\(\s*\{([^}]{1,600})\}", t):
            inner = call.group(1) or call.group(2) or ""
            for km in LLM_KEYS.finditer(inner + ","):
                val = km.group(2) or km.group(1)
                if val in names:
                    out.append("%s:%d" % (walk.rel(repo, p), walk.line_of(t, call.start())))
                    break
    return out


def _near_client_key(repo, rel, ln, span=12):
    """The limiter is keyed by a client: a client key within `span` lines, or in the function it calls."""
    lines = walk.read_code(os.path.join(repo, rel)).splitlines()
    window = "\n".join(lines[max(0, ln - 1 - span): ln + span])
    if CLIENT_KEY.search(window):
        return True
    # a call like geoUpstreamAllowed(c): look inside that function's body in the same file
    for name in re.findall(r"\b(\w+)\s*\(", window):
        m = re.search(r"(?:function\s+%s\s*\(|const\s+%s\s*=)" % (re.escape(name), re.escape(name)), "\n".join(lines))
        if m:
            body = "\n".join(lines)[m.start(): m.start() + 2500]
            if CLIENT_KEY.search(body):
                return True
    return False


def _comment_line(repo, rel, ln):
    lines = walk.read_code(os.path.join(repo, rel)).splitlines()
    s = lines[ln - 1].lstrip() if 0 < ln <= len(lines) else ""
    return s.startswith(("//", "*", "/*", "#", "<!--"))


def _importers(repo):
    """rel -> files that import it with a relative import (one level)."""
    out = {}
    for p in walk.files(repo, tests=False, served=True):
        src = walk.rel(repo, p)
        for g in imported(repo, src)[1:]:
            out.setdefault(g, set()).add(src)
    return out


def imported(repo, rel):
    """The file plus the relative files it imports (one level)."""
    out = [rel]
    t = walk.read_code(os.path.join(repo, rel))
    for m in IMPORT_REL.finditer(t):
        base = os.path.normpath(os.path.join(os.path.dirname(rel), m.group(1)))
        if not os.path.isfile(os.path.join(repo, base)):
            base = JS_TO_TS.sub("", base)  # TypeScript ESM imports name the .js that the .ts becomes
        for e in EXTS:
            cand = base + e
            if os.path.isfile(os.path.join(repo, cand)):
                out.append(cand.replace(os.sep, "/"))
                break
    return out


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    own_hosts = set()
    for f in ("wrangler.toml", "wrangler.jsonc"):
        own_hosts |= set(re.findall(r"""pattern\s*[=:]\s*["']([^"'/*]+)""", walk.read_code(os.path.join(repo, f))))

    sites = {}
    for host, prov in surface.PAID_HOSTS.items():
        for r, ln, _ in walk.find(repo, re.escape(host), tests=False, served=True):
            sites.setdefault(prov, []).append((r, ln))
    # SDK clients call the provider with no host string in the code (Phase 5 audit #8).
    for pkg, prov in surface.SDK_PAID.items():
        rx = re.compile(r"""(?:from\s+['"]%s['"]|require\(\s*['"]%s['"]\s*\)|^\s*(?:import|from)\s+%s\b)""" % ((re.escape(pkg),) * 3), re.M)
        for r, ln, _ in walk.find(repo, rx, tests=False, served=True):
            sites.setdefault(prov, []).append((r, ln))
    importers = _importers(repo)
    has_routes = any(True for _ in surface.handlers(repo))
    for prov, where in sorted(sites.items()):
        files = sorted({r for r, _ in where})
        caps, uncapped = [], []

        def guarded_here(rel):
            """Cap enforcement written in THIS file: a guard-shaped cap line, or a call to a cap function
            (overDailySpendCap(), checkBudget(), gate.reserve()). A guard in some imported module does
            not show this caller uses it (a coaching app's prose.ts, 2026-10-09)."""
            if walk.TEST_PATH.search(rel) or rel.endswith((".tsx", ".jsx", ".html", ".vue", ".svelte")):
                return []
            t2 = walk.read_code(os.path.join(repo, rel), strings=False)
            lines = t2.splitlines()
            out = []
            for m in surface.CAP_RX.finditer(t2):
                ln = walk.line_of(t2, m.start())
                if GUARD_SHAPE.search(lines[ln - 1]) and not re.match(r"\s*(?:import|export\s+(?:type|interface)|from\s+\S+\s+import)\b", lines[ln - 1]):
                    out.append("%s:%d" % (rel, ln))
            for m in CAP_CALL.finditer(t2):
                out.append("%s:%d" % (rel, walk.line_of(t2, m.start())))
            return out
        cap_mw = [(m.group(1).rstrip("*").rstrip("/") or "/", "%s:%d" % (r, ln)) for r, ln, m in walk.find(repo, surface.MW_RX, tests=False, served=True)
                  if CAP_MW_NAME.search(m.group(2))]

        def mw_covered(rel, callee=None):
            """Every route in this file that calls the paid client sits under a cap middleware mounted with
            app.use(path, ..., requireCaps)."""
            hs = [h for h in surface.handlers(repo) if h["file"] == rel]
            if callee:
                names = set()
                for m in re.finditer(r"""import\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]""", walk.read_code(os.path.join(repo, rel))):
                    base = os.path.normpath(os.path.join(os.path.dirname(rel), m.group(2)))
                    if os.path.splitext(callee)[0] in (base, JS_TO_TS.sub("", base)):
                        names |= {x.split(" as ")[-1].strip() for x in m.group(1).split(",") if x.strip()}
                if names:
                    # one level of same-file helpers: function draft() { ... llmCall() ... } called by the route
                    code = walk.read_code(os.path.join(repo, rel))
                    defs = list(re.finditer(r"(?m)^(?:export\s+)?(?:async\s+)?function\s+(\w+)|^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>", code))
                    helpers = set()
                    for i, d in enumerate(defs):
                        body = code[d.end(): defs[i + 1].start() if i + 1 < len(defs) else len(code)]
                        if any(re.search(r"\b%s\s*\(" % re.escape(n), body) for n in names):
                            helpers.add(d.group(1) or d.group(2))
                    calls = names | helpers
                    direct = [h for h in hs if any(re.search(r"\b%s\s*\(" % re.escape(n), h["code"]) for n in calls)]
                    hs = direct or hs  # nothing traced: judge every route in the file
            if not hs or not cap_mw:
                return []
            hits = []
            for h in hs:
                paths = [h["path"]] + surface.mount_paths(repo, rel, h["path"])
                at = next((surface.covered(p, cap_mw) for p in paths if surface.covered(p, cap_mw)), None)
                if not at:
                    return []
                hits.append(at)
            return sorted(set(hits))
        for f in files:
            own = guarded_here(f) or mw_covered(f)
            ups = sorted(u for u in importers.get(f, ()) if not walk.TEST_PATH.search(u))
            if own or not ups:
                (caps.extend(own) if own else uncapped.append(f))
                continue
            # a shared client module: every caller must enforce the cap itself
            for u in ups:
                found = guarded_here(u) or mw_covered(u, f)
                (caps.extend(found) if found else uncapped.append(u))
        cid = "spend.cap.%s" % re.sub(r"[^a-z0-9]+", "-", prov.lower()).strip("-")
        if caps and not uncapped:
            res.append(result(cid, "%s spend has a cap" % prov, "PASS", "cap reference at %s" % ledger.join_hits(sorted(set(caps)), 3, ", "),
                              detail="a reference, not a proof: confirm the cap is enforced before the call with a mutation-proven test"))
        else:
            res.append(result(cid, "%s spend has a cap" % prov, "FAIL", ledger.join_hits(sorted(set(uncapped)), 4, ", "), severity="high" if has_routes else "medium",
                              fix="add a daily spend cap checked before every call, paused (not unlimited) when unset",
                              detail=None if has_routes else "no public route found: spend here is driven by schedules or scripts, not by strangers"))

    unl = ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, UNLIMITED, tests=False, served=True)]
    unl += ["%s:%d (cap enforced only when set)" % (r, ln) for r, ln, _ in walk.find(repo, CAP_FALSY_SKIP, tests=False, served=True)]
    unl += ["%s:%d (a cap set to unlimited)" % (r, ln) for r, ln, _ in walk.find(repo, UNLIMITED_VALUE, tests=False, served=True)]
    if unl:
        res.append(result("spend.unset-cap", "An unset cap means paused, not unlimited", "FAIL", ledger.join_hits(unl, 6, ", "), severity="high",
                          fix="treat a missing or unparseable cap as 0 (paused) and say so in the response"))
    elif sites:
        res.append(result("spend.unset-cap", "An unset cap means paused, not unlimited", "PASS", "no cap falls back to unlimited in production source"))

    hs = list(surface.handlers(repo))
    proxies, forwarders = [], []
    for h in hs:
        if not surface.REQ_INPUT_RX.search(h["body"]):
            continue
        hosts = {m.group(1) for m in surface.URL_HOST_RX.finditer(h["body"])} - own_hosts
        calls_out = hosts and re.search(r"\bfetch\(|axios|got\(", h["body"])
        if calls_out:
            forwarders.append(h)
            if not BOUNDS.search(h["body"]):
                proxies.append("%s:%d %s %s -> %s" % (h["file"], h["line"], h["method"], h["path"], ",".join(sorted(hosts))[:60]))
    if proxies:
        res.append(result("spend.open-proxy", "Routes that forward to other services bound their input", "FAIL", ledger.join_hits(proxies, 6, "; "), severity="medium",
                          fix="bound every forwarded value (area, length, count) and refuse anything outside before calling out"))
    elif forwarders:
        res.append(result("spend.open-proxy", "Routes that forward to other services bound their input", "PASS",
                          "%d forwarding route(s), each with a bounds check in the handler" % len(forwarders)))
    if forwarders or sites:
        # Only server-side evidence counts: a 429 handled in a browser component limits nothing.
        lim = [("%s:%d" % (r, ln)) for r, ln, _ in walk.find(repo, LIMITER, exts=walk.CODE_EXT + (".toml", ".jsonc", "wrangler.json"), tests=False, served=True)
               if not CLIENT_CODE.search(r) and not re.match(r"""\s*['"]use client['"]""", walk.read_code(os.path.join(repo, r)))
               and not _comment_line(repo, r, ln) and _near_client_key(repo, r, ln)]
        if lim:
            res.append(result("spend.per-client", "One client cannot drive unbounded calls", "PASS", "limiter reference at %s" % ledger.join_hits(lim, 3, ", ")))
        else:
            res.append(result("spend.per-client", "One client cannot drive unbounded calls", "FAIL",
                              "%d paid provider(s), %d forwarding route(s), no limiter or 429 anywhere" % (len(sites), len(forwarders)), severity="medium",
                              fix="add a per-client ceiling in code (in memory if the privacy page promises no storage) and a zone rate-limit rule as a backstop"))

    llm = ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, LLM_PARAMS, tests=False, served=True)] + ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, LLM_MODEL, tests=False, served=True)]
    llm += _destructured_llm(repo)
    if llm:
        res.append(result("spend.llm-params", "The caller cannot set model, n or max_tokens", "FAIL", ledger.join_hits(llm, 6, ", "), severity="medium",
                          fix="fix model and max_tokens server-side; clamp anything the client may tune"))
    elif any(p in sites for p in ("Anthropic", "OpenAI", "Google Gemini", "OpenRouter", "Perplexity")):
        res.append(result("spend.llm-params", "The caller cannot set model, n or max_tokens", "PASS", "no request value reaches model, n or max_tokens"))
    if not res:
        res.append(result("spend.none", "Paid or forwarding surface", "PASS", "no paid API host and no forwarding route found in production source"))
    return ledger.emit(res)


if __name__ == "__main__":
    sys.exit(main())
