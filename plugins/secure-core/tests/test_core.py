#!/usr/bin/env python3
"""secure-core tests: the ledger refuses unmeasured verdicts, UNKNOWN stays
UNKNOWN, and the inventory maps a known surface. Known-bad first."""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import ledger  # noqa: E402
import testkit as T  # noqa: E402

S = os.path.join(HERE, "..", "scripts")


def rejects(name, r):
    try:
        ledger.validate(r)
        T.expect("ledger rejects " + name, False, "accepted")
    except ledger.LedgerError:
        T.expect("ledger rejects " + name, True)


# --- ledger: known-bad results are refused ---
rejects("an unknown status", ledger.result("x", "t", "WARN", "a:1"))
rejects("a PASS with no evidence", ledger.result("x", "t", "PASS", ""))
rejects("a FAIL with no severity", ledger.result("x", "t", "FAIL", "a:1", fix="f"))
rejects("a FAIL with no fix", ledger.result("x", "t", "FAIL", "a:1", severity="high"))
rejects("an UNKNOWN with no reason", ledger.result("x", "t", "UNKNOWN", "a:1"))
rejects("a credential-shaped value in the text", ledger.result("x", "t", "PASS", "found " + T.fake_key("google")))
# ...and good ones pass.
for r in (ledger.result("x", "t", "PASS", "a:1"), ledger.result("x", "t", "FAIL", "a:1", severity="low", fix="f"),
          ledger.result("x", "t", "UNKNOWN", "a:1", reason="tool missing")):
    try:
        ledger.validate(r)
        T.expect("ledger accepts a well-formed %s" % r["status"], True)
    except ledger.LedgerError as e:
        T.expect("ledger accepts a well-formed %s" % r["status"], False, str(e))

# --- emit exit codes: UNKNOWN is never exit 0 ---
P = ledger.result("p", "t", "PASS", "a:1")
F = ledger.result("f", "t", "FAIL", "a:1", severity="high", fix="x")
U = ledger.result("u", "t", "UNKNOWN", "a:1", reason="r")
T.expect("emit: any FAIL exits 1", ledger.emit([P, F, U], io.StringIO()) == 1)
T.expect("emit: UNKNOWN without FAIL exits 3, not 0", ledger.emit([P, U], io.StringIO()) == 3)
T.expect("emit: no results exits 3 (nothing measured is not a pass)", ledger.emit([], io.StringIO()) == 3)
T.expect("emit: all PASS exits 0", ledger.emit([P], io.StringIO()) == 0)

# --- markdown and counts keep UNKNOWN separate ---
led = ledger.build("/tmp/x", [dict(P), dict(U), dict(F)], ["node"], {})
T.expect("counts keep UNKNOWN on its own", led["counts"] == {"PASS": 1, "FAIL": 1, "UNKNOWN": 1}, str(led["counts"]))
md = ledger.to_markdown(led)
T.expect("markdown has an UNKNOWN section with the reason", "## UNKNOWN (1)" in md and "why unknown: r" in md)

# --- accepted.json: entries need a reason and a date; acceptance never changes status ---
bad_acc = T.tree({"security/accepted.json": json.dumps({"accepted": [{"id": "f"}]})})
try:
    ledger.load_accepted(bad_acc)
    T.expect("accepted.json without reason/date is refused", False)
except ledger.LedgerError:
    T.expect("accepted.json without reason/date is refused", True)
import datetime
_today = datetime.date.today().isoformat()
good_acc = T.tree({"security/accepted.json": json.dumps({"accepted": [{"id": "f", "reason": "ruled", "ruled": _today, "evidence": "a:1"}]})})
led = ledger.build(good_acc, [dict(F)], [], {}, ledger.load_accepted(good_acc))
T.expect("an accepted FAIL is still FAIL, marked accepted", led["results"][0]["status"] == "FAIL" and led["results"][0]["accepted"]["ruled"] == _today)

# --- inventory: a known surface is mapped (known-bad = uncapped paid API, unguarded route) ---
HONO = {
    "package.json": json.dumps({"dependencies": {"hono": "4.6.0"}}),
    "wrangler.toml": 'name = "demo-api"\nmain = "src/index.ts"\n[[d1_databases]]\nbinding = "DB"\n',
    "src/index.ts": (
        "import { Hono } from 'hono'\nconst app = new Hono()\n"
        "app.get('/api/health', (c) => c.text('ok'))\n"
        "app.post('/api/ask', async (c) => {\n  const r = await fetch('https://api.anthropic.com/v1/messages', {headers: {'x-api-key': c.env.ANTHROPIC_API_KEY}})\n  return c.json(await r.json())\n})\n"
        "app.delete('/api/walks/:id', async (c) => {\n  const user = await requireUser(c)\n  await c.env.DB.prepare('delete from walks where id=? and owner_id=?').run()\n  return c.text('ok')\n})\nexport default app\n"),
    "src/index.test.ts": "app.get('/api/only-in-tests', () => 1)\n",
}
bad = T.tree(HONO)
out = T.tree({})
rc = subprocess.run([sys.executable, os.path.join(S, "inventory.py"), bad, "--out", out], capture_output=True, text=True).returncode
inv = json.load(open(os.path.join(out, "inventory.json")))
T.expect("inventory: exits 0", rc == 0)
T.expect("inventory: stack has hono and cloudflare", {"hono", "cloudflare"} <= set(inv["stack"]), str(inv["stack"]))
T.expect("inventory: finds the 3 production routes, not the test-only one", sorted(r["path"] for r in inv["routes"]) == ["/api/ask", "/api/health", "/api/walks/:id"], str(inv["routes"]))
gates = {r["path"]: r["gate"] for r in inv["routes"]}
T.expect("inventory: the owned delete route shows an auth reference", gates["/api/walks/:id"] == "auth reference")
T.expect("inventory: the paid route shows none", gates["/api/ask"] == "none found")
paid = {p["provider"]: p for p in inv["paid_apis"]}
T.expect("inventory: Anthropic found with NO spend cap reference", "Anthropic" in paid and paid["Anthropic"]["spend_cap_reference"] is None, str(paid))
T.expect("inventory: secret name listed, never a value", any(s["name"] == "ANTHROPIC_API_KEY" for s in inv["secrets_read"]))
T.expect("inventory: D1 store and Worker target", any(s["store"] == "D1" for s in inv["data_stores"]) and inv["deploy_targets"][0]["target"] == "Cloudflare Worker")
# known-good: the same app with a daily spend cap next to the call
good_files = dict(HONO)
good_files["src/index.ts"] = good_files["src/index.ts"].replace("  const r = await fetch", "  if (await overDailySpendCap(c)) return c.json({paused: true}, 503)\n  const r = await fetch")
good = T.tree(good_files)
out2 = T.tree({})
subprocess.run([sys.executable, os.path.join(S, "inventory.py"), good, "--out", out2], capture_output=True)
inv2 = json.load(open(os.path.join(out2, "inventory.json")))
cap = [p for p in inv2["paid_apis"] if p["provider"] == "Anthropic"][0]["spend_cap_reference"]
T.expect("inventory: a spend cap next to the call is found", bool(cap), str(cap))
# empty repo: no crash, nothing invented
empty = T.tree({"README.md": "hi"})
out3 = T.tree({})
rc = subprocess.run([sys.executable, os.path.join(S, "inventory.py"), empty, "--out", out3], capture_output=True).returncode
inv3 = json.load(open(os.path.join(out3, "inventory.json")))
T.expect("inventory: empty repo maps nothing and exits 0", rc == 0 and inv3["route_count"] == 0 and inv3["stack"] == [])

# --- walk: agent scratch copies and ignored folders are not the repo's code (Phase 4 defect, a repo's .agents/) ---
import walk  # noqa: E402
scratch = T.git_init(T.tree({".gitignore": "ignored/\n", "src/app.ts": "export const a = 1\n",
                             ".agents/run/inputs/repo/src/app.ts": "app.get('/api/debug/env', x)\n",
                             "ignored/copy/src/app.ts": "app.get('/api/debug/env', x)\n"}))
open(os.path.join(scratch, "src", "new.ts"), "w").write("export const untracked = 1\n")
seen = sorted(walk.rel(scratch, p) for p in walk.files(scratch))
T.expect("walk: reads tracked and untracked-not-ignored source only", seen == ["src/app.ts", "src/new.ts"], str(seen))

# --- node-runtime: the built-code load check applies to code that runs under Node, not to a Worker bundle ---
srv = T.tree({"package.json": json.dumps({"dependencies": {"express": "4"}})})
wk = T.tree({"package.json": json.dumps({"dependencies": {"hono": "4"}}), "wrangler.toml": 'name = "w"\n'})
o1, o2 = T.tree({}), T.tree({})
subprocess.run([sys.executable, os.path.join(S, "inventory.py"), srv, "--out", o1], capture_output=True)
subprocess.run([sys.executable, os.path.join(S, "inventory.py"), wk, "--out", o2], capture_output=True)
T.expect("stack: an express server is node-runtime", "node-runtime" in json.load(open(os.path.join(o1, "inventory.json")))["stack"])
T.expect("stack: a Hono Worker is not", "node-runtime" not in json.load(open(os.path.join(o2, "inventory.json")))["stack"])

# --- Phase 5 audit: the ledger refuses a URL password, an AWS key and an unshaped high-entropy token ---
import random as _r
_al = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
pw = (lambda g: "".join(g.choice(_al) for _ in range(22)))(_r.Random(8))
rejects("a URL carrying a password", ledger.result("x", "t", "PASS", "postgres://admin:%s@db.example.com/app" % pw))
rejects("an AWS access key id", ledger.result("x", "t", "PASS", "AKIA" + (lambda g: "".join(g.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(16)))(_r.Random(9))))
rejects("an unshaped high-entropy token", ledger.result("x", "t", "PASS", "token " + (lambda g: "".join(g.choice(_al) for _ in range(40)))(_r.Random(10))))
try:
    ledger.validate(ledger.result("x", "t", "PASS", "/var/folders/0b/7x7bxdrj1zyhrxd53h0000gn/T/sl-fixture-abc/src/index.ts:12"))
    T.expect("ledger accepts an ordinary temp path (not a key)", True)
except ledger.LedgerError:
    T.expect("ledger accepts an ordinary temp path (not a key)", False)

# --- Phase 8: stack detection routes nested fly / railway / supabase ---
# A monorepo keeps fly.toml, railway.json and supabase/ one folder down; detect_stack used to read the root only,
# so the adapters never ran (core.route.*-nested bench cases). Decoy: a client folder named supabase is not a project.
def _stack(files):
    d, o = T.tree(files), T.tree({})
    subprocess.run([sys.executable, os.path.join(S, "inventory.py"), d, "--out", o], capture_output=True)
    return set(json.load(open(os.path.join(o, "inventory.json")))["stack"])
T.expect("P8 stack: a fly.toml under services/api/ routes to fly", "fly" in _stack({"services/api/fly.toml": 'app = "api"\n', "README.md": "# m\n"}))
T.expect("P8 stack: a railway.json under services/mcp/ routes to railway", "railway" in _stack({"package.json": json.dumps({"private": True, "workspaces": ["services/*"]}), "services/mcp/railway.json": "{}", "services/mcp/package.json": "{}"}))
T.expect("P8 stack: a railway.toml two levels down routes to railway", "railway" in _stack({"apps/svc/worker/railway.toml": "[deploy]\n", "README.md": "# m\n"}))
T.expect("P8 stack: services/api/supabase/migrations/ routes to supabase", "supabase" in _stack({"services/api/supabase/migrations/0001.sql": "create table public.n (id int);\n", "services/api/main.py": "x = 1\n"}))
T.expect("P8 stack: the Python supabase client (requirements.txt) routes to supabase", "supabase" in _stack({"services/api/requirements.txt": "supabase==2.9.0\nfastapi==0.115.0\n", "services/api/main.py": "x = 1\n"}))
T.expect("P8 stack: `from supabase import create_client` in code routes to supabase", "supabase" in _stack({"bot/db.py": "from supabase import create_client\n"}))
T.expect("P8 stack: a src/lib/supabase/ client folder with no config or migrations is not a Supabase project", "supabase" not in _stack({"src/lib/supabase/client.ts": "export const x = 1\n", "package.json": json.dumps({"dependencies": {"react": "19"}})}))
T.expect("P8 stack: a fly.toml inside node_modules is not the repo's app", "fly" not in _stack({"node_modules/dep/fly.toml": 'app = "dep"\n', "README.md": "# m\n"}))
T.expect("P8 stack: a repo with none of these detects none", not {"fly", "railway", "supabase"} & _stack({"README.md": "# m\n", "package.json": json.dumps({"dependencies": {"hono": "4"}})}))

# --- Phase 9: shared helpers ---
# names.secret_name, surface.import_names / imported / request_names / CALLER_SUPPLIED_RX and walk.block /
# enclosing_block / function_body / decl_src replaced copies in the platform, app and ai scripts (2026-11-01).
# Each former copy's own cases, then every disagreement between copies and the reading the merge keeps.
import names  # noqa: E402
import surface  # noqa: E402
import walk  # noqa: E402

# the cloudflare copy's cases (wrangler [vars] and NEXT_PUBLIC_ names)
for _n, _want in (("STRIPE_SECRET_KEY", True), ("GITHUB_TOKEN", True), ("ANTHROPIC_API_KEY", True), ("DB_PASSWORD", True),
                  ("SUPABASE_SERVICE_ROLE_KEY", True), ("SSH_PRIVATE_KEY", True), ("SENTRY_DSN", True), ("MAPS_KEY", True),
                  ("KEYBOARD_LAYOUT", False), ("MAX_TOKENS", False), ("SESSION_TOKEN_TTL_SECONDS", False), ("TURNSTILE_SITE_KEY", False),
                  ("STRIPE_PUBLISHABLE_KEY", False), ("SUPABASE_ANON_KEY", False), ("PUBLIC_SITE_URL", False), ("MODEL", False)):
    T.expect("P9 names: secret_name(%s) is %s" % (_n, _want), names.secret_name(_n) is _want)
# the fly copy's cases ([env] names and values)
for _n, _want in (("SUPABASE_SERVICE_KEY", True), ("JWT_SECRET", True), ("SUPABASE_URL", False), ("TOKEN_ISSUER", False)):
    T.expect("P9 names: secret_name(%s) is %s" % (_n, _want), names.secret_name(_n) is _want)
T.expect("P9 names: a key-shaped VALUE under an innocent name is a secret", names.secret_name("BILLING_PROVIDER", T.fake_key("stripe", 21)) is True)
T.expect("P9 names: a URL password in the value is a secret", names.secret_name("UPSTREAM", "postgres://app:pw@db.internal/app") is True)
T.expect("P9 names: an innocent name with an innocent value is not", names.secret_name("BILLING_PROVIDER", "stripe") is False)
# disagreements between the copies, and the reading kept
T.expect("P9 names: a setting suffix cancels a strong segment (fly rule): PRIVATE_KEY_PATH", names.secret_name("PRIVATE_KEY_PATH") is False)
T.expect("P9 names: SECRET_KEY_ID and CLIENT_SECRET_FILE are settings about a secret", not names.secret_name("SECRET_KEY_ID") and not names.secret_name("CLIENT_SECRET_FILE"))
T.expect("P9 names: PASSWORD_MIN_LENGTH is a setting", names.secret_name("PASSWORD_MIN_LENGTH") is False)
T.expect("P9 names: a database URL name is a secret everywhere (fly rule): DATABASE_URL, REDIS_URL, PG_DSN", all(names.secret_name(n) for n in ("DATABASE_URL", "REDIS_URL", "PG_DSN", "MONGODB_URI")))
T.expect("P9 names: DATABASE_URL behind a browser prefix is a secret too", names.secret_name("DATABASE_URL", browser=True) is True)
T.expect("P9 names: MAPBOX_TOKEN is public in every config (cloudflare rule)", names.secret_name("MAPBOX_TOKEN") is False and names.secret_name("MAPBOX_TOKEN", browser=True) is False)
T.expect("P9 names: the public allowlist wins over the database rule and the vocabulary", not names.secret_name("PUBLIC_DATABASE_URL") and not names.secret_name("PUBLIC_API_KEY"))
T.expect("P9 names: the fly words PASS, PWD, APIKEY are suffixes: DB_PASS, REDIS_PWD, STRIPE_APIKEY", all(names.secret_name(n) for n in ("DB_PASS", "REDIS_PWD", "STRIPE_APIKEY")))
T.expect("P9 names: weak words count only as a suffix (cloudflare rule): ACCESS_TOKEN_LIFETIME, KEY_VALUE, PRIVATE_NOTES", not any(names.secret_name(n) for n in ("ACCESS_TOKEN_LIFETIME", "KEY_VALUE", "PRIVATE_NOTES", "PASS_THROUGH")))
T.expect("P9 names: strong words count anywhere: SITE_PASSWORD, ALL_SECRETS, PASSWORD_HASH", all(names.secret_name(n) for n in ("SITE_PASSWORD", "ALL_SECRETS", "PASSWORD_HASH")))
T.expect("P9 names: a browser Maps key is public only under a browser prefix", names.secret_name("GOOGLE_MAPS_API_KEY", browser=True) is False and names.secret_name("GOOGLE_MAPS_API_KEY") is True)
T.expect("P9 names: case and whitespace do not matter; an empty name is not a secret", names.secret_name(" stripe_secret_key ") is True and names.secret_name("") is False and names.secret_name("___") is False)

# surface: relative imports
_imp = T.tree({"src/index.ts": "import geo from './geo.js'\nimport { lookup as find, type Opts } from './lib/index'\nconst { reserve } = require('./meter')\nexport { x } from './re'\n",
               "src/geo.ts": "export default async function geo(q) { return fetch('https://maps.googleapis.com/x?q=' + q) }\n",
               "src/lib/index.ts": "export function lookup(a) { return a }\n", "src/meter.js": "exports.reserve = () => {}\n", "src/re.ts": "export const x = 1\n"})
_names = surface.import_names(_imp, "src/index.ts")
T.expect("P9 imports: a default import maps to its LOCAL name (both callers searched the target for it)", _names.get("geo") == ("src/geo.ts", "geo"))
T.expect("P9 imports: './geo.js' resolves to geo.ts (TypeScript ESM names the built file)", _names["geo"][0] == "src/geo.ts")
T.expect("P9 imports: `lookup as find` maps the local name to the exported one, through /index.ts", _names.get("find") == ("src/lib/index.ts", "lookup"))
T.expect("P9 imports: `type Opts` brings no code", "Opts" not in _names)
T.expect("P9 imports: a destructured require resolves too", _names.get("reserve") == ("src/meter.js", "reserve"))
T.expect("P9 imports: imported() lists the file and one level of imports and re-exports", surface.imported(_imp, "src/index.ts") == ["src/index.ts", "src/geo.ts", "src/lib/index.ts", "src/meter.js", "src/re.ts"])
T.expect("P9 imports: an unresolvable specifier is skipped, never guessed", surface.import_names(T.tree({"a.ts": "import z from './missing'\n"}), "a.ts") == {} and surface.resolve_import(_imp, "src/index.ts", "./nope") is None)
T.expect("P9 imports: import_names takes the caller's already-read text", surface.import_names(_imp, "src/index.ts", "import geo from './geo'\n") == {"geo": ("src/geo.ts", "geo")})

# surface: caller input and the names it flows into
_js = """const { model, max_tokens } = await c.req.json()
const input = Schema.parse(await c.req.json())
const q = c.req.query('q')
let page: number = Number(c.req.query('page'))
const { topic } = body
const chosen = ALLOWED.includes(body.model) ? body.model : DEFAULT
const safe = String(model).slice(0, 20)
const res = await fetch(url, { body: JSON.stringify(x) })
const ip = c.req.header('cf-connecting-ip')
const ua = c.req.header('user-agent')
const prompt = `Write about ${safe}`
"""
_rn = surface.request_names(_js)
T.expect("P9 taint: destructured from the body and a schema-parsed whole value are caller input (spend rule)", {"model", "max_tokens", "input", "q"} <= _rn)
T.expect("P9 taint: a bare conventional name (body) at the START of a value binds (spend rule)", "topic" in _rn)
T.expect("P9 taint: a server choice that merely mentions body.model is NOT caller input", "chosen" not in _rn)
T.expect("P9 taint: `body:` inside a fetch option is not the request body", "res" not in _rn)
T.expect("P9 taint: a connecting-address header is never caller input; another header is", "ip" not in _rn and "ua" in _rn)
T.expect("P9 taint: input flows one level through a tainted VALUE (ai rule)", "safe" in _rn and "prompt" in _rn)
T.expect("P9 taint: a typed `let` binding counts", "page" in _rn)
T.expect("P9 taint: an accessor anywhere in the value taints it (ai rule)", "x" in surface.request_names("const x = clean(c.req.query('q')) + '!'\n"))
T.expect("P9 taint: a property named like a tainted variable does not carry taint", "y" not in surface.request_names("const { model } = await c.req.json()\nconst y = cfg.model\n"))
T.expect("P9 taint: Python assignments from the request count", {"data", "topic"} <= surface.request_names("data = request.get_json()\ntopic = request.args.get('t')\nmodel = DEFAULT\n") and "model" not in surface.request_names("model = DEFAULT\n"))
T.expect("P9 taint: nothing bound means an empty set", surface.request_names("const a = 1\nconst b = a + 2\n") == set())
T.expect("P9 taint: the wider CALLER_SUPPLIED reading sees headers and context vars the entry vocabulary does not", surface.CALLER_SUPPLIED_RX.search("c.get('userId')") and surface.CALLER_SUPPLIED_RX.search("c.req.header('x-device')") and not surface.CALLER_INPUT_RX.search("c.get('userId')"))

# walk: brace-balanced blocks and declarations
T.expect("P9 blocks: block() returns the balanced block that opens at or after start", walk.block("x { a { b } c } y", 0) == "{ a { b } c }" and walk.block("f() {\n  if (a) { b }\n}\n", 3) == "{\n  if (a) { b }\n}")
T.expect("P9 blocks: no brace means ''", walk.block("no braces here", 0) == "")
T.expect("P9 blocks: an unbalanced block is read to the cap, never shorter (6000, the larger of the two copies)", len(walk.block("{" + "a" * 7000, 0)) == walk.BLOCK_LIMIT and walk.block("{ ab", 0, limit=3) == "{ a")
T.expect("P9 blocks: block_end gives the index past the matching brace, None when unbalanced", walk.block_end("{ { } }", 0) == 7 and walk.block_end("{ {", 0) is None and walk.block_end("{" + "x" * 10 + "}", 0, limit=5) is None)
_code = "export default {\n  async fetch(req, env) {\n    if (!env.ADMIN_TOKEN) return next()\n  }\n}\n"
_pos = _code.index("return next()")
T.expect("P9 blocks: enclosing_block() is the innermost block around pos, from the strings-blanked view", walk.enclosing_block(_code, _code, _pos) == "{\n    if (!env.ADMIN_TOKEN) return next()\n  }")
T.expect("P9 blocks: enclosing_block() at top level is the whole text", walk.enclosing_block("const a = 1\n", "const a = 1\n", 5) == "const a = 1\n")
T.expect("P9 blocks: function_body() for a declaration and an arrow", walk.function_body("function geo(q) { return q }", "geo") == "{ return q }" and walk.function_body("const geo = async (q) => {\n  return q\n}", "geo") == "{\n  return q\n}")
T.expect("P9 blocks: function_decl() finds let/var too and None when absent", walk.function_decl("let f = () => 1", "f") is not None and walk.function_decl("const g = 1", "f") is None and walk.function_body("x", "f") == "")
T.expect("P9 decl: decl_src() reads a const, a destructuring, a Python assignment, in scope order", walk.decl_src("key", "const key = `ai:${day}`") == "`ai:${day}`" and walk.decl_src("deviceId", "const { deviceId } = await c.req.json()") == "await c.req.json()" and walk.decl_src("n", "n = request.args['n']") == "request.args['n']")
T.expect("P9 decl: the first scope with a binding wins; none means ''", walk.decl_src("k", "const k = inner", "const k = outer") == "inner" and walk.decl_src("k", "const j = 1") == "" and walk.decl_src("k", "if (k == 2) {}") == "")

# --- the version every ledger reports matches the plugin manifest (it sat at 0.3.0 through 0.5.2, found 2026-11-01) ---
_pj = json.load(open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json")))
T.expect("ledger.SUITE_VERSION equals secure-core's plugin.json version", ledger.SUITE_VERSION == _pj["version"], "%s vs %s" % (ledger.SUITE_VERSION, _pj["version"]))

T.finish()
