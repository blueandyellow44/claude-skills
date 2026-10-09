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
AUTH_RX = re.compile(r"requireAuth|requireUser|requireAdmin|requireSession|getSession|getServerSession|auth\(\)|currentUser|verifySession|readSession|sessionFrom|getUser\(|isAdmin|jwtVerify|Cf-Access-Jwt-Assertion|ownerId|owner_id|user_id\s*=|passcode|checkPasscode|withAuth|authMiddleware|ensureSignedIn|signedInUser|userFromRequest|userSpace|requireOwner|\b40[13]\b\s*\)|status\(\s*40[13]\s*\)|status:\s*40[13]\b|Unauthorized|Forbidden|SIGN_IN_REQUIRED|Depends\(\s*\w*(?:auth|user|session|verify)\w*|HTTPException\(\s*(?:status_code\s*=\s*)?40[13]\b|login_required|@requires_auth", re.I)
CAP_RX = re.compile(r"(spend|budget|cost|usage|daily|monthly)[_\- ]?(cap|limit|ceiling|max)|max[_\-]?(spend|cost|usd|dollars)|free[_\-]?(uses|limit|walks)|\bquota\b"
                    r"|MAX_[A-Z_]*_PER_(?:RUN|DAY|REQUEST|HOUR)|(?:score|call|request|token)Limit\b|SPEND_CUTOFF|\w*_BUDGET\b|Budget(?:Exceeded|Error)\b", re.I)
REQ_INPUT_RX = re.compile(r"c\.req\.(?:query|param|queries|json|parseBody|formData|header)\(|\.searchParams\.get\(|req\.(?:query|params|body)\b|request\.(?:json|formData|text)\(\)|await\s+c\.req\.json\(\)|\bctx\.params\b|context\.params\b")
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
                yield {"file": r, "line": ln, "method": "ANY", "path": m.group(1), "body": body, "code": code}
        for rx in FILE_ROUTE_RX:
            fm = rx.search(r)
            if fm:
                path = "/" + re.sub(r"/?index$", "", fm.group(1))
                methods = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)|export\s+const\s+onRequest(Get|Post|Put|Patch|Delete)?", t)
                ms = sorted({(a or b or "ANY").upper() for a, b in methods}) or ["ANY"]
                for meth in ms:
                    yield {"file": r, "line": 1, "method": meth, "path": path, "body": t, "code": "\n".join(code_lines)}
                break


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
