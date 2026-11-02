"""surface.py - the route and outbound-call vocabulary shared by the inventory
and the app-layer checks, so both read a handler the same way."""
import os
import re

import walk

PAID_HOSTS = {
    "api.anthropic.com": "Anthropic",
    "api.openai.com": "OpenAI",
    "generativelanguage.googleapis.com": "Google Gemini",
    "aiplatform.googleapis.com": "Google Vertex",
    "api.elevenlabs.io": "ElevenLabs",
    "api.deepgram.com": "Deepgram",
    "routes.googleapis.com": "Google Routes",
    "maps.googleapis.com": "Google Maps",
    "places.googleapis.com": "Google Places",
    "tile.googleapis.com": "Google Map Tiles",
    "api.replicate.com": "Replicate",
    "fal.run": "fal",
    "queue.fal.run": "fal",
    "api.perplexity.ai": "Perplexity",
    "openrouter.ai": "OpenRouter",
    "api.resend.com": "Resend",
    "api.twilio.com": "Twilio",
}
SDK_PAID = {
    "@anthropic-ai/sdk": "Anthropic", "openai": "OpenAI", "@google/generative-ai": "Google Gemini",
    "@google/genai": "Google Gemini", "elevenlabs": "ElevenLabs", "@elevenlabs/elevenlabs-js": "ElevenLabs",
    "@deepgram/sdk": "Deepgram", "replicate": "Replicate", "@fal-ai/client": "fal", "resend": "Resend",
    "twilio": "Twilio", "anthropic": "Anthropic",
}
# Any object's route method with a path literal (app, translationsRouter, gradebook...), and Python decorators.
ROUTE_RX = re.compile(r"""(?<![.\w])(?!(?:axios|got|ky|fetch|http|https|request|superagent|client|res|req|c|ctx|map|cache|params|headers|searchParams|url|kv|db|env|this)\.)[A-Za-z_$][\w$]*\.(get|post|put|patch|delete|all)\(\s*['"`](/[^'"`]*)['"`]""")
PY_ROUTE_RX = re.compile(r"""@\w+\.(get|post|put|patch|delete|route|api_route)\(\s*['"](/[^'"]*)['"](?:[^)]*methods\s*=\s*\[([^\]]*)\])?""")
WORKER_PATH_RX = re.compile(r"""(?:pathname|url\.pathname|path)\s*(?:===|==|\.startsWith\()\s*['"`](/[^'"`]*)['"`]""")
# request.method === 'DELETE' / req.method == "POST" / method === 'PUT' on the same condition as a pathname test
WORKER_METHOD_RX = re.compile(r"""\bmethod\s*(?:===|==)\s*['"](GET|POST|PUT|PATCH|DELETE)['"]""", re.I)
AUTH_RX = re.compile(r"requireAuth|requireUser|requireAdmin|requireSession|getSession|getServerSession|auth\(\)|currentUser|verifySession|readSession|sessionFrom|getUser\(|isAdmin|jwtVerify|Cf-Access-Jwt-Assertion|ownerId|owner_id|user_id\s*=|passcode|checkPasscode|withAuth|authMiddleware|ensureSignedIn|signedInUser|userFromRequest|userSpace|requireOwner|\b40[13]\b\s*\)|status\(\s*40[13]\s*\)|status:\s*40[13]\b|Unauthorized|Forbidden|SIGN_IN_REQUIRED|Depends\(\s*\w*(?:auth|user|session|verify)\w*|HTTPException\(\s*(?:status_code\s*=\s*)?40[13]\b|login_required|@requires_auth", re.I)
# The AUTH_RX alternatives that name only a refusal, not who is being refused: a 401/403 or a
# Forbidden/Unauthorized identifier. These gate a handler only when the condition that triggers
# them speaks of identity (auth_ref); `if (note.locked) return 403` refuses locked notes, not strangers.
STATUS_ONLY_RX = re.compile(r"^(?:\b40[13]\b\s*\)|status\(\s*40[13]\s*\)|status:\s*40[13]\b|Unauthorized|Forbidden|HTTPException\(\s*(?:status_code\s*=\s*)?40[13]\b)$", re.I)
IDENTITY_WORD_RX = re.compile(r"user|session|auth|owner|token|login|logged|signed|identity|principal|account|member|admin|role|perm|allow|email|claim|jwt|\bsub\b|\buid\b|tenant|caller|actor|\bme\b|\bkey\b|secret|passcode|verif|can[A-Z]\w*|is(?:Owner|Admin|Allowed|Authori[sz]ed|Member|Mine)|teacher|student", re.I)
# Ownership identifiers that AUTH_RX credits; worthless when the caller supplies them (ownerId from the JSON body)
OWNER_ID_RX = re.compile(r"\b(?:ownerId|owner_id|user_id|userId|accountId|tenantId)\b")
REQ_SOURCE_RX = re.compile(r"c\.req\.(?:json|parseBody|formData|query|queries|param|header)\(|req(?:uest)?\.(?:body|query|params|headers)\b|request\.(?:json|formData|text)\(|\b(?:body|payload|input|params)\b|searchParams\.get\(")
CAP_RX = re.compile(r"(spend|budget|cost|usage|daily|monthly)[_\- ]?(cap|limit|ceiling|max)|max[_\-]?(spend|cost|usd|dollars)|free[_\-]?(uses|limit|walks)|\bquota\b"
                    r"|MAX_[A-Z_]*_PER_(?:RUN|DAY|REQUEST|HOUR)|(?:score|call|request|token)Limit\b|SPEND_CUTOFF|\w*_BUDGET\b|Budget(?:Exceeded|Error)\b", re.I)
# searchParams.get( with or without a receiver: `const { searchParams } = new URL(req.url)` destructures it (Phase 8)
REQ_INPUT_RX = re.compile(r"c\.req\.(?:query|param|queries|json|parseBody|formData|header)\(|\bsearchParams\.get\(|req\.(?:query|params|body)\b|request\.(?:json|formData|text)\(\)|await\s+c\.req\.json\(\)|\bctx\.params\b|context\.params\b")
FILE_ROUTE_RX = [re.compile(r"(?:^|/)app/(.*)/route\.(?:ts|js|tsx|jsx)$"), re.compile(r"(?:^|/)pages/(api/.*)\.(?:ts|js)$"),
                 re.compile(r"(?:^|/)functions/(.*)\.(?:ts|js)$")]
FETCH_RX = re.compile(r"""\b(?:fetch|axios(?:\.(?:get|post|put|request))?|got|ky|https?\.(?:get|request))\(\s*([^,\)\n]{1,160})""")
URL_HOST_RX = re.compile(r"""https?://([A-Za-z0-9.\-]+)""")
STUB_RX = re.compile(r"stub|fake|mock|dummy|noop|bypass", re.I)  # authStub trusts a header: not auth
# Frameworks whose routes are defined in code (a Next app with no route.ts simply has no handlers)
ROUTING_DEPS = {"hono", "express", "fastify", "koa", "itty-router", "@hono/node-server", "fastapi", "flask", "starlette"}
MW_RX = re.compile(r"""\b\w+\.use\(\s*['"`]([^'"`]*)['"`]\s*,\s*([^\n]{1,200})""")  # the whole chain: requireTier('a'), requireCaps


HANDLER_MAX = 200  # a handler runs to the next route definition, at most this many lines


def handlers(repo, served=True):
    """Yield dicts {file, line, method, path, body} for every route handler found.
    body is the handler's text: up to HANDLER_MAX lines, cut at the next route definition.
    File-based routes (Next app router, pages/api, Pages Functions) use the whole file."""
    for p in walk.files(repo, tests=False, served=served):
        t = walk.read_code(p)
        r = walk.rel(repo, p)
        lines = t.splitlines()
        code_lines = walk.read_code(p, strings=False).splitlines()
        found = [(m, "ROUTE") for m in ROUTE_RX.finditer(t)] + [(m, "WORKER") for m in WORKER_PATH_RX.finditer(t)]
        if r.endswith(".py"):
            found += [(m, "PY") for m in PY_ROUTE_RX.finditer(t)]
        starts = sorted(walk.line_of(t, m.start()) for m, _ in found)
        for m, kind in found:
            ln = walk.line_of(t, m.start())
            nxt = min([s for s in starts if s > ln] or [ln + HANDLER_MAX])
            body = "\n".join(lines[ln - 1: min(nxt - 1, ln + HANDLER_MAX)])
            code = "\n".join(code_lines[ln - 1: min(nxt - 1, ln + HANDLER_MAX)])
            if kind == "ROUTE":
                yield {"file": r, "line": ln, "method": m.group(1).upper(), "path": m.group(2), "body": body, "code": code}
            elif kind == "PY":
                meth = m.group(1).upper()
                if meth in ("ROUTE", "API_ROUTE"):
                    meth = (re.findall(r"[A-Z]+", (m.group(3) or "GET").upper()) or ["GET"])[0]
                yield {"file": r, "line": ln, "method": meth, "path": m.group(2), "body": body, "code": code}
            else:
                # a raw fetch handler: the method is whatever the same condition compares request.method to,
                # and startsWith('/api/notes/') is a prefix with something after it, written /api/notes/*
                cond = "\n".join(lines[ln - 1: ln + 1])
                mm = WORKER_METHOD_RX.search(cond)
                path = m.group(1)
                if "startsWith" in m.group(0) and path.endswith("/"):
                    path += "*"
                yield {"file": r, "line": ln, "method": mm.group(1).upper() if mm else "ANY", "path": path, "body": body, "code": code}
        for rx in FILE_ROUTE_RX:
            fm = rx.search(r)
            if fm:
                path = "/" + re.sub(r"/?index$", "", fm.group(1))
                methods = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)|export\s+const\s+onRequest(Get|Post|Put|Patch|Delete)?", t)
                ms = sorted({(a or b or "ANY").upper() for a, b in methods}) or ["ANY"]
                for meth in ms:
                    yield {"file": r, "line": 1, "method": meth, "path": path, "body": t, "code": "\n".join(code_lines)}
                break


def auth_ref(code):
    """The first AUTH_RX match in a handler's code that actually speaks of identity, or None.

    Two AUTH_RX credits are withdrawn here (Phase 8 benchmark misses):
    - an ownership identifier (ownerId, owner_id, user_id...) that the handler reads from the
      request (destructured from c.req.json(), assigned from req.body, read as body.ownerId):
      the caller names the owner, so it is not an ownership check;
    - a bare 401/403 or Forbidden/Unauthorized whose triggering condition names no identity
      (user, session, token, owner, admin, role...): `if (note.locked) return 403` refuses locked
      notes, not strangers.
    `code` is the handler text with comments AND strings blanked (surface.handlers()['code']).
    Other callers of AUTH_RX (the inventory's route map) keep the wider reading on purpose."""
    for name in set(OWNER_ID_RX.findall(code)):
        sourced = (re.search(r"\{[^}]*\b%s\b[^}]*\}\s*=\s*(?:await\s+)?(?:%s)" % (re.escape(name), REQ_SOURCE_RX.pattern), code)
                   or re.search(r"\b%s\s*=\s*(?:await\s+)?(?:%s)" % (re.escape(name), REQ_SOURCE_RX.pattern), code)
                   or re.search(r"\b(?:body|payload|input|params|req\.body|req\.query|req\.params)\.%s\b" % re.escape(name), code))
        if sourced:
            code = re.sub(r"\b%s\b" % re.escape(name), " " * len(name), code)
    for m in AUTH_RX.finditer(code):
        if not STATUS_ONLY_RX.match(m.group(0)):
            return m
        # the condition that leads to this refusal: from the nearest `if (` / `if ...:` within three lines
        start = code.rfind("\n", 0, m.start())
        for _ in range(3):
            start = code.rfind("\n", 0, max(0, start))
            if start <= 0:
                start = 0
                break
        window = code[start: m.start()]
        ifs = list(re.finditer(r"\b(?:if|elif|else\s+if|unless|guard|catch)\b", window))
        cond = window[ifs[-1].start():] if ifs else window
        if IDENTITY_WORD_RX.search(cond):
            return m
    return None


def middleware_auth(repo):
    """Path prefixes covered by an auth middleware mounted with app.use(prefix, fn)."""
    out = []
    for r, ln, m in walk.find(repo, MW_RX, tests=False):
        if AUTH_RX.search(m.group(2)) and not STUB_RX.search(m.group(2)):
            out.append((m.group(1).rstrip("*").rstrip("/") or "/", "%s:%d" % (r, ln)))
    for rel in ("middleware.ts", "middleware.js", "src/middleware.ts", "src/middleware.js"):
        p = os.path.join(repo, rel)
        if os.path.exists(p) and AUTH_RX.search(walk.read_code(p)):
            t = walk.read_code(p)
            m = re.search(r"matcher\s*:\s*(\[[^\]]*\]|['\"][^'\"]+['\"])", t)
            if m:  # only the matched prefixes are covered
                for pat in re.findall(r"['\"](/[^'\"]*)['\"]", m.group(1)):
                    out.append((re.sub(r"[:(].*$", "", pat).rstrip("/*") or "/", rel + " matcher"))
            else:
                out.append(("/", rel + " (Next middleware, no matcher: every path)"))
    return out


MOUNT_RX = re.compile(r"""\.(?:route|use)\(\s*['"](/[^'"]*)['"]\s*,\s*(\w+)\s*\)""")


def mount_paths(repo, rel, path):
    """Full paths for a sub-router file: app.route('/api/generate', generate) + '/lesson' -> /api/generate/lesson.
    Matches the mounted identifier against the file's import name or stem."""
    stem = os.path.splitext(os.path.basename(rel))[0].lower().replace("-", "").replace("_", "")
    out = []
    for r, ln, m in walk.find(repo, MOUNT_RX, tests=False, served=True):
        name = m.group(2).lower()
        if name == stem or name.startswith(stem[:5]) or stem.startswith(name[:5]):
            out.append(m.group(1).rstrip("/") + path)
    return out


def covered(path, mw):
    for prefix, at in mw:
        if prefix == "/" or path == prefix or path.startswith(prefix + "/"):
            return at
    return None


# ---- relative imports (Phase 9, 2026-11-01: one home) ----
# Merged from check_spend (_resolve, imported, _import_names) and check_auth_gates (_resolve, _import_names).
# The one disagreement: a default import (`import geo from './geo'`) mapped to the exported name "default" in
# check_spend and to the local name in check_auth_gates. Both callers then searched the target file for the
# LOCAL name (check_spend substituted it at its one use), so the local name is the one semantics kept here.
# `import type` brings no code: it is not a call path (a coaching app's prose.ts imports a TYPE from coach.ts).
IMPORT_REL = re.compile(r"""(?:^|[;\n])\s*(?:import\s+(?!type\b)(?:[^'";]*?\s+from\s+)?|export\s+(?!type\b)[^'";]*?\s+from\s+|[^\n]*?\brequire\(\s*)['"](\.{1,2}/[^'"]+)['"]""")
IMPORT_NAMES = re.compile(r"""import\s+(?:(\w+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*['"](\.{1,2}/[^'"]+)['"]|(?:const|let|var)\s*\{([^}]*)\}\s*=\s*require\(\s*['"](\.{1,2}/[^'"]+)['"]\s*\)""")
IMPORT_EXTS = ("", ".ts", ".tsx", ".js", ".mjs", "/index.ts", "/index.js")
JS_TO_TS = re.compile(r"\.(?:js|mjs)$")


def resolve_import(repo, rel, spec):
    """The repo-relative file a relative import specifier names, or None.
    TypeScript ESM imports name the .js that the .ts becomes, so './geo.js' resolves to geo.ts."""
    base = os.path.normpath(os.path.join(os.path.dirname(rel), spec))
    if not os.path.isfile(os.path.join(repo, base)):
        base = JS_TO_TS.sub("", base)
    for e in IMPORT_EXTS:
        cand = base + e
        if os.path.isfile(os.path.join(repo, cand)):
            return cand.replace(os.sep, "/")
    return None


def imported(repo, rel):
    """The file plus the relative files it imports or re-exports (one level), as repo-relative paths."""
    out = [rel]
    t = walk.read_code(os.path.join(repo, rel))
    for m in IMPORT_REL.finditer(t):
        target = resolve_import(repo, rel, m.group(1))
        if target:
            out.append(target)
    return out


def import_names(repo, rel, text=None):
    """local name -> (file, exported name) for every relative import in rel. A default import maps to its
    local name; `import { a as b }` maps b to (file, 'a'); `import type` members are skipped.
    `text` is the file's comment-stripped code when the caller already has it."""
    out = {}
    if text is None:
        text = walk.read_code(os.path.join(repo, rel))
    for m in IMPORT_NAMES.finditer(text):
        target = resolve_import(repo, rel, m.group(3) or m.group(5))
        if not target:
            continue
        if m.group(1):
            out[m.group(1)] = (target, m.group(1))
        for x in (m.group(2) or m.group(4) or "").split(","):
            x = x.strip()
            if x and not x.startswith("type "):
                parts = re.split(r"\s+as\s+|\s*:\s*", x)
                out[parts[-1]] = (target, parts[0])
    return out


# ---- caller input and the names it flows into (Phase 9, 2026-11-01: one home) ----
# Merged from check_spend._request_names (bindings whose value STARTS with a request accessor, through an
# optional schema parse; the connecting-address headers excluded) and check_ai._tainted (bindings whose value
# MENTIONS an accessor anywhere, flowing one level through earlier tainted names, plus Python assignments).
# The merge is the union: a binding is caller input when its right-hand side starts with an accessor or a
# conventional request-value name (body, payload, reqBody, requestBody), mentions an accessor anywhere, or
# mentions a name already bound to caller input earlier in the file. The conventional names count only at the
# START of a value: `const { model } = body` binds model, `fetch(url, { body: ... })` binds nothing. The
# connecting-address headers (cf-connecting-ip, x-real-ip, x-forwarded-for) are excluded for every consumer:
# the edge sets them, the caller does not, so a limiter keyed on them is a real per-client key.
CALLER_INPUT_RX = re.compile(
    r"c\.req\.(?:json|parseBody|formData|query|queries|param|text)\(|c\.req\.header\(\s*['\"](?!cf-connecting-ip|x-real-ip|x-forwarded-for)"
    r"|await\s+(?:req|request|c\.req)\.(?:json|text|formData)\(\)|\breq\.(?:body|query|params)\b|request\.(?:json|formData|text)\(|ctx\.request\.body"
    r"|\.searchParams\.get\(|\bformData\.get\(|\bevent\.body\b|request\.get_json\(|request\.(?:form|args|json)\b")
REQUEST_VALUE_NAMES = ("body", "payload", "reqBody", "requestBody")
# `const input = Schema.parse(await c.req.json())`, `const q = c.req.query('q')`, `const { model } = body`: the
# whole value is the request's. `const chosen = ALLOWED.includes(body.model) ? ...` is NOT (the server chooses).
BOUND_TO_INPUT_RX = re.compile(r"(?:await\s+)?(?:[\w$.]*(?:parse|safeParse|validate|decode)\w*\s*\(\s*)?(?:await\s+)?(?:%s|\b(?:%s)\b)"
                               % (CALLER_INPUT_RX.pattern, "|".join(REQUEST_VALUE_NAMES)))
ASSIGN_RX = re.compile(r"\b(?:const|let|var)\b\s*(\{[^}]{1,300}\}|[\w$]+)\s*(?::[^=\n]{0,80})?\s*=\s*([^;\n]{1,240})")
PY_ASSIGN_RX = re.compile(r"^[ \t]*([\w]+)\s*=\s*([^\n]{1,240})", re.M)
# The wider reading for a value already known to be a key component (check_metering): any header, a context
# variable a middleware set from the request, a query/param accessor, the request body under any accessor.
# Case-insensitive. Never use it to find where input enters a file; `.query(` also matches `db.query(`.
CALLER_SUPPLIED_RX = re.compile(CALLER_INPUT_RX.pattern +
                                r"|\.header\(|headers\.get\(|headers\[|req\.body|\bbody\.|payload\.|c\.get\(\s*['\"](?:teacher|user|account)|c\.var\.|searchParams\.get\(|\.query\(|\.param\("
                                r"|c\.req\.(?:json|parseBody|formData)\(|request\.json\(|req\.json\(|\bbody\b|\bpayload\b", re.I)
IDENT_RX = re.compile(r"^[A-Za-z_$][\w$]*$")


def _destructured(lhs):
    """Names bound by a destructuring pattern's text: `{ a, b: c = 1 }` binds a and c."""
    return {x.split(":")[-1].split("=")[0].strip() for x in lhs.strip("{}").split(",") if x.strip()}


def request_names(text):
    """Identifiers bound to caller input in this file (one level of flow): destructured from the body or
    query, assigned the whole request value (possibly through a schema parse), assigned an expression that
    reads a request accessor, or assigned from a name bound earlier in the file (as a value, not as a
    property: `obj.model` does not carry a tainted `model`). Python assignments count when they read an
    accessor. Used to follow caller input past its first name."""
    names = set()
    for m in ASSIGN_RX.finditer(text):
        lhs, rhs = m.group(1), m.group(2)
        if CALLER_INPUT_RX.search(rhs) or BOUND_TO_INPUT_RX.match(rhs) or any(re.search(r"(?<![\w$.])%s\b" % re.escape(n), rhs) for n in names):
            if lhs.startswith("{"):
                names |= _destructured(lhs)
            else:
                names.add(lhs)
    for m in PY_ASSIGN_RX.finditer(text):
        if CALLER_INPUT_RX.search(m.group(2)):
            names.add(m.group(1))
    return {n for n in names if IDENT_RX.match(n)}
