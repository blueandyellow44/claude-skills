#!/usr/bin/env python3
"""store_secret.py - write one secret into a NAME=VALUE file from stdin, never
echoing it, then confirm by shape.

  pbpaste | store_secret.py FILE NAME

Replaces an existing NAME= line or appends one, keeping every other line
byte-for-byte. Strips one trailing newline and surrounding whitespace from the
input (the clipboard often carries them) and refuses a value that itself starts
with "NAME=" (the 2026-10-06 ElevenLabs failure). Prints only: the file, the
name, the action, and the value's length.
"""
import os
import re
import sys


def main():
    if len(sys.argv) != 3:
        print("usage: pbpaste | store_secret.py FILE NAME", file=sys.stderr)
        return 2
    path, name = sys.argv[1], sys.argv[2]
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        print("refused: %r is not a variable name" % name, file=sys.stderr)
        return 2
    if sys.stdin.isatty():
        print("refused: pipe the value in (pbpaste | ...); typing it would put it on screen", file=sys.stderr)
        return 2
    val = sys.stdin.read().strip()
    if not val:
        print("refused: empty value on stdin", file=sys.stderr)
        return 2
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", val):
        print("refused: the value starts with NAME= (copy the value alone)", file=sys.stderr)
        return 2
    if "\n" in val:
        print("refused: the value spans several lines", file=sys.stderr)
        return 2
    lines = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    rx = re.compile(r"^\s*(?:export\s+)?%s\s*=" % re.escape(name))
    hits = [i for i, l in enumerate(lines) if rx.match(l)]
    if len(hits) > 1:
        print("refused: %s is defined %d times in %s; fix by hand first" % (name, len(hits), path), file=sys.stderr)
        return 2
    new = "%s=%s" % (name, val)
    if hits:
        lines[hits[0]] = new
        action = "replaced"
    else:
        if lines and lines[-1] == "":
            lines.insert(len(lines) - 1, new)
        else:
            lines.append(new)
        action = "added"
    tmp = path + ".tmp-store"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) if lines[-1:] == [""] else "\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    print("%s %s in %s (%d characters)" % (action, name, path, len(val)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
