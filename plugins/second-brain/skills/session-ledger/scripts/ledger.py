#!/usr/bin/env python3
"""ledger.py - the session ledger: what this session was asked, what it must
satisfy, what it decided and why, and what done means.

Lives at ~/.claude/session-state/<session_id>.ledger.json. Hooks of your own can
read it (to re-deliver it after compaction, or to list its open items before a
commit, deploy or PR); none ship with this plugin.

Usage (session id: see the session-ledger skill's Inputs):
  ledger.py --session SID request "build the session manager, all phases"
  ledger.py --session SID req "drift checks stay proportionate"        # requirement
  ledger.py --session SID done-when "every suite passes and a live session shows it"
  ledger.py --session SID decide "gate advisory" --why "3 of 3 real blocks were wrong"
  ledger.py --session SID check req 2          # mark requirement 2 met (1-based)
  ledger.py --session SID check done 1
  ledger.py --session SID drop req 3 --why "owner cut it"   # scope change, kept as history
  ledger.py --session SID show [--open]
Env: SESSION_MANIFEST_DIR overrides the directory (tests).
"""
import argparse
import json
import os
import sys
import time

DIR = os.environ.get("SESSION_MANIFEST_DIR") or os.path.expanduser("~/.claude/session-state")
KEYS = {"req": "requirements", "done": "done_when"}


def path(sid):
    return os.path.join(DIR, "%s.ledger.json" % sid)


def load(sid):
    try:
        with open(path(sid), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"request": "", "requirements": [], "decisions": [], "done_when": [], "dropped": []}


def save(sid, led):
    os.makedirs(DIR, exist_ok=True)
    led["updated"] = time.time()
    tmp = "%s.%d.tmp" % (path(sid), os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(led, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path(sid))


def show(led, only_open=False):
    out = []
    if led.get("request"):
        out.append("REQUEST: " + led["request"])
    for key, label in (("requirements", "REQ"), ("done_when", "DONE WHEN")):
        for i, it in enumerate(led.get(key) or [], 1):
            if only_open and it.get("done"):
                continue
            out.append("%s %d [%s] %s" % (label, i, "x" if it.get("done") else " ", it["text"]))
    if not only_open:
        for it in led.get("decisions") or []:
            out.append("DECISION: %s%s" % (it["text"], " (why: %s)" % it["why"] if it.get("why") else ""))
        for it in led.get("dropped") or []:
            out.append("DROPPED: %s (why: %s)" % (it["text"], it.get("why") or "-"))
    return "\n".join(out) or "(empty ledger)"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Session ledger: request, requirements, decisions, done-when.")
    ap.add_argument("--session", required=True)
    ap.add_argument("op", choices=["request", "req", "done-when", "decide", "check", "drop", "show"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--why", default="")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args(argv)
    if not a.session.strip() or "/" in a.session:
        sys.exit("--session must be the session id")
    led = load(a.session)
    text = " ".join(a.args).strip()
    if a.op == "show":
        print(show(led, a.open))
        return 0
    if a.op == "request":
        if not text:
            sys.exit("request needs text")
        led["request"] = text
    elif a.op in ("req", "done-when"):
        if not text:
            sys.exit("%s needs text" % a.op)
        led[KEYS["req" if a.op == "req" else "done"]].append({"text": text, "done": False, "added": time.time()})
    elif a.op == "decide":
        if not text:
            sys.exit("decide needs text")
        led["decisions"].append({"text": text, "why": a.why, "at": time.time()})
    elif a.op in ("check", "drop"):
        if len(a.args) != 2 or a.args[0] not in KEYS or not a.args[1].isdigit():
            sys.exit("%s needs: req|done <number>" % a.op)
        items = led[KEYS[a.args[0]]]
        i = int(a.args[1]) - 1
        if not 0 <= i < len(items):
            sys.exit("no %s %s (have %d)" % (a.args[0], a.args[1], len(items)))
        if a.op == "check":
            items[i]["done"] = True
        else:
            led.setdefault("dropped", []).append({"text": items.pop(i)["text"], "why": a.why})
    save(a.session, led)
    print(show(led, only_open=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
