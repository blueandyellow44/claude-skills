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

T.finish()
