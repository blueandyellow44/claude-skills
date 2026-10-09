#!/usr/bin/env python3
"""scan_captures.py - find secret values in captured session transcripts
without printing them.

  scan_captures.py [DIR ...] [--json]

Default DIRs: four capture folders under the notes root in VAULT below;
pass DIRs explicitly to scan anywhere else.
Runs gitleaks over plain files with the value fully redacted, after proving
the detector on planted fake keys. Prints RULE  path:line, never the match.

Exit: 0 clean, 1 findings, 2 detector not proven or not installed (report
"not run", never "clean").

STAGED: nothing schedules this. Wiring it into an automated commit is a
standing change for the owner; the steps are in the secure-launch README.
"""
import json
import os
import random
import shutil
import string
import subprocess
import sys
import tempfile

# Folders to scan when none are passed: SECURE_CAPTURE_DIRS, separated like PATH.
CAPTURE_DIRS_ENV = "SECURE_CAPTURE_DIRS"


def gitleaks(path, report):
    empty = os.path.join(os.path.dirname(report), "noignore")
    os.makedirs(empty, exist_ok=True)
    subprocess.run(["gitleaks", "dir", path, "-c", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gitleaks-suite.toml"),
                    "-i", empty, "--ignore-gitleaks-allow", "--redact=100", "--no-banner", "-f", "json", "-r", report],
                   capture_output=True, text=True)
    try:
        return json.load(open(report))
    except (OSError, ValueError):
        return None


def prove(work):
    r = random.Random(11)
    al = string.ascii_letters + string.digits
    canary = os.path.join(work, "canary")
    os.makedirs(canary)
    with open(os.path.join(canary, "session.md"), "w") as fh:
        fh.write("Ran the command and it printed:\n")
        fh.write("GOOGLE_MAPS_KEY=AIza" + "".join(r.choice(al + "-_") for _ in range(35)) + "\n")
        fh.write("stripe " + "sk_" + "live_" + "".join(r.choice(al) for _ in range(40)) + "\n")
    got = gitleaks(canary, os.path.join(work, "canary.json"))
    return got is not None and len(got) >= 2


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not shutil.which("gitleaks"):
        print("gitleaks not installed (brew install gitleaks): capture scan NOT RUN")
        return 2
    dirs = args or [os.path.expanduser(d) for d in os.environ.get(CAPTURE_DIRS_ENV, "").split(os.pathsep) if d]
    if not dirs:
        print("no capture folders: pass them as arguments or set %s; capture scan NOT RUN" % CAPTURE_DIRS_ENV)
        return 2
    work = tempfile.mkdtemp(prefix="capscan-")
    try:
        if not prove(work):
            print("DETECTOR NOT PROVEN on planted keys: capture scan NOT RUN")
            return 2
        findings, scanned = [], []
        for i, d in enumerate(dirs):
            if not os.path.isdir(d):
                print("skipped (not found): %s" % d)
                continue
            got = gitleaks(d, os.path.join(work, "r%d.json" % i))
            if got is None:
                print("SCAN FAILED on %s: capture scan NOT RUN" % d)
                return 2
            scanned.append(d)
            for f in got:
                findings.append({"rule": f.get("RuleID"), "file": f.get("File"), "line": f.get("StartLine")})
        if as_json:
            print(json.dumps({"scanned": scanned, "findings": findings}, indent=1))
        else:
            print("detector proven; scanned %d folder(s); %d finding(s)" % (len(scanned), len(findings)))
            for f in findings:
                print("  %s  %s:%s" % (f["rule"], f["file"], f["line"]))
        return 1 if findings else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
