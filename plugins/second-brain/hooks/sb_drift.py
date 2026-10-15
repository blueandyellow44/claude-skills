#!/usr/bin/env python3
"""Drift checks: did anything this session relies on change under it?

  UserPromptSubmit  stat every file the session was given or touched. A file that
                    changed and was not changed by this session is named once; a
                    changed project hub is re-delivered in full slice. Stats only:
                    no file is read unless it changed.
  PostToolUse       Read/Edit/Write/MultiEdit/NotebookEdit: record the file and the
                    state this session left it in, so its own edits are never drift.
                    On the first edit under a hub's workspace, deliver that hub:
                    the edit is the evidence of which project this is.

Usage: sb_drift.py prompt | sb_drift.py tool
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sb_common as c  # noqa: E402

HOOK = "drift"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def last_commit(path):
    try:
        out = subprocess.run(["git", "-C", os.path.dirname(path), "log", "-1", "--format=%h %s", "--", path],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def on_prompt(data):
    sid = data.get("session_id", "")
    if not sid or not c.claim(sid, "UserPromptSubmit", data.get("prompt", "")):
        return
    moved = c.changed(sid)
    if not moved:
        return
    vault, _ = c.vault()
    lines, extra = [], []
    hubs_by_path = {h["path"]: h for h in c.hubs(vault)} if vault else {}
    for path, kind, now_m in moved:
        if now_m is None:
            lines.append("  - %s (%s): deleted or moved since this session loaded it" % (path, kind))
            c.record(sid, {"rec": "seen", "path": path, "mtime": None, "size": None})
            continue
        commit = last_commit(path)
        lines.append("  - %s (%s)%s" % (path, kind, ": last commit " + commit if commit else ""))
        hub = hubs_by_path.get(path)
        if hub:
            text = c.hub_slice(hub, "re-delivered: changed since this session loaded it")
            extra.append(text)
            c.delivered(sid, HOOK, "project", path, text)
        else:
            c.seen(sid, path)
    context = ("DRIFT: these files changed since this session loaded or last touched them, and this "
               "session did not change them (another session, an editor, or a sync). Re-read any of them "
               "before editing it:\n" + "\n".join(lines))
    if extra:
        context += "\n\n" + "\n\n".join(extra)
    c.emit("UserPromptSubmit", context, "%s: %d file(s) changed under this session" % (c.PREFIX, len(lines)))


def on_tool(data):
    sid = data.get("session_id", "")
    tool = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    if tool == "Bash":
        cmd = str(tin.get("command", ""))
        if "Daily/" in cmd and (">>" in cmd or "tee " in cmd) and sid:
            c.record(sid, {"rec": "wrap", "via": "bash"})
        return
    path = tin.get("file_path") or tin.get("notebook_path") or ""
    if not sid or not path:
        return
    if not c.claim(sid, "PostToolUse", data.get("tool_use_id") or "%s:%s" % (tool, path)):
        return
    path = os.path.abspath(os.path.expanduser(path))
    c.touched(sid, path, "edit" if tool in EDIT_TOOLS else "read")
    if tool not in EDIT_TOOLS:
        return
    vault, _ = c.vault()
    if not vault or path.startswith(os.path.realpath(vault) + os.sep) or path.startswith(vault + os.sep):
        return
    hub = c.hub_for_path(vault, os.path.dirname(path))
    if not hub:
        return
    if any(r.get("rec") == "delivered" and r.get("path") == hub["path"] for r in c.records(sid)):
        return
    text = c.hub_slice(hub, "first edit under its workspace: %s" % path)
    c.delivered(sid, HOOK, "project", hub["path"], text)
    c.emit("PostToolUse", text, "%s: delivered project %s (first edit in its workspace)" % (c.PREFIX, hub["name"]))


def main():
    if c.hooks_off():
        return
    data = c.read_input()
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "prompt":
        on_prompt(data)
    elif mode == "tool":
        on_tool(data)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write(json.dumps({"systemMessage": "%s: drift hook failed (%s: %s)" % (
            c.PREFIX, type(exc).__name__, exc)}))
