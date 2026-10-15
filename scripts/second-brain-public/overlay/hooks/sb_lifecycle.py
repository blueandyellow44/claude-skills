#!/usr/bin/env python3
"""Session lifecycle: notice an unwrapped session, count compactions, keep a ledger.

  Stop        once per session: if it wrote files and has not written a daily entry,
              tell the person in one line that a wrap would record it. Never blocks.
  PreCompact  record that a compaction happened (SessionStart re-delivers after it).
  SessionEnd  append one line to sb-sessions.jsonl: did it write, did it wrap. The next
              session's startup counts the recent unwrapped ones.

A session counts as wrapped when it edited a file under <vault>/Daily/, or ran a shell
append into Daily/ (both recorded by sb_drift.py).

Usage: sb_lifecycle.py stop | precompact | end
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sb_common as c  # noqa: E402


def status(sid):
    vault, _ = c.vault()
    daily_dir = os.path.join(vault, "Daily") + os.sep if vault else None
    wrote, wrapped, reminded = set(), False, False
    for r in c.records(sid):
        kind = r.get("rec")
        if kind == "touched" and r.get("action") == "edit":
            path = r.get("path", "")
            if daily_dir and path.startswith(daily_dir):
                wrapped = True
            else:
                wrote.add(path)
        elif kind == "wrap":
            wrapped = True
        elif kind == "wrap_reminded":
            reminded = True
    return wrote, wrapped, reminded


def on_stop(data):
    sid = data.get("session_id", "")
    if not sid or data.get("stop_hook_active"):
        return
    wrote, wrapped, reminded = status(sid)
    if not wrote or wrapped or reminded:
        return
    if not c.claim(sid, "Stop", "wrap-reminder"):
        return
    c.record(sid, {"rec": "wrap_reminded"})
    c.emit("Stop", message="%s: this session edited %d file(s) and has no daily entry yet. "
                           "Say \"wrap session\" to record what it did, decided and left open." % (c.PREFIX, len(wrote)))


def on_precompact(data):
    sid = data.get("session_id", "")
    if sid and c.claim(sid, "PreCompact", c.event_key(data, data.get("trigger", ""))):
        c.record(sid, {"rec": "compaction", "trigger": data.get("trigger", "")})


def on_end(data):
    sid = data.get("session_id", "")
    if not sid or not c.claim(sid, "SessionEnd", c.event_key(data, "end")):
        return
    wrote, wrapped, _ = status(sid)
    try:
        os.makedirs(c.STATE, exist_ok=True)
        line = json.dumps({"sid": sid, "cwd": data.get("cwd", ""), "wrote": len(wrote),
                           "wrapped": wrapped, "reason": data.get("reason", ""), "ended": time.time()})
        with open(os.path.join(c.STATE, "sb-sessions.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def main():
    if c.hooks_off():
        return
    data = c.read_input()
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    {"stop": on_stop, "precompact": on_precompact, "end": on_end}.get(mode, lambda d: None)(data)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write(json.dumps({"systemMessage": "%s: lifecycle hook failed (%s: %s)" % (
            c.PREFIX, type(exc).__name__, exc)}))
