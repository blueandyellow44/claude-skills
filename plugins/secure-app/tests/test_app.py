#!/usr/bin/env python3
"""secure-app tests: ASVS-lite, outbound fetch, abuse and spend, mutation and
SSRF trap. Known-bad first; the bad fixture is shaped like a map app and
a news-scoring app before their 2026-10-07 repairs."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "secure-core", "lib"))
import testkit as T  # noqa: E402

S = os.path.join(HERE, "..", "scripts")

BAD = {
    "package.json": json.dumps({"dependencies": {"hono": "4.6.0"}}),
    "wrangler.toml": 'name = "maps"\n',
    "src/index.ts": """import { Hono } from 'hono'
import { cors } from 'hono/cors'
const app = new Hono()
app.use('*', cors({ origin: (o) => o, credentials: true }))
app.get('/api/route', async (c) => {
  const from = c.req.query('from')
  const r = await fetch(`https://router.project-osrm.org/route/v1/foot/${from}`)
  return c.json(await r.json())
})
app.get('/api/preview', async (c) => {
  const target = c.req.query('url')
  const r = await fetch(target)
  return c.text(await r.text())
})
app.post('/api/narrate', async (c) => {
  const body = await c.req.json()
  const r = await fetch('https://api.anthropic.com/v1/messages', { method: 'POST', body: JSON.stringify({ model: body.model, max_tokens: body.max_tokens }) })
  return c.json(await r.json())
})
app.delete('/api/walks/:id', async (c) => {
  await c.env.DB.prepare('delete from walks where id = ?').bind(c.req.param('id')).run()
  return c.text('ok')
})
app.get('/api/debug/env', (c) => c.json(Object.keys(c.env)))
app.post('/api/signout', (c) => {
  c.header('Set-Cookie', 'session=; Max-Age=0; Path=/')
  return c.text('bye')
})
app.onError((err, c) => c.json({ message: err.message, stack: err.stack }, 500))
export default app
""",
    "src/budget.ts": "const cap = Number(env.DAILY_SPEND_CAP) || Infinity\n",
    "src/ingest.ts": "export async function pull(feed) {\n  const res = await fetch(feed.link)\n  return res.text()\n}\n",
}
GOOD = {
    "package.json": json.dumps({"dependencies": {"hono": "4.6.0"}}),
    "src/index.ts": """import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { overDailySpendCap } from './spend'
import { safeFetch } from './safeFetch'
const app = new Hono()
app.use('*', cors({ origin: ['https://app.example.com'], credentials: true }))
app.get('/api/route', async (c) => {
  const from = c.req.query('from')
  if (!isInSanFrancisco(from)) return c.json({ error: 'outside the city' }, 400)
  const r = await fetch(`https://router.project-osrm.org/route/v1/foot/${from}`)
  return c.json(await r.json())
})
app.post('/api/narrate', async (c) => {
  const body = await c.req.json()
  if (await overDailySpendCap(c)) return c.json({ paused: true }, 503)
  const r = await fetch('https://api.anthropic.com/v1/messages', { method: 'POST', body: JSON.stringify({ model: 'claude-sonnet-5', max_tokens: 800, messages: [{ role: 'user', content: String(body.text).slice(0, 2000) }] }) })
  return c.json(await r.json())
})
app.delete('/api/walks/:id', async (c) => {
  const user = await requireUser(c)
  await c.env.DB.prepare('delete from walks where id = ? and owner_id = ?').bind(c.req.param('id'), user.id).run()
  return c.text('ok')
})
app.post('/api/signout', async (c) => {
  c.header('Set-Cookie', 'session=; Max-Age=0; Path=/')
  await c.env.DB.prepare('INSERT INTO revoked_sessions (hash, expires_at) VALUES (?, ?)').run()
  return c.text('bye')
})
app.onError((err, c) => { console.error(err.stack); return c.json({ error: 'internal' }, 500) })
export default app
""",
    "src/spend.ts": "export async function overDailySpendCap(c) {\n  const cap = Number(c.env.DAILY_SPEND_CAP)\n  if (!Number.isFinite(cap)) return true // unset cap = paused\n  return false\n}\nconst limiter = new Map()\nexport function allow(ip) { const n = (limiter.get(ip) || 0) + 1; limiter.set(ip, n); return n <= 60 }\n",
    "src/safeFetch.ts": "const BLOCKED = ['169.254.0.0/16']\nexport async function safeFetch(u) { if (isPrivateAddress(u)) throw new Error('blocked'); return fetch(u) }\n",
    "src/ingest.ts": "import { safeFetch } from './safeFetch'\nexport async function pull(feed) {\n  const res = await safeFetch(feed.link)\n  return res.text()\n}\n",
}

bad, good = T.tree(BAD), T.tree(GOOD)

rc, c, out = T.run(os.path.join(S, "check_app.py"), bad)
for cid in ("app.cors", "app.error-leak", "app.debug-routes", "app.signout", "app.object-writes"):
    T.status_is("app bad", c, cid, "FAIL", out)
rc, c, out = T.run(os.path.join(S, "check_app.py"), good)
for cid in ("app.cors", "app.error-leak", "app.debug-routes", "app.signout", "app.object-writes"):
    T.status_is("app good", c, cid, "PASS", out)
mw = T.tree({"src/index.ts": "app.use('/api/*', requireAuth)\napp.delete('/api/walks/:id', async (c) => c.text('x'))\n"})
rc, c, out = T.run(os.path.join(S, "check_app.py"), mw)
T.status_is("auth middleware over the path", c, "app.object-writes", "PASS", out)

rc, c, out = T.run(os.path.join(S, "check_fetch.py"), bad)
T.status_is("fetch bad", c, "fetch.request-url", "FAIL", out)
T.expect("fetch: the request-url FAIL names /api/preview", "/api/preview" in c.get("fetch.request-url", {}).get("evidence", ""))
T.status_is("fetch bad", c, "fetch.data-url", "FAIL", out)
T.expect("fetch: a Worker makes data-url severity low", c.get("fetch.data-url", {}).get("severity") == "low")
rc, c, out = T.run(os.path.join(S, "check_fetch.py"), good)
T.status_is("fetch good", c, "fetch.request-url", "PASS", out)
T.status_is("fetch good", c, "fetch.data-url", "PASS", out)
mixed = dict(GOOD)
mixed["src/other.ts"] = "export async function grab(item) { return fetch(item.image) }\n"
rc, c, out = T.run(os.path.join(S, "check_fetch.py"), T.tree(mixed))
T.status_is("fetch guard exists but a raw site remains", c, "fetch.data-url", "UNKNOWN", out)

rc, c, out = T.run(os.path.join(S, "check_spend.py"), bad)
for cid in ("spend.cap.anthropic", "spend.unset-cap", "spend.open-proxy", "spend.per-client", "spend.llm-params"):
    T.status_is("spend bad", c, cid, "FAIL", out)
rc, c, out = T.run(os.path.join(S, "check_spend.py"), good)
for cid in ("spend.cap.anthropic", "spend.unset-cap", "spend.open-proxy", "spend.per-client", "spend.llm-params"):
    T.status_is("spend good", c, cid, "PASS", out)

# ---------- mutation_check and ssrf_probe (moved from launch-secure-site) ----------
r = T.git_init(T.tree({"app.py": "def can_edit(owner, user):\n    return owner == user\n",
                       "guarded_test.py": "from app import can_edit\nassert can_edit('a','a')\nassert not can_edit('a','mallory')\n",
                       "weak_test.py": "from app import can_edit\nassert can_edit('a','a')\n"}))
def mut(test, find="owner == user"):
    return subprocess.run([sys.executable, os.path.join(S, "mutation_check.py"), "--repo", r, "--file", "app.py", "--find", find,
                           "--replace", "True", "--test", test], capture_output=True, text=True).returncode
T.expect("mutation: the guarded test DETECTS the removed ownership check (exit 0)", mut("python3 guarded_test.py") == 0)
T.expect("mutation: the weak test lets it SURVIVE (exit 1)", mut("python3 weak_test.py") == 1)
T.expect("mutation: an ambiguous pattern is refused (exit 2)", mut("true", "e") == 2)
T.expect("mutation: the real tree is untouched", "owner == user" in open(os.path.join(r, "app.py")).read())
T.expect("ssrf: the trap server's redirect routes answer", subprocess.run([sys.executable, os.path.join(S, "ssrf_probe.py"), "--self-test"], capture_output=True).returncode == 0)

# ---------- Phase 4 false-positive regressions (real repos, 2026-10-08) ----------
fp = T.tree({
    "wrangler.toml": 'name = "w"\nroutes = [{ pattern = "coach.example.com", custom_domain = true }]\n',
    "src/index.ts": """app.put('/walks/:id', async (c) => {
  const space = await userSpace(c)
  if (!space) return c.json({ error: SIGN_IN_REQUIRED }, 401)
  return c.text('ok')
})
app.get('/geo', async (c) => {
  const url =
    `https://photon.komoot.io/api/?q=${encodeURIComponent(c.req.query('q') ?? '').slice(0, 80)}`
  return fetch(url)
})
export async function cal(env) { return fetch(env.CALENDAR_ICS_URL) }
const SUBSTACK_URL = 'https://example.substack.com'
const FEED_URL = `${SUBSTACK_URL}/feed`
export async function feed() { return fetch(FEED_URL) }
export async function ask(env, params) {
  return fetch('https://api.anthropic.com/v1/messages', { body: JSON.stringify({ model: MODEL, max_tokens: params.maxTokens ?? 1024 }) })
}
const DAILY_SPEND_CAP = 5
""",
    "src/lib/fakeAnthropic.ts": "export function fake(body) { return { model: body.model, max_tokens: body.max_tokens } }\n",
    "scripts/_fal-edit.mjs": "await fetch('https://fal.run/fal-ai/flux')\n",
})
rc, c, out = T.run(os.path.join(S, "check_app.py"), fp)
T.status_is("FP: a handler that answers 401 is gated", c, "app.object-writes", "PASS", out)
rc, c, out = T.run(os.path.join(S, "check_fetch.py"), fp)
T.status_is("FP: multi-line constant, env URL and a template on a constant are not data URLs", c, "fetch.data-url", "PASS", out)
rc, c, out = T.run(os.path.join(S, "check_spend.py"), fp)
T.status_is("FP: an internal params.maxTokens and a test double are not caller-set", c, "spend.llm-params", "PASS", out)
T.expect("FP: local scripts/ are not attacker-reachable spend", "spend.cap.fal" not in c, str(list(c)))
access = T.tree({"README.md": "Live behind Cloudflare Access, gated to one account.\n",
                 "src/index.ts": "app.put('/api/journal/:date/work', async (c) => c.text('x'))\n"})
rc, c, out = T.run(os.path.join(S, "check_app.py"), access)
T.expect("Access-fronted app: still FAIL (no gate in code) but medium, naming Access",
         c.get("app.object-writes", {}).get("status") == "FAIL" and c["app.object-writes"]["severity"] == "medium" and "Cloudflare Access" in c["app.object-writes"]["detail"], out[-300:])

fp2 = T.tree({"src/api.ts": """const BASE = "/api"
export async function get(path) { return fetch(`${BASE}${path}`) }
export async function pay(gate, op, url) { return gate.fetch(op, url, {}) }
export async function stripe(opts) {
  const url = (opts.rewrite ?? ((u) => u))("https://api.stripe.com/v1/checkout/sessions")
  return fetch(url)
}
"""})
rc, c, out = T.run(os.path.join(S, "check_fetch.py"), fp2)
T.status_is("FP: same-origin path, a method named fetch, and a URL built on a fixed literal", c, "fetch.data-url", "PASS", out)
rc, c, out = T.run(os.path.join(S, "check_fetch.py"), T.tree({"src/p.ts": "export function photo(photoUrl, key) {\n  const url = photoUrl.replace('{KEY}', key)\n  return fetch(url)\n}\n"}))
T.status_is("a URL from data with no fixed host stays a FAIL", c, "fetch.data-url", "FAIL", out)

cl = T.tree({"src/index.ts": "app.get('/api/route', async (c) => { const f = c.req.query('f'); if (!inBounds(f)) return c.text('no', 400); return fetch(`https://router.example.org/${f}`) })\n",
             "components/Search.tsx": "if (res.status === 429) showBusy()\n"})
rc, c, out = T.run(os.path.join(S, "check_spend.py"), cl)
T.status_is("a 429 handled only in a browser component is not a limiter", c, "spend.per-client", "FAIL", out)

# ---------- Phase 5 audit: bypasses that used to PASS ----------
def st(script, files, cid):
    rc, c, out = T.run(os.path.join(S, script), T.tree(files))
    return c.get(cid, {}).get("status"), out
s, out = st("check_spend.py", {"src/a.ts": "// TODO: add a daily limit before launch\nexport async function f(){ return fetch('https://api.anthropic.com/v1/messages') }\n"}, "spend.cap.anthropic")
T.expect("audit #9: a comment mentioning a limit is not a spend cap", s == "FAIL", out[-200:])
s, out = st("check_spend.py", {"src/a.ts": "app.get('/x', async (c) => { const q = c.req.query('q'); const r = await fetch(`https://api.example.org/?q=${q}`.slice(0, 200)); if (r.status === 429) return c.text('busy'); return c.json(await r.json()) })\n"}, "spend.per-client")
T.expect("audit #9: reading an upstream 429 is not a per-client limiter", s == "FAIL", out[-200:])
s, out = st("check_spend.py", {"src/a.ts": "export async function f(env, spent){ if (env.DAILY_CAP && spent > env.DAILY_CAP) return null; return fetch('https://api.anthropic.com/v1/messages') }\nconst DAILY_SPEND_CAP = 1\n"}, "spend.unset-cap")
T.expect("audit #9: `if (cap && spent > cap)` (unset = unlimited) fails", s == "FAIL", out[-200:])
sdk = {"package.json": json.dumps({"dependencies": {"@anthropic-ai/sdk": "0.50.0", "hono": "4"}}),
       "src/a.ts": "import Anthropic from '@anthropic-ai/sdk'\nconst client = new Anthropic()\napp.post('/ask', async (c) => {\n  const { model, max_tokens, messages } = await c.req.json()\n  return c.json(await client.messages.create({ model, max_tokens, messages }))\n})\n"}
rc, c, out = T.run(os.path.join(S, "check_spend.py"), T.tree(sdk))
T.status_is("audit #8: a paid API called through its SDK is a paid site", c, "spend.cap.anthropic", "FAIL", out)
T.status_is("audit #8: model and max_tokens destructured from the request", c, "spend.llm-params", "FAIL", out)
s, out = st("check_app.py", {"src/a.ts": "app.delete('/walks/:id', async (c) => {\n  // TODO: return Unauthorized\n  await c.env.DB.prepare('delete').run()\n})\n"}, "app.object-writes")
T.expect("audit #9: 'Unauthorized' in a comment is not a gate", s == "FAIL", out[-200:])
s, out = st("check_app.py", {"lib/old/middleware.ts": "export function m(){ return getSession() }\n", "src/a.ts": "app.delete('/walks/:id', async (c) => c.text('x'))\n"}, "app.object-writes")
T.expect("audit #9: a middleware.ts outside the app root does not gate every route", s == "FAIL", out[-200:])
s, out = st("check_app.py", {"app/api/signout/route.ts": "import { cookies } from 'next/headers'\nexport async function POST() { cookies().delete('session'); return Response.json({ok: true}) }\n"}, "app.signout")
T.expect("audit #9: a cookie-only sign-out (cookies().delete) fails", s == "FAIL", out[-200:])
for label, src in (("(o, c) => o", "app.use('*', cors({ origin: (o, c) => o, credentials: true }))\n"),
                   ("origin echoed through a variable", "const origin = c.req.header('Origin')\nc.header('Access-Control-Allow-Origin', origin)\nc.header('Access-Control-Allow-Credentials', 'true')\n")):
    s, out = st("check_app.py", {"src/a.ts": src}, "app.cors")
    T.expect("audit #9: reflected CORS via %s fails" % label, s == "FAIL", out[-200:])
s, out = st("check_app.py", {"src/a.ts": "app.use('*', cors({ origin: (o) => ALLOWED.includes(o) ? o : null, credentials: true }))\n"}, "app.cors")
T.expect("an allow-listed origin function still passes", s == "PASS", out[-200:])
s, out = st("check_fetch.py", {"src/a.ts": "app.post('/p', async (c) => {\n  const { url } = await c.req.json()\n  return fetch(url)\n})\n"}, "fetch.request-url")
T.expect("audit #9: a destructured request URL is caught as request-url", s == "FAIL", out[-200:])
s, out = st("check_fetch.py", {"src/a.ts": "// blocks 169.254.169.254 (todo)\nexport async function g(item) { return fetch(item.link) }\n"}, "fetch.data-url")
T.expect("audit #9: a comment naming 169.254 is not a guard", s == "FAIL", out[-200:])

# ---------- second audit: routes on any router, FastAPI, stripper, CORS, spend ----------
s, out = st("check_app.py", {"package.json": json.dumps({"dependencies": {"express": "4"}}), "src/users.ts": "usersRouter.delete('/:id', async (req, res) => { await db.remove(req.params.id); res.end() })\n"}, "app.object-writes")
T.expect("audit 2: a route on usersRouter is seen and fails", s == "FAIL", out[-200:])
s, out = st("check_app.py", {"requirements.txt": "fastapi\n", "app/main.py": "@app.delete('/users/{user_id}')\ndef delete_user(user_id: int):\n    db.delete(user_id)\n"}, "app.object-writes")
T.expect("audit 2: a FastAPI {id} route without auth fails", s == "FAIL", out[-200:])
s, out = st("check_app.py", {"requirements.txt": "fastapi\n", "app/main.py": "@router.post('/positions/{position_id}/close')\ndef close(position_id: str, user=Depends(verify_supabase_user)):\n    return 1\n"}, "app.object-writes")
T.expect("audit 2: FastAPI Depends(verify_...) counts as auth", s == "PASS", out[-200:])
s, out = st("check_app.py", {"package.json": json.dumps({"dependencies": {"hono": "4"}}), "src/index.ts": "const x = 1\n"}, "app.object-writes")
T.expect("audit 2: a routing framework with no recognised route is UNKNOWN, not PASS", s == "UNKNOWN", out[-200:])
s, out = st("check_app.py", {"src/a.ts": "app.delete('/walks/:id', async (c) => {\n  const s = name.replace(/'/g, '')  // TODO: requireAuth\n  await c.env.DB.prepare('d').run()\n})\n"}, "app.object-writes")
T.expect("audit 2: a regex literal does not turn a comment into code", s == "FAIL", out[-200:])
s, out = st("check_app.py", {"requirements.txt": "flask\n", "app.py": "@app.post('/debug/reset-db')\ndef reset():\n    \"\"\"Call requireAuth and check NODE_ENV first.\"\"\"\n    db.reset()\n"}, "app.debug-routes")
T.expect("audit 2: a docstring is not a guard", s == "FAIL", out[-200:])
s, out = st("check_app.py", {"src/i.ts": "app.use('*', authStub)\napp.delete('/a/:id', (c) => c.text('x'))\nexport const authStub = async (c, next) => { c.set('teacher', c.req.header('X-Teacher-Id')); await next() }\n"}, "app.header-identity")
T.expect("audit 2: identity from X-Teacher-Id fails", s == "FAIL", out[-200:])
for label, src in (("typed arrow", "app.use(cors({ origin: (origin: string) => origin, credentials: true }))"), ("async arrow", "app.use(cors({ origin: async (origin) => origin, credentials: true }))"),
                   ("/.*/", "app.use(cors({ origin: /.*/, credentials: true }))"), ("callback", "app.use(cors({ origin: function (o, cb) { cb(null, true) }, credentials: true }))"),
                   ("express setHeader", "res.setHeader(ACAO, req.headers.origin)\nres.setHeader('Access-Control-Allow-Credentials', 'true')"),
                   ("express header get", "res.header(ACAO, req.get('origin'))\nres.header('Access-Control-Allow-Credentials', 'true')")):
    s, out = st("check_app.py", {"src/a.ts": src + "\n"}, "app.cors")
    T.expect("audit 2: CORS %s fails" % label, s == "FAIL", out[-160:])
s, out = st("check_app.py", {"app.py": "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True)\n"}, "app.cors")
T.expect("audit 2: Starlette * with credentials fails", s == "FAIL", out[-160:])
s, out = st("check_spend.py", {"src/a.ts": "class UpstreamLimitError extends Error {}\napp.get('/x', async (c) => { const q = c.req.query('q').slice(0, 9); const r = await fetch(`https://api.example.org/?q=${q}`); if (!r.ok) throw new UpstreamLimitError('x'); return c.json({}) })\n"}, "spend.per-client")
T.expect("audit 2: an error class named *LimitError is not a limiter", s == "FAIL", out[-200:])
s, out = st("check_spend.py", {"src/llm.ts": "export async function ask(){ return fetch('https://api.anthropic.com/v1/messages') }\n", "src/Help.tsx": "import { ask } from './llm'\nexport const H = () => <p>There is no daily spend cap yet</p>\n"}, "spend.cap.anthropic")
T.expect("audit 2: JSX text is not a spend cap", s == "FAIL", out[-200:])
s, out = st("check_spend.py", {"src/a.ts": "const GIFT_LIMITS = { dailyUsdCap: Number.MAX_SAFE_INTEGER }\nexport async function f(){ return fetch('https://api.anthropic.com/v1/messages') }\n"}, "spend.unset-cap")
T.expect("audit 2: a cap set to MAX_SAFE_INTEGER is unlimited", s == "FAIL", out[-200:])
two = {"src/translator.ts": "export async function tr(){ return fetch('https://api.anthropic.com/v1/messages') }\n",
       "src/scorer.ts": "import { DAILY_SPEND_CAP } from './caps'\nexport async function sc(){ return fetch('https://api.anthropic.com/v1/messages') }\n",
       "src/caps.ts": "export const DAILY_SPEND_CAP = 5\n"}
s, out = st("check_spend.py", two, "spend.cap.anthropic")
T.expect("audit 2: one capped call site does not cover an uncapped one", s == "FAIL" and "translator.ts" in out, out[-200:])

s, out = st("check_app.py", {"app.py": "@app.get('/x')\ndef x():\n    try:\n        run()\n    except Exception:\n        return JSONResponse({'error': traceback.format_exc()}, status_code=500)\n"}, "app.error-leak")
T.expect("a Python traceback returned in a response fails", s == "FAIL", out[-200:])

# ---------- cap enforcement must be at the call site (2026-10-09 hand checks: a coaching app, a classroom app, a map app) ----------
llm = "export async function runGeneration(){ return fetch('https://api.anthropic.com/v1/messages') }\n"
mw = {"src/lib/llm.ts": llm,
      "src/index.ts": "import planning from './routes/planning'\napp.use('/api/planning/lessons/generate', requireCaps)\napp.route('/api/planning', planning)\n",
      "src/routes/planning.ts": "import { runGeneration } from '../lib/llm'\nplanning.post('/lessons/generate', async (c) => { return c.json(await runGeneration()) })\nplanning.get('/library', async (c) => c.json([]))\n"}
s, out = st("check_spend.py", mw, "spend.cap.anthropic")
T.expect("a cap middleware mounted over the calling route counts", s == "PASS", out[-200:])
gate_ = {"src/lib/llm.ts": llm, "src/api.ts": "import { runGeneration } from './lib/llm'\napp.post('/x', async (c) => { const g = new SpendGate(c.env.DB); await g.begin(); return c.json(await runGeneration()) })\n"}
s, out = st("check_spend.py", gate_, "spend.cap.anthropic")
T.expect("constructing a spend gate at the call site counts", s == "PASS", out[-200:])
disp = {"src/lib/llm.ts": llm, "src/coach.ts": "export const DAILY_OUTPUT_BUDGET = 1000\nexport function chat(used){ if (used > DAILY_OUTPUT_BUDGET) throw new Error('budget') }\n",
        "src/index.ts": "import { DAILY_OUTPUT_BUDGET } from './coach'\nimport { runGeneration } from './lib/llm'\napp.get('/c', async (c) => { await runGeneration(); return c.json({ budget: DAILY_OUTPUT_BUDGET }) })\n"}
s, out = st("check_spend.py", disp, "spend.cap.anthropic")
T.expect("a budget imported only to display it is not enforcement", s == "FAIL" and "index.ts" in out, out[-200:])
typ = {"src/prose.ts": "import type { Env } from './coach'\nexport async function p(){ return fetch('https://api.anthropic.com/v1/messages') }\n",
       "src/coach.ts": "export type Env = {}\nexport function g(used){ if (used > DAILY_OUTPUT_BUDGET) throw 1 }\n"}
s, out = st("check_spend.py", typ, "spend.cap.anthropic")
T.expect("an `import type` is not a call path to a cap", s == "FAIL", out[-200:])

s, out = st("check_spend.py", {"src/a.ts": "app.get('/t', async (c) => { const q = c.req.query('q').slice(0, 9); return fetch(`https://api.anthropic.com/v1/x?q=${q}`) })\nconst limiter = new ModelCallLimiter(4)\nif (res.status !== 429) retry()\n"}, "spend.per-client")
T.expect("a concurrency limiter and an upstream 429 comparison are not per-client limits", s == "FAIL", out[-200:])

T.finish()
