#!/usr/bin/env python3
"""secure-gate tests: the gate refuses FAIL and unaccepted UNKNOWN, the deploy
gate stops a build, the pre-push hook refuses, the vendored copy runs, and the
CI template passes the suite's own pinning check. Known-bad first."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "secure-core", "lib"))
import ledger  # noqa: E402
import testkit as T  # noqa: E402

S = os.path.join(HERE, "..", "scripts")
TPL = os.path.join(HERE, "..", "templates")
GATE = os.path.join(S, "gate.py")
P = ledger.result("a", "t", "PASS", "x:1")
F = ledger.result("b", "t", "FAIL", "x:2", severity="high", fix="f")
U = ledger.result("c", "t", "UNKNOWN", "x:3", reason="tool missing")


def write_ledger(results, repo=None, complete=True):
    repo = repo or T.tree({})
    led = ledger.build(repo, [dict(r) for r in results], [], {"secure-app/check_app.py": "ran: %d checks" % len(results)})
    if complete:
        led["complete"] = True
    p = os.path.join(repo, "findings.json")
    json.dump(led, open(p, "w"))
    return repo, p


def gate(p, *a):
    return subprocess.run([sys.executable, GATE, p] + list(a), capture_output=True, text=True)


repo, p = write_ledger([P, F])
T.expect("gate: a FAIL refuses (exit 1)", gate(p, "--repo", repo).returncode == 1)
repo, p = write_ledger([P, U])
r = gate(p, "--repo", repo)
T.expect("gate: an UNKNOWN alone refuses (exit 1), it is never a pass", r.returncode == 1 and "BLOCKING UNKNOWN c" in r.stdout, r.stdout)
repo, p = write_ledger([])
T.expect("gate: an empty ledger refuses (nothing measured)", gate(p, "--repo", repo).returncode == 1)
repo, p = write_ledger([P])
led = json.load(open(p)); led["counts"]["PASS"] = 5; json.dump(led, open(p, "w"))
T.expect("gate: hand-edited counts are a gate error (exit 2)", gate(p, "--repo", repo).returncode == 2)
repo, p = write_ledger([P])
led = json.load(open(p)); led["results"][0]["status"] = "WARN"; json.dump(led, open(p, "w"))
T.expect("gate: a status outside PASS/FAIL/UNKNOWN is a gate error (exit 2)", gate(p, "--repo", repo).returncode == 2)
repo, p = write_ledger([P])
led = json.load(open(p)); led["generated_at"] = "2020-01-01T00:00:00+00:00"; json.dump(led, open(p, "w"))
T.expect("gate: a stale ledger refuses with --max-age-hours", gate(p, "--repo", repo, "--max-age-hours", "24").returncode == 1)
repo, p = write_ledger([P])
T.expect("gate: --tests-from with no declared command refuses (gate.tests UNKNOWN)", gate(p, "--repo", repo, "--tests-from", "security/gate.json").returncode == 1)
repo = T.tree({"security/gate.json": json.dumps({"test_command": "exit 3"})})
repo, p = write_ledger([P], repo)
T.expect("gate: a failing security test command refuses", gate(p, "--repo", repo, "--tests-from", "security/gate.json").returncode == 1)
# known-good
repo, p = write_ledger([P])
T.expect("gate: all PASS passes (exit 0)", gate(p, "--repo", repo).returncode == 0)
import datetime
TODAY = datetime.date.today().isoformat()
repo = T.tree({"security/accepted.json": json.dumps({"accepted": [{"id": "c", "reason": "pip-audit not used here, ruled", "ruled": TODAY, "evidence": "x:3"}]}),
               "security/gate.json": json.dumps({"test_command": "true"})})
repo, p = write_ledger([P, U], repo)
r = gate(p, "--repo", repo, "--tests-from", "security/gate.json")
T.expect("gate: an accepted UNKNOWN passes AND is still printed", r.returncode == 0 and ("ACCEPTED (%s" % TODAY) in r.stdout, r.stdout)
r = subprocess.run([sys.executable, GATE, p, "--repo", repo], capture_output=True, text=True, env=dict(os.environ, GITHUB_ACTIONS="true", GITHUB_STEP_SUMMARY=os.path.join(repo, "summary.md")))
T.expect("gate: in Actions the accepted item is a ::warning and lands in the step summary", "::warning::" in r.stdout and "ACCEPTED" in open(os.path.join(repo, "summary.md")).read())

# ---------- Phase 5 audit: the bypasses it reproduced are now refused ----------
other = T.tree({})
_, p_other = write_ledger([P], other)
here = T.tree({})
import shutil
shutil.copy(p_other, os.path.join(here, "findings.json"))
r = gate(os.path.join(here, "findings.json"), "--repo", here)
T.expect("audit #1: a ledger copied or committed from another repo is a gate error", r.returncode == 2 and "not" in r.stdout, r.stdout)
repo, p = write_ledger([P], complete=False)
T.expect("audit #1: a ledger from a run that did not finish is a gate error", gate(p, "--repo", repo).returncode == 2)
repo, p = write_ledger([P])
led = json.load(open(p)); led["adapters"] = {}; json.dump(led, open(p, "w"))
T.expect("audit #1: a ledger with no adapter that ran is a gate error", gate(p, "--repo", repo).returncode == 2)
repo, p = write_ledger([P])
led = json.load(open(p)); led["generated_at"] = "2026-01-01T00:00:00+00:00"; json.dump(led, open(p, "w"))
T.expect("audit #1: a stale ledger refuses by default (6 h)", gate(p, "--repo", repo).returncode == 1)
CRIT = ledger.result("secrets.history", "t", "FAIL", "src/a.ts x1", severity="critical", fix="f")
HIGH = ledger.result("secrets.history", "t", "FAIL", "src/a.ts x1", severity="high", fix="f")
def accept(entries):
    return T.tree({"security/accepted.json": json.dumps({"accepted": entries})})
repo = accept([{"id": "secrets.history", "reason": "r", "ruled": TODAY, "evidence": "src/a.ts x1"}])
repo, p = write_ledger([CRIT], repo)
T.expect("audit #7: a critical FAIL can never be accepted", gate(p, "--repo", repo).returncode == 1)
repo = accept([{"id": "secrets.history", "reason": "r", "ruled": TODAY, "evidence": "src/a.ts x1"}])
repo, p = write_ledger([dict(HIGH, evidence="src/b.ts x1")], repo)
T.expect("audit #7: an acceptance does not cover a new leak under the same id", gate(p, "--repo", repo).returncode == 1)
repo = accept([{"id": "secrets.history", "reason": "r", "ruled": "2025-01-01", "evidence": "src/a.ts x1"}])
repo, p = write_ledger([HIGH], repo)
T.expect("audit #7: an expired acceptance (90 days) is not honored", gate(p, "--repo", repo).returncode == 1)
repo = accept([{"id": "secrets.history", "reason": "r", "ruled": "y", "evidence": "src/a.ts x1"}])
repo, p = write_ledger([HIGH], repo)
T.expect("audit #7: a ruling that is not a date is a gate error", gate(p, "--repo", repo).returncode == 2)
repo = accept([{"id": "secrets.history", "reason": "ruled false positive", "ruled": TODAY, "evidence": "src/a.ts x1"}])
repo, p = write_ledger([HIGH], repo)
T.expect("an exact, dated, unexpired acceptance of a high FAIL passes", gate(p, "--repo", repo).returncode == 0)
r = subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "secure-core", "scripts", "secure_launch.py"), T.tree({"package.json": "[]", "src/a.ts": "x"}), "--out", T.tree({})], capture_output=True, text=True)
T.expect("audit #1: a malformed package.json does not crash the orchestrator into a missing ledger (exit is 0/1/3, or 4 with no ledger)", r.returncode in (0, 1, 3, 4), r.stderr[-200:])

# ---------- vendoring + pre-push + deploy gate, on a throwaway repo ----------
target = T.git_init(T.tree({"package.json": json.dumps({"scripts": {"test:api": "node -e \"process.exit(1)\""}}), "src/index.js": "export default 1\n",
                            ".gitignore": ".dev.vars\n"}))
r = subprocess.run([sys.executable, os.path.join(S, "install_gate.py"), target, "--with-ci", "--with-pre-push", "--with-deploy-gate"], capture_output=True, text=True)
T.expect("install: vendors the suite and the three templates", r.returncode == 0 and os.path.exists(os.path.join(target, ".secure-launch/secure-core/lib/ledger.py"))
         and os.path.exists(os.path.join(target, ".github/workflows/secure-launch.yml")) and os.path.exists(os.path.join(target, "scripts/secure-gate.mjs")), r.stdout + r.stderr)
T.expect("install: testkit is not vendored", not os.path.exists(os.path.join(target, ".secure-launch/secure-core/lib/testkit.py")))
r = subprocess.run([sys.executable, os.path.join(S, "install_gate.py"), target, "--with-ci"], capture_output=True, text=True)
T.expect("install: refuses to overwrite what exists", r.returncode == 2)
out = T.tree({})
r = subprocess.run([sys.executable, os.path.join(target, ".secure-launch/secure-core/scripts/secure_launch.py"), target, "--out", out], capture_output=True, text=True)
T.expect("vendored: the orchestrator runs from .secure-launch and writes a ledger", os.path.exists(os.path.join(out, "findings.json")), r.stdout + r.stderr[-300:])
led = json.load(open(os.path.join(out, "findings.json")))
T.expect("vendored: no adapter ran as 'not found' (every plugin resolved)", not any(x["id"].endswith(".run") for x in led["results"]), str([x["id"] for x in led["results"] if x["id"].endswith(".run")]))
# pre-push: the clean throwaway repo passes; a planted debug route then refuses
r = subprocess.run(["bash", os.path.join(target, ".secure-launch/pre-push")], cwd=target, capture_output=True, text=True)
T.expect("pre-push: a clean repo passes", r.returncode == 0, (r.stdout + r.stderr)[-300:])
open(os.path.join(target, "src", "debug.js"), "w").write("app.get('/api/debug/env', (c) => c.json(Object.keys(c.env)))\n")
r = subprocess.run(["bash", os.path.join(target, ".secure-launch/pre-push")], cwd=target, capture_output=True, text=True)
T.expect("pre-push: refuses once a FAIL appears", r.returncode == 1 and "app.debug-routes" in r.stdout, (r.stdout + r.stderr)[-300:])
os.remove(os.path.join(target, "src", "debug.js"))
r = subprocess.run(["bash", os.path.join(target, ".secure-launch/pre-push")], cwd=target, capture_output=True, text=True, env=dict(os.environ, SECURE_LAUNCH_SKIP="1"))
T.expect("pre-push: the skip is allowed but says nothing was checked", r.returncode == 0 and "SKIPPED" in r.stderr)
# deploy gate: a failing test command stops the deploy before the build marker is written
deploy = os.path.join(target, "scripts", "deploy.mjs")
open(deploy, "w").write("import { secureGate } from './secure-gate.mjs';\nimport { writeFileSync } from 'node:fs';\n"
                        "secureGate({ root: %s, testCommand: ['npm', 'run', '-s', 'test:api'], ledger: false });\nwriteFileSync(%s, 'built');\n"
                        % (json.dumps(target), json.dumps(os.path.join(target, "BUILT"))))
r = subprocess.run(["node", deploy], capture_output=True, text=True)
T.expect("deploy gate: a failing test refuses and the build never starts", r.returncode == 1 and not os.path.exists(os.path.join(target, "BUILT")), r.stderr[-200:])
pj = json.load(open(os.path.join(target, "package.json"))); pj["scripts"]["test:api"] = "node -e \"process.exit(0)\""; json.dump(pj, open(os.path.join(target, "package.json"), "w"))
r = subprocess.run(["node", deploy], capture_output=True, text=True)
T.expect("deploy gate: passing tests let the build run", r.returncode == 0 and os.path.exists(os.path.join(target, "BUILT")), r.stderr[-200:])

# ---------- the CI template passes the suite's own pinning check ----------
ci = T.tree({".github/workflows/secure-launch.yml": open(os.path.join(TPL, "github-workflow.yml")).read()})
rc, c, out = T.run(os.path.join(HERE, "..", "..", "secure-supply-chain", "scripts", "check_pinning.py"), ci)
T.status_is("CI template", c, "actions.pinned", "PASS", out)
T.status_is("CI template", c, "actions.secret-scope", "PASS", out)

# ---------- second audit: acceptance bound to the full hit list; expiry clamped; future rulings refused; ledger bound to a commit ----------
sys.path.insert(0, os.path.join(HERE, "..", "..", "secure-core", "lib"))
eight = ["src/a.ts:%d DELETE /x/:id" % i for i in range(8)]
twelve = eight + ["src/b.ts:%d DELETE /y/:id" % i for i in range(4)]
R8 = ledger.result("app.object-writes", "t", "FAIL", ledger.join_hits(eight, 8, "; "), severity="high", fix="f")
R12 = ledger.result("app.object-writes", "t", "FAIL", ledger.join_hits(twelve, 8, "; "), severity="high", fix="f")
repo = accept([{"id": "app.object-writes", "reason": "r", "ruled": TODAY, "evidence": R8["evidence"]}])
repo, p = write_ledger([R12], repo)
T.expect("audit 2: four new hits beyond the shown eight break the acceptance", gate(p, "--repo", repo).returncode == 1)
repo = accept([{"id": "secrets.history", "reason": "r", "ruled": "2026-01-02", "expires": "2099-12-31", "evidence": "src/a.ts x1"}])
repo, p = write_ledger([HIGH], repo)
T.expect("audit 2: an expiry beyond ruled + 90 days is clamped (old ruling, not honored)", gate(p, "--repo", repo).returncode == 1)
repo = accept([{"id": "secrets.history", "reason": "r", "ruled": "2099-01-01", "evidence": "src/a.ts x1"}])
repo, p = write_ledger([HIGH], repo)
T.expect("audit 2: a ruling dated in the future is a gate error", gate(p, "--repo", repo).returncode == 2)
gr = T.git_init(T.tree({"src/a.ts": "export const a = 1\n"}))
outd = T.tree({})
subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "secure-core", "scripts", "secure_launch.py"), gr, "--out", outd], capture_output=True)
open(os.path.join(gr, "src", "b.ts"), "w").write("app.get('/api/debug/env', (c) => c.json({}))\n")
r = gate(os.path.join(outd, "findings.json"), "--repo", gr)
T.expect("audit 2: a ledger from before a new change is refused (commit/tree bound)", r.returncode == 2 and "another commit" in r.stdout, r.stdout[-200:])

# ---------- first real CI run (a coaching app's PR): bytecode in a COMMITTED .secure-launch must not look like a new tree ----------
ci = T.git_init(T.tree({"src/a.ts": "export const a = 1\n"}))
subprocess.run([sys.executable, os.path.join(S, "install_gate.py"), ci, "--with-ci"], capture_output=True)
subprocess.run(["git", "-C", ci, "add", "-A"], capture_output=True)
subprocess.run(["git", "-C", ci, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "gate"], capture_output=True)
outd = T.tree({})
subprocess.run([sys.executable, os.path.join(ci, ".secure-launch/secure-core/scripts/secure_launch.py"), ci, "--out", outd], capture_output=True)
r = subprocess.run([sys.executable, os.path.join(ci, ".secure-launch/secure-gate/scripts/gate.py"), os.path.join(outd, "findings.json"), "--repo", ci], capture_output=True, text=True)
T.expect("CI shape: vendored, committed, python bytecode written -> the gate judges the ledger (no tree-mismatch error)", r.returncode in (0, 1) and "another commit" not in r.stdout, r.stdout[-300:])
open(os.path.join(ci, "src", "b.ts"), "w").write("export const b = 2\n")
r = subprocess.run([sys.executable, os.path.join(ci, ".secure-launch/secure-gate/scripts/gate.py"), os.path.join(outd, "findings.json"), "--repo", ci], capture_output=True, text=True)
T.expect("...while a real source change after the ledger is still refused", r.returncode == 2 and "another commit" in r.stdout, r.stdout[-200:])

T.finish()
