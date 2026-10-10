#!/usr/bin/env python3
"""capability-candidates.py - the ledger behind session-wrap's capability harvest.

Tested skills, hooks and executable workflows are more durable fixes than
another lesson; keep lessons as evidence, move repeatable procedures and
enforceable checks into mechanisms that run. When a workflow becomes a skill:
one session can start it and a second hones it.

Each candidate is one JSON line in <vault>/Resources/operator/capability-candidates.jsonl
(append-only; the newest line per slug is its state). The vault is the
SECOND_BRAIN_VAULT environment variable; unset, the script stops.
  kind     workflow (a procedure that worked) | failure (a recurring failure to prevent)
  stage    workflow: drafted -> honed -> promoted   (promotion is the owner's call)
           failure:  proposed -> installed          (installing a hook/check is the owner's call)
  slug, session, evidence, target (skill path or mechanism), verify (command), note

Rules the script enforces, so the wrap cannot skip a step:
  - drafted needs a target under Skills/_staging/ or an existing skill path to improve;
  - honed must come from a DIFFERENT session than the draft (the second session hones);
  - promoted needs a prior honed stage and --by owner;
  - a workflow needs a verify command.

Usage:
  capability-candidates.py add --kind workflow --slug S --stage drafted --session SID \
      --target Skills/_staging/S --verify "python3 Skills/_staging/S/tests/t.py" --evidence "..."
  capability-candidates.py add --kind failure --slug S --stage proposed --session SID \
      --target "hook: ~/.claude/hooks/x.py" --evidence "recurred 2026-10-07: ..."
  capability-candidates.py list [--open]
Env: CAPABILITY_LEDGER overrides the file (tests).
"""
import argparse
import json
import os
import sys
import time



def _ledger():
    """CAPABILITY_LEDGER (tests), else the ledger inside the vault. Never guessed."""
    path = os.environ.get("CAPABILITY_LEDGER")
    if path:
        return path
    vault = os.environ.get("SECOND_BRAIN_VAULT")
    if not vault:
        sys.exit("SECOND_BRAIN_VAULT is not set. Set it to the absolute path of your vault "
                 "(see the plugin README).")
    vault = os.path.abspath(os.path.expanduser(vault))
    if not os.path.isdir(vault):
        sys.exit("vault not found: %s (check SECOND_BRAIN_VAULT)" % vault)
    return os.path.join(vault, "Resources", "operator", "capability-candidates.jsonl")


LEDGER = _ledger()
STAGES = {"workflow": ["drafted", "honed", "promoted"], "failure": ["proposed", "installed"]}


def rows():
    out = []
    try:
        with open(LEDGER, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def history(slug):
    return [r for r in rows() if r.get("slug") == slug]


def add(a):
    if a.stage not in STAGES[a.kind]:
        return "stage %r is not a %s stage (%s)" % (a.stage, a.kind, ", ".join(STAGES[a.kind]))
    hist = history(a.slug)
    stages = [r["stage"] for r in hist]
    if a.kind == "workflow":
        if not a.verify:
            return "a workflow candidate needs --verify (the command that proves it works)"
        if a.stage == "drafted" and not (a.target.startswith("Skills/_staging/") or a.target.startswith("Skills/")):
            return "drafted needs --target Skills/_staging/<slug> (new) or Skills/<existing> (improve)"
        if a.stage == "honed":
            drafts = [r for r in hist if r["stage"] == "drafted"]
            if not drafts:
                return "honed needs a prior drafted entry for %s" % a.slug
            if all(r["session"] == a.session for r in drafts):
                return "honed must come from a different session than the draft (the second session hones)"
        if a.stage == "promoted":
            if "honed" not in stages:
                return "promoted needs a prior honed entry for %s" % a.slug
            if a.by != "owner":
                return "promotion is the owner's call: pass --by owner only on their word"
    if a.kind == "failure" and a.stage == "installed" and a.by != "owner":
        return "installing a hook or check is a standing change: --by owner only on their word"
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": a.kind, "slug": a.slug, "stage": a.stage,
           "session": a.session, "target": a.target, "verify": a.verify, "evidence": a.evidence,
           "by": a.by, "note": a.note}
    os.makedirs(os.path.dirname(os.path.abspath(LEDGER)), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return None


def latest():
    last = {}
    for r in rows():
        last[r["slug"]] = r
    return last


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capability-harvest ledger (session-wrap Step 6.7).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("add")
    ad.add_argument("--kind", choices=sorted(STAGES), required=True)
    ad.add_argument("--slug", required=True)
    ad.add_argument("--stage", required=True)
    ad.add_argument("--session", required=True)
    ad.add_argument("--target", default="")
    ad.add_argument("--verify", default="")
    ad.add_argument("--evidence", default="")
    ad.add_argument("--by", default="claude")
    ad.add_argument("--note", default="")
    ls = sub.add_parser("list")
    ls.add_argument("--open", action="store_true", help="only candidates not yet promoted/installed")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        err = add(a)
        if err:
            print("REFUSED: " + err)
            return 1
        print("recorded %s %s -> %s" % (a.kind, a.slug, a.stage))
        return 0
    for slug, r in sorted(latest().items()):
        if a.open and r["stage"] in ("promoted", "installed"):
            continue
        nxt = {"drafted": "next session that uses it hones it", "honed": "awaiting the owner: promote?",
               "proposed": "awaiting the owner: install?"}.get(r["stage"], "")
        print("%-9s %-28s %-9s %s  %s" % (r["kind"], slug, r["stage"], r["target"], nxt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
