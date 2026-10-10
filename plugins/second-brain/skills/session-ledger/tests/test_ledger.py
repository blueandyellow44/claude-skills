#!/usr/bin/env python3
"""ledger.py cases. Unhappy paths first. Run: python3 tests/test_ledger.py"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
L = os.path.join(HERE, "..", "scripts", "ledger.py")
D = tempfile.mkdtemp()
ENV = {**os.environ, "SESSION_MANIFEST_DIR": D}
res = []


def run(*args):
    return subprocess.run([sys.executable, L, "--session", "t1", *args], capture_output=True, text=True, env=ENV)


def chk(name, ok, extra=""):
    res.append(bool(ok))
    print("PASS" if ok else "FAIL", name, "" if ok else extra)


chk("checking a missing item fails loud", run("check", "req", "1").returncode != 0)
chk("a requirement needs text", run("req").returncode != 0)
chk("a path-like session id is refused",
    subprocess.run([sys.executable, L, "--session", "../x", "show"], capture_output=True, env=ENV).returncode != 0)
run("request", "build the session manager")
run("req", "drift checks stay proportionate")
run("req", "unknown is reported, never collapsed")
run("done-when", "every suite passes")
r = run("decide", "gate advisory", "--why", "3 of 3 real blocks were wrong")
led = json.load(open(os.path.join(D, "t1.ledger.json")))
chk("request, requirements, done-when and decision recorded",
    led["request"] and len(led["requirements"]) == 2 and len(led["done_when"]) == 1
    and led["decisions"][0]["why"].startswith("3 of 3"))
run("check", "req", "1")
r = run("show", "--open")
chk("--open hides met items", "proportionate" not in r.stdout and "never collapsed" in r.stdout, r.stdout)
run("drop", "req", "2", "--why", "owner cut it")
led = json.load(open(os.path.join(D, "t1.ledger.json")))
chk("a dropped requirement is kept as history with its reason",
    len(led["requirements"]) == 1 and led["dropped"][0]["why"] == "owner cut it")
chk("updated timestamp set", led.get("updated", 0) > 0)
print("%d / %d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
