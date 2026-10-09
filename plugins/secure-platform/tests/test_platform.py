#!/usr/bin/env python3
"""secure-platform tests: one known-bad and one known-good fixture per adapter,
plus the moved probe_headers/find_embedders cases through the live-header check."""
import http.server
import json
import os
import socket
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "secure-core", "lib"))
import testkit as T  # noqa: E402

S = os.path.join(HERE, "..", "scripts")
run = lambda script, repo, *a: T.run(os.path.join(S, script), repo, *a)

# ---------- Cloudflare ----------
bad = T.tree({
    "wrangler.toml": 'name = "app"\n[vars]\nSTRIPE_SECRET_KEY = "not-a-real-value-just-a-placeholder"\nSITE_NAME = "x"\n[[d1_databases]]\nbinding = "DB"\ndatabase_id = "prod-123"\n[env.preview]\n[[env.preview.d1_databases]]\nbinding = "DB"\ndatabase_id = "prod-123"\n',
    "public/_headers": "/api/*\n  X-Content-Type-Options: nosniff\n",
    "src/index.ts": "export default { fetch() { return new Response('ok') } }\n",
})
rc, c, out = run("check_cloudflare.py", bad)
for cid in ("cf.headers.framing", "cf.headers.hsts", "cf.headers.nosniff", "cf.headers.referrer", "cf.vars-secrets", "cf.env-bindings"):
    T.status_is("cf bad", c, cid, "FAIL", out)
T.expect("cf: a header only on /api/* does not count for every path", c.get("cf.headers.nosniff", {}).get("status") == "FAIL")
T.expect("cf: cannot_see lists zone rules and the pages.dev alias", "pages.dev" in out and "zone rules" in out.lower())
good = T.tree({
    "wrangler.toml": 'name = "app"\n[vars]\nSITE_NAME = "x"\n[[d1_databases]]\nbinding = "DB"\ndatabase_id = "prod-123"\n[env.preview]\n[[env.preview.d1_databases]]\nbinding = "DB"\ndatabase_id = "preview-456"\n',
    "public/_headers": "/*\n  Content-Security-Policy: frame-ancestors 'self' https://example.com\n  Strict-Transport-Security: max-age=31536000\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n",
})
rc, c, out = run("check_cloudflare.py", good)
T.expect("cf good: all PASS", rc == 0 and len(c) == 6 and all(v["status"] == "PASS" for v in c.values()), out[-500:])
hono = T.tree({"wrangler.toml": 'name = "w"\n', "src/index.ts": "import { secureHeaders } from 'hono/secure-headers'\napp.use(secureHeaders())\n"})
rc, c, out = run("check_cloudflare.py", hono)
T.status_is("hono secureHeaders", c, "cf.headers.framing", "PASS", out)

# ---------- live headers (probe_headers.sh against a local server) ----------
class H(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        if self.path.startswith("/good"):
            for k, v in [("Content-Security-Policy", "frame-ancestors 'self'"), ("Strict-Transport-Security", "max-age=31536000"),
                         ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer")]:
                self.send_header(k, v)
        self.end_headers()
    def do_GET(self):
        if self.path == "/" and self.server.redirects:
            self.send_response(301)
            self.send_header("Location", "https://127.0.0.1:%d/" % self.server.server_address[1])
            self.end_headers()
            return
        self.do_HEAD()
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
srv.redirects = False
threading.Thread(target=srv.serve_forever, daemon=True).start()
port = srv.server_address[1]
rc, c, out = run("check_live_headers.py", good, "--url", "http://127.0.0.1:%d/bad" % port)
T.status_is("live bad", c, "live.127.0.0.1:%d.https-redirect" % port, "FAIL", out)
T.status_is("live bad", c, "live.127.0.0.1:%d.framing" % port, "FAIL", out)
T.status_is("live bad", c, "live.127.0.0.1:%d.hsts" % port, "FAIL", out)
srv.redirects = True
rc, c, out = run("check_live_headers.py", good, "--url", "http://127.0.0.1:%d/good" % port)
T.status_is("live good", c, "live.127.0.0.1:%d.https-redirect" % port, "PASS", out)
T.status_is("live good", c, "live.127.0.0.1:%d.framing" % port, "PASS", out)
T.status_is("live good", c, "live.127.0.0.1:%d.referrer" % port, "PASS", out)
srv.shutdown()
s = socket.socket(); s.bind(("127.0.0.1", 0)); dead = s.getsockname()[1]; s.close()
rc, c, out = run("check_live_headers.py", good, "--url", "http://127.0.0.1:%d/" % dead)
T.status_is("live no answer", c, "live.127.0.0.1:%d" % dead, "UNKNOWN", out)

# ---------- Next.js ----------
bad = T.tree({
    "package.json": json.dumps({"dependencies": {"next": "16.2.10"}}),
    "next.config.mjs": "export default { output: 'export', async headers() { return [{ source: '/(.*)', headers: [{ key: 'X-Frame-Options', value: 'DENY' }] }] } }\n",
    "app/actions.ts": "'use server'\nexport async function deleteWalk(id: string) {\n  await db.delete(walks).where(eq(walks.id, id))\n}\n",
    ".env.example": "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY=\n",
})
rc, c, out = run("check_nextjs.py", bad)
T.status_is("next bad", c, "next.public-env-secrets", "FAIL", out)
T.status_is("next bad", c, "next.static-export-headers", "FAIL", out)
bad_sa = T.tree({"next.config.ts": "export default {}\n", "app/actions.ts": "'use server'\nexport async function deleteWalk(id: string) {\n  await db.delete(walks).where(eq(walks.id, id))\n}\n"})
rc, c, out = run("check_nextjs.py", bad_sa)
T.status_is("next bad", c, "next.server-actions", "FAIL", out)
good = T.tree({
    "next.config.ts": "export default {}\n",
    "app/actions.ts": "'use server'\nexport async function deleteWalk(id: string) {\n  const user = await requireUser()\n  await db.delete(walks).where(and(eq(walks.id, id), eq(walks.ownerId, user.id)))\n}\n",
    ".env.example": "NEXT_PUBLIC_SUPABASE_ANON_KEY=\n",
})
rc, c, out = run("check_nextjs.py", good)
T.status_is("next good", c, "next.server-actions", "PASS", out)
T.status_is("next good", c, "next.public-env-secrets", "PASS", out)
static_ok = T.tree({"next.config.mjs": "export default { output: 'export', async headers() { return [] } }\n", "public/_headers": "/*\n  X-Frame-Options: DENY\n"})
rc, c, out = run("check_nextjs.py", static_ok)
T.status_is("next static export with _headers", c, "next.static-export-headers", "PASS", out)

# ---------- Fly + Supabase ----------
bad = T.tree({
    "fly.toml": 'app = "bot"\n[env]\n  LOG_LEVEL = "info"\n  SUPABASE_SERVICE_KEY = "x"\n[http_service]\n  force_https = false\n[[services]]\n  internal_port = 5432\n  [[services.ports]]\n    port = 5432\n',
    "infra/supabase/migrations/001.sql": "create table public.trades (id int);\ncreate table picks (id int);\nalter table public.trades enable row level security;\n",
    "src/components/Admin.tsx": "'use client'\nconst k = process.env.SUPABASE_SERVICE_ROLE_KEY\n",
})
rc, c, out = run("check_fly_supabase.py", bad)
for cid in ("fly.env-secrets", "fly.exposure", "supabase.rls", "supabase.service-role"):
    T.status_is("fly/supabase bad", c, cid, "FAIL", out)
T.expect("supabase: the table without RLS is named, the one with it is not", "picks" in c.get("supabase.rls", {}).get("evidence", "") and "trades" not in c.get("supabase.rls", {}).get("evidence", ""))
good = T.tree({
    "fly.toml": 'app = "bot"\n[env]\n  LOG_LEVEL = "info"\n[http_service]\n  internal_port = 8080\n  force_https = true\n',
    "infra/supabase/migrations/001.sql": "create table public.trades (id int);\ncreate table picks (id int);\nalter table public.trades enable row level security;\nALTER TABLE picks ENABLE ROW LEVEL SECURITY;\n",
    "src/server/db.ts": "const k = process.env.SUPABASE_SERVICE_ROLE_KEY\n",
})
rc, c, out = run("check_fly_supabase.py", good)
T.expect("fly/supabase good: all PASS", rc == 0 and len(c) == 4 and all(v["status"] == "PASS" for v in c.values()), out[-500:])
nomig = T.tree({"package.json": json.dumps({"dependencies": {"@supabase/supabase-js": "2"}}), "src/db.ts": "import { createClient } from '@supabase/supabase-js'\n"})
rc, c, out = run("check_fly_supabase.py", nomig)
T.status_is("supabase without migrations", c, "supabase.rls", "UNKNOWN", out)

# ---------- Apps Script ----------
gk = T.fake_key("google", 9)
bad = T.tree({
    "appsscript.json": json.dumps({"webapp": {"access": "ANYONE_ANONYMOUS", "executeAs": "USER_DEPLOYING"},
                                   "oauthScopes": ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/script.external_request"]}),
    "Index.html": "<script>const KEY = '%s';</script>\n" % gk,
    "Code.gs": "function doGet() { return HtmlService.createHtmlOutputFromFile('Index') }\n",
})
rc, c, out = run("check_gas.py", bad)
for cid in ("gas.webapp-access", "gas.scopes", "gas.keys-in-code"):
    T.status_is("gas bad", c, cid, "FAIL", out)
T.expect("gas: anonymous + execute-as-deployer is critical", c.get("gas.webapp-access", {}).get("severity") == "critical")
T.expect("gas: the key value is never printed", gk not in out)
good = T.tree({
    "appsscript.json": json.dumps({"webapp": {"access": "DOMAIN", "executeAs": "USER_ACCESSING"}, "oauthScopes": ["https://www.googleapis.com/auth/drive.file"]}),
    "Code.gs": "function key() { return PropertiesService.getScriptProperties().getProperty('MAPS_KEY') }\n",
})
rc, c, out = run("check_gas.py", good)
T.expect("gas good: all PASS", rc == 0 and len(c) == 3 and all(v["status"] == "PASS" for v in c.values()), out[-400:])
auto = T.tree({"appsscript.json": json.dumps({"timeZone": "America/Los_Angeles"}), "Code.gs": "function f(){}\n"})
rc, c, out = run("check_gas.py", auto)
T.status_is("gas auto-detected scopes", c, "gas.scopes", "UNKNOWN", out)

# ---------- Railway ----------
bad = T.tree({"railway.json": json.dumps({"deploy": {"startCommand": "npm run dev"}}), "src/server.js": "console.log(process.env)\n"})
rc, c, out = run("check_railway.py", bad)
T.status_is("railway bad", c, "railway.env-dump", "FAIL", out)
T.status_is("railway bad", c, "railway.config", "FAIL", out)
T.expect("railway: cannot_see gives the count-only command", "grep -c" in out)
good = T.tree({"railway.json": json.dumps({"deploy": {"startCommand": "node dist/server.js"}}), "src/server.js": "console.log(Object.keys(process.env).length)\n"})
rc, c, out = run("check_railway.py", good)
T.expect("railway good: all PASS", rc == 0 and all(v["status"] == "PASS" for v in c.values()), out[-300:])

# ---------- find_embedders (moved) ----------
site = T.tree({"index.html": '<iframe src="https://demo.example.test/"></iframe>\n', "node_modules/x.html": '<iframe src="https://demo.example.test/"></iframe>\n'})
r = subprocess.run(["bash", os.path.join(S, "find_embedders.sh"), "demo.example.test", site], capture_output=True, text=True)
T.expect("embedders: found once, node_modules skipped", r.stdout.count("index.html") == 1 and "node_modules" not in r.stdout)

# ---------- Phase 4 false-positive regressions ----------
pages = T.tree({"wrangler.app.toml": 'name = "site"\npages_build_output_dir = "out"\n',
                "public/_headers": "/*\n  Content-Security-Policy: frame-ancestors 'self'\n  Strict-Transport-Security: max-age=31536000\n",
                ".claude/worktrees/old/public/_headers": "/api/*\n  X-Frame-Options: DENY\n"})
rc, c, out = run("check_cloudflare.py", pages)
T.status_is("FP: Pages default", c, "cf.headers.nosniff", "PASS", out)
T.status_is("FP: Pages default", c, "cf.headers.referrer", "PASS", out)
T.expect("FP: _headers under a dot-folder worktree is not read", ".claude" not in out)
worker = T.tree({"wrangler.toml": 'name = "w"\nmain = "src/index.ts"\n', "src/index.ts": "export default {}\n"})
rc, c, out = run("check_cloudflare.py", worker)
T.status_is("a Worker gets no Pages default", c, "cf.headers.nosniff", "FAIL", out)
py = T.tree({"infra/supabase/migrations/001.sql": "create table t (id int);\nalter table t enable row level security;\n",
             "src/bot/db/client.py": "key = os.environ['SUPABASE_SERVICE_ROLE_KEY']\n"})
rc, c, out = run("check_fly_supabase.py", py)
T.status_is("FP: server-side Python named client.py is not browser code", c, "supabase.service-role", "PASS", out)

ci_pages = T.tree({".github/workflows/daily.yml": "jobs:\n  d:\n    steps:\n      - run: npx wrangler pages deploy dist --project-name news-app\n", "package.json": "{}"})
rc, c, out = run("check_cloudflare.py", ci_pages)
T.status_is("Pages deployed from CI also gets the default", c, "cf.headers.nosniff", "PASS", out)
T.status_is("...but framing is still the repo's job", c, "cf.headers.framing", "FAIL", out)

wk_comment = T.tree({"wrangler.toml": 'name = "coach"\nmain = "src/worker/index.ts"\n[assets]\ndirectory = "./dist"\n',
                     "scripts/deploy.sh": "#!/bin/sh\n# do NOT run `wrangler pages deploy dist` from here; this is a Worker\nnpx wrangler deploy\n"})
rc, c, out = run("check_cloudflare.py", wk_comment)
T.status_is("a Worker whose script only MENTIONS pages deploy in a comment gets no Pages default", c, "cf.headers.nosniff", "FAIL", out)

# ---------- Phase 5 audit: platform bypasses ----------
weak = T.tree({"wrangler.toml": 'name = "w"\nmain = "src/i.ts"\n', "public/_headers": "/*\n  X-Frame-Options: ALLOWALL\n  Strict-Transport-Security: max-age=0\n",
               "src/i.ts": "// sets X-Content-Type-Options and Referrer-Policy later\nexport default {}\n"})
rc, c, out = run("check_cloudflare.py", weak)
T.status_is("audit #9: X-Frame-Options ALLOWALL does not protect", c, "cf.headers.framing", "FAIL", out)
T.status_is("audit #9: HSTS max-age=0 does not protect", c, "cf.headers.hsts", "FAIL", out)
T.status_is("audit #9: header names in a comment are not headers", c, "cf.headers.nosniff", "FAIL", out)
rls = T.tree({"supabase/migrations/001.sql": "create table public.picks (id int);\nalter table public.picks enable row level security;\n",
              "supabase/migrations/002.sql": "alter table public.picks disable row level security;\n"})
rc, c, out = run("check_fly_supabase.py", rls)
T.status_is("audit #10: RLS enabled then disabled is off", c, "supabase.rls", "FAIL", out)
pol = T.tree({"supabase/migrations/001.sql": "create table t (id int);\nalter table t enable row level security;\ncreate policy p on t for all using (true);\n"})
rc, c, out = run("check_fly_supabase.py", pol)
T.status_is("audit #10: a write policy using (true) opens the table", c, "supabase.rls", "FAIL", out)
cm = T.tree({"supabase/migrations/001.sql": "create table t (id int);\n-- alter table t enable row level security;\n"})
rc, c, out = run("check_fly_supabase.py", cm)
T.status_is("audit: a commented-out ENABLE does not count", c, "supabase.rls", "FAIL", out)
vite = T.tree({"package.json": json.dumps({"dependencies": {"@supabase/supabase-js": "2"}}), "supabase/migrations/1.sql": "",
               "src/lib/db.ts": "export const admin = createClient(url, import.meta.env.VITE_SUPABASE_ADMIN_KEY)\n",
               "src/App.tsx": "import { admin } from './lib/db'\n"})
rc, c, out = run("check_fly_supabase.py", vite)
T.status_is("audit #11: a VITE_ admin key ships to the browser", c, "supabase.service-role", "FAIL", out)
shared = T.tree({"supabase/migrations/1.sql": "", "src/lib/db.ts": "export const k = process.env.SUPABASE_SERVICE_ROLE_KEY\n",
                 "src/components/Page.tsx": "import { k } from '../lib/db'\n"})
rc, c, out = run("check_fly_supabase.py", shared)
T.status_is("audit #11: a service key in a module a client component imports", c, "supabase.service-role", "FAIL", out)
import random as _r
hexkey = "%032x" % _r.Random(3).getrandbits(128)
pw = (lambda g: "".join(g.choice("abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!#%") for _ in range(22)))(_r.Random(4))
gk = T.tree({"appsscript.json": json.dumps({"webapp": {"access": "DOMAIN"}, "oauthScopes": []}),
             "Code.gs": "var WEATHER_KEY = '%s';\nvar DB_PASSWORD = '%s';\n" % (hexkey, pw)})
rc, c, out = run("check_gas.py", gk)
T.status_is("audit #12: an unshaped hex key and a password literal", c, "gas.keys-in-code", "FAIL", out)
T.expect("audit #12: neither value printed", hexkey not in out and pw not in out)
ign = T.git_init(T.tree({".gitignore": "appsscript.json\n", ".clasp.json": "{}", "Code.gs": "function f(){}\n"}))
open(os.path.join(ign, "appsscript.json"), "w").write(json.dumps({"webapp": {"access": "ANYONE_ANONYMOUS", "executeAs": "USER_DEPLOYING"}}))
rc, c, out = run("check_gas.py", ign)
T.status_is("audit #2: a git-ignored appsscript.json is still read", c, "gas.webapp-access", "FAIL", out)
pwd = (lambda g: "".join(g.choice("abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(22)))(_r.Random(6))
leak = T.tree({"railway.json": json.dumps({"deploy": {"startCommand": "DATABASE_URL=postgres://admin:%s@db.example.com/app node server.js" % pwd}})})
rc, c, out = run("check_railway.py", leak)
T.expect("audit #5: a password in the start command never reaches the output", pwd not in out and c.get("railway.config", {}).get("status") == "PASS", out[-300:])

# ---------- second audit: open RLS policy variants ----------
for label, pol in (("no FOR clause (defaults to ALL)", "create policy p on t to authenticated using (true);"), ("using (1=1)", "create policy p on t for update using (1=1);"),
                   ("using (true is true)", "create policy p on t for delete using (true is true);")):
    rp = T.tree({"supabase/migrations/001.sql": "create table t (id int);\nalter table t enable row level security;\n" + pol + "\n"})
    rc, c, out = run("check_fly_supabase.py", rp)
    T.status_is("audit 2: RLS %s" % label, c, "supabase.rls", "FAIL", out)
rp = T.tree({"supabase/migrations/001.sql": "create table t (id int);\nalter table t enable row level security;\ncreate policy p on t for select using (true);\n"})
rc, c, out = run("check_fly_supabase.py", rp)
T.status_is("a public-read SELECT policy using (true) is allowed", c, "supabase.rls", "PASS", out)

T.finish()
