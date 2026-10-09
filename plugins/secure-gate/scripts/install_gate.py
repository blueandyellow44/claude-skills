#!/usr/bin/env python3
"""install_gate.py - vendor the suite's check scripts into a repo so CI and
hooks can run them without the plugins installed. ON REQUEST ONLY: it writes
into the target repo.

  install_gate.py REPO [--with-ci] [--with-pre-push] [--with-deploy-gate] [--dry-run]

Copies secure-core/{lib,scripts} and every other plugin's scripts/ into
REPO/.secure-launch/ (same layout, so _corepath resolves), writes
.secure-launch/VERSION (suite version and source commit), and optionally:
  --with-ci           .github/workflows/secure-launch.yml from the template
  --with-pre-push     .secure-launch/pre-push (the owner links it: ln -s ../../.secure-launch/pre-push .git/hooks/pre-push)
  --with-deploy-gate  scripts/secure-gate.mjs (import it at the top of the deploy script)
Never overwrites an existing file; lists what it would write with --dry-run.
Never commits.
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402

GATE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(GATE)
PLUGINS = ["secure-core", "secure-secrets", "secure-supply-chain", "secure-app", "secure-platform", "secure-gate"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "testkit.py")


def plan(repo, a):
    items = []
    for p in PLUGINS:
        src = os.path.join(ROOT, p)
        for sub in (["lib", "scripts"] if p == "secure-core" else ["scripts"]):
            if os.path.isdir(os.path.join(src, sub)):
                items.append(("tree", os.path.join(src, sub), os.path.join(repo, ".secure-launch", p, sub)))
    t = os.path.join(GATE, "templates")
    if a.with_ci:
        items.append(("file", os.path.join(t, "github-workflow.yml"), os.path.join(repo, ".github", "workflows", "secure-launch.yml")))
    if a.with_pre_push:
        items.append(("file", os.path.join(t, "pre-push"), os.path.join(repo, ".secure-launch", "pre-push")))
    if a.with_deploy_gate:
        items.append(("file", os.path.join(t, "secure-gate.mjs"), os.path.join(repo, "scripts", "secure-gate.mjs")))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--with-ci", action="store_true")
    ap.add_argument("--with-pre-push", action="store_true")
    ap.add_argument("--with-deploy-gate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    items = plan(repo, a)
    clash = [d for _, _, d in items if os.path.exists(d)]
    if clash:
        print("refused: these already exist (remove them or update by hand): %s" % ", ".join(os.path.relpath(c, repo) for c in clash))
        return 2
    for kind, src, dst in items:
        print("%s %s" % ("would write" if a.dry_run else "write", os.path.relpath(dst, repo)))
        if a.dry_run:
            continue
        if kind == "tree":
            shutil.copytree(src, dst, ignore=SKIP)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    if not a.dry_run:
        sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
        with open(os.path.join(repo, ".secure-launch", "VERSION"), "w") as fh:
            fh.write("secure-launch %s from %s\n" % (ledger.SUITE_VERSION, sha))
        print("vendored secure-launch %s (%s); nothing committed" % (ledger.SUITE_VERSION, sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
