#!/usr/bin/env python3
"""gate.py - turn a secure-launch ledger into a ship / do-not-ship decision.

  gate.py LEDGER [--repo R] [--tests-from security/gate.json] [--max-age-hours N]

Refuses (exit 1) on any FAIL and on any UNKNOWN, unless that exact check id is
listed in R/security/accepted.json with a reason and a ruling date. Accepted
items are still printed. An empty ledger refuses: nothing measured is not a
pass. A malformed or internally inconsistent ledger is exit 2.

--tests-from: a JSON file {"test_command": "npm run test:api"} naming the
repo's mutation-proven security tests. The command runs first; a failure
refuses. A missing file becomes UNKNOWN gate.tests (refused unless accepted).

In GitHub Actions it writes ::error / ::warning annotations and a step summary.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402

GHA = os.environ.get("GITHUB_ACTIONS") == "true"


def note(kind, msg):
    if GHA:
        print("::%s::%s" % (kind, msg.replace("\n", " ")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--tests-from")
    ap.add_argument("--max-age-hours", type=float, default=6.0, help="refuse an older ledger (default 6 h)")
    a = ap.parse_args()
    try:
        led = json.load(open(a.ledger))
        results = led["results"]
        for r in results:
            ledger.validate(r)
    except (OSError, ValueError, KeyError, TypeError, ledger.LedgerError) as exc:
        print("GATE ERROR: ledger unusable: %s" % exc)
        return 2
    if ledger.counts(results) != led.get("counts"):
        print("GATE ERROR: ledger counts do not match its results (edited by hand?)")
        return 2
    if os.path.realpath(led.get("repo", "")) != os.path.realpath(a.repo):
        print("GATE ERROR: ledger is for %s, not %s (a committed or copied ledger is never trusted)" % (led.get("repo"), os.path.realpath(a.repo)))
        return 2
    ran = {k: v for k, v in (led.get("adapters") or {}).items() if str(v).startswith("ran")}
    if not ran:
        print("GATE ERROR: ledger records no adapter that ran")
        return 2
    g = led.get("git")
    if g:
        now = ledger.git_state(a.repo) or {}
        if now.get("head") != g.get("head") or now.get("status") != g.get("status"):
            print("GATE ERROR: ledger was made at another commit or working tree (%s); re-run secure-launch" % (g.get("head", "")[:10]))
            return 2
    if led.get("complete") is not True:
        print("GATE ERROR: ledger is not marked complete (the run did not finish)")
        return 2
    if a.max_age_hours and a.max_age_hours > 0:
        try:
            age = datetime.datetime.now().astimezone() - datetime.datetime.fromisoformat(led["generated_at"])
            if age.total_seconds() > a.max_age_hours * 3600:
                print("GATE REFUSED: ledger is %.1f h old (limit %.1f h); re-run secure-launch" % (age.total_seconds() / 3600, a.max_age_hours))
                return 1
        except (KeyError, ValueError):
            print("GATE ERROR: ledger has no usable generated_at")
            return 2
    try:
        accepted = ledger.load_accepted(a.repo)
    except ledger.LedgerError as exc:
        print("GATE ERROR: %s" % exc)
        return 2
    results = list(results)
    if a.tests_from is not None:
        p = a.tests_from if os.path.isabs(a.tests_from) else os.path.join(a.repo, a.tests_from)
        cmd = None
        if os.path.exists(p):
            try:
                cmd = json.load(open(p)).get("test_command")
            except ValueError:
                cmd = None
        if not cmd:
            results.append(ledger.result("gate.tests", "Mutation-proven security tests ran", "UNKNOWN", a.tests_from,
                                         reason="no test_command declared in %s" % a.tests_from))
        else:
            print("running security tests: %s" % cmd)
            rc = subprocess.run(cmd, shell=True, cwd=a.repo).returncode
            if rc == 0:
                results.append(ledger.result("gate.tests", "Mutation-proven security tests ran", "PASS", "%s exited 0" % cmd))
            else:
                results.append(ledger.result("gate.tests", "Mutation-proven security tests ran", "FAIL", "%s exited %d" % (cmd, rc),
                                             severity="high", fix="fix the failing security test; never weaken it to pass"))
    if not results:
        print("GATE REFUSED: the ledger holds no results (nothing measured)")
        note("error", "secure-launch ledger is empty")
        return 1
    blocking, shown = [], []
    for r in results:
        if r["status"] == "PASS":
            continue
        acc = ledger.acceptance(accepted, r)
        tag = "%s %s [%s] %s" % (r["status"], r["id"], r.get("severity", "-"), r.get("reason") or r.get("fix") or "")
        if acc:
            shown.append("ACCEPTED (%s, until %s, %s) %s" % (acc["ruled"], acc["expires"], acc["reason"], tag))
            note("warning", "accepted %s: %s" % (r["id"], acc["reason"]))
        else:
            blocking.append(tag + "  <- " + r["evidence"][:160])
            note("error" if r["status"] == "FAIL" else "warning", "%s %s: %s" % (r["status"], r["id"], r.get("reason") or r.get("fix", "")))
    c = ledger.counts(results)
    head = "secure-launch gate: %d FAIL, %d UNKNOWN, %d PASS (%d accepted)" % (c["FAIL"], c["UNKNOWN"], c["PASS"], len(shown))
    print(head)
    for s in shown:
        print("  " + s)
    for b in blocking:
        print("  BLOCKING " + b)
    if GHA and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write("## %s\n\n" % head)
            fh.write("UNKNOWN is not a pass: each blocks until it runs or is accepted in security/accepted.json.\n\n")
            for b in blocking:
                fh.write("- BLOCKING %s\n" % b.replace("|", "/"))
            for s in shown:
                fh.write("- %s\n" % s.replace("|", "/"))
    if blocking:
        print("GATE REFUSED: %d blocking item(s)" % len(blocking))
        return 1
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
