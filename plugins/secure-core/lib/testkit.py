"""testkit.py - fixture helpers for the suite's own tests.

Fixtures are built in temp dirs at test time. Key-shaped strings are generated
here from a seeded RNG and never stored in a file in this repo.
"""
import json
import os
import random
import string
import subprocess
import sys
import tempfile

_pass = 0
_fail = 0
_made = []


def _cleanup():
    import shutil
    for d in _made:
        shutil.rmtree(d, ignore_errors=True)


import atexit  # noqa: E402
atexit.register(_cleanup)  # fixtures are deleted when the test file exits


def tree(files, base=None):
    if base is None:
        base = tempfile.mkdtemp(prefix="sl-fixture-")
        _made.append(base)
    for rel, content in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
    return base


def git_init(repo):
    for c in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"], ["add", "-A"], ["commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", repo] + c, capture_output=True, check=False)
    return repo


def fake_key(kind, seed=7):
    r = random.Random(seed)
    pick = lambda a, n: "".join(r.choice(a) for _ in range(n))
    al = string.ascii_letters + string.digits
    return {
        "google": "AIza" + pick(al + "-_", 35),
        "stripe": "sk_" + "live_" + pick(al, 40),
        "anthropic": "sk-" + "ant-api03-" + pick(al, 60),
        "github": "gh" + "p_" + pick(al, 36),
    }[kind]


def run(script, repo, *args):
    r = subprocess.run([sys.executable, script, repo] + list(args), capture_output=True, text=True)
    try:
        checks = {c["id"]: c for c in json.loads(r.stdout)["checks"]}
    except (ValueError, KeyError):
        checks = {}
    cov = os.environ.get("SL_COVERAGE")
    if cov:  # Phase 3 matrix: every (script, check id, status) a fixture produced
        with open(cov, "a") as fh:
            for c in checks.values():
                fh.write("%s\t%s\t%s\n" % (os.path.basename(script), c["id"], c["status"]))
    return r.returncode, checks, r.stdout + r.stderr


def expect(name, cond, note=""):
    global _pass, _fail
    if cond:
        _pass += 1
        print("ok   " + name)
    else:
        _fail += 1
        print("FAIL " + name + (("  (" + note + ")") if note else ""))


def status_is(name, checks, cid, want, out=""):
    got = checks.get(cid, {}).get("status")
    expect("%s: %s is %s" % (name, cid, want), got == want, "got %s; ids=%s; %s" % (got, sorted(checks)[:12], out[-300:]))


def finish():
    print("%d passed, %d failed" % (_pass, _fail))
    sys.exit(1 if _fail else 0)
