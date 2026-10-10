#!/usr/bin/env python3
"""capability-candidates.py stage rules, unhappy paths first.
Run: python3 test_capability_candidates.py"""
import os
import subprocess
import sys
import tempfile

S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capability-candidates.py")
ENV = {**os.environ, "CAPABILITY_LEDGER": os.path.join(tempfile.mkdtemp(), "c.jsonl")}
res = []


def run(*a):
    return subprocess.run([sys.executable, S, *a], capture_output=True, text=True, env=ENV)


def chk(n, r, ok_expected):
    ok = (r.returncode == 0) == ok_expected
    res.append(ok)
    print("PASS" if ok else "FAIL", n, "" if ok else r.stdout + r.stderr)


W = ["add", "--kind", "workflow", "--slug", "moonwalk-fix"]
chk("a workflow without --verify is refused", run(*W, "--stage", "drafted", "--session", "s1",
                                                   "--target", "Skills/_staging/moonwalk-fix"), False)
chk("drafting outside Skills/ is refused", run(*W, "--stage", "drafted", "--session", "s1",
                                                "--target", "/tmp/x", "--verify", "python3 t.py"), False)
chk("honing before any draft is refused", run(*W, "--stage", "honed", "--session", "s2", "--verify", "python3 t.py"), False)
chk("a valid draft is recorded", run(*W, "--stage", "drafted", "--session", "s1",
                                      "--target", "Skills/_staging/moonwalk-fix", "--verify", "python3 t.py"), True)
chk("the drafting session cannot hone its own draft", run(*W, "--stage", "honed", "--session", "s1",
                                                           "--verify", "python3 t.py"), False)
chk("promotion before honing is refused", run(*W, "--stage", "promoted", "--session", "s2",
                                               "--verify", "python3 t.py", "--by", "owner"), False)
chk("a second session hones it", run(*W, "--stage", "honed", "--session", "s2", "--verify", "python3 t.py"), True)
chk("promotion without the owner is refused", run(*W, "--stage", "promoted", "--session", "s3", "--verify", "python3 t.py"), False)
chk("promotion on the owner's word is recorded", run(*W, "--stage", "promoted", "--session", "s3",
                                                      "--verify", "python3 t.py", "--by", "owner"), True)
F = ["add", "--kind", "failure", "--slug", "stale-route", "--session", "s1"]
chk("a failure proposal is recorded", run(*F, "--stage", "proposed", "--target", "hook: x.py"), True)
chk("installing a check needs the owner", run(*F, "--stage", "installed"), False)
r = run("list", "--open")
ok = "stale-route" in r.stdout and "moonwalk-fix" not in r.stdout
res.append(ok); print("PASS" if ok else "FAIL", "list --open hides promoted, shows awaiting", "" if ok else r.stdout)
print("%d / %d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
