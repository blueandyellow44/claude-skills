#!/usr/bin/env python3
"""check_railway.py - Railway adapter.

  check_railway.py REPO

Railway keeps variables and networking in the dashboard, so most of what
matters is under cannot_see with the count-only command to read it.

  railway.env-dump  code that logs or returns the whole environment
                    (console.log(process.env), JSON.stringify(process.env),
                    print(os.environ), c.json(env)) FAILs high: every variable
                    lands in Railway's logs or a response.
  railway.config    railway.json/railway.toml parses; a start command that
                    runs a dev server (npm run dev, --reload, nodemon) FAILs low.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

DUMP = re.compile(r"""(?:console\.(?:log|info|debug|error)|JSON\.stringify|print|logger\.\w+|c\.json|res\.json|Response\.json)\s*\(\s*(?:process\.env|os\.environ|c\.env|env|Deno\.env\.toObject\(\))\s*[,)]""")
DEV = re.compile(r"npm run dev|next dev|vite(?:\s|$)|nodemon|--reload|uvicorn[^\n]*--reload|flask run")


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    dumps = ["%s:%d" % (r, ln) for r, ln, _ in walk.find(repo, DUMP, tests=False)]
    if dumps:
        res.append(result("railway.env-dump", "The environment is never logged or returned whole", "FAIL", ledger.join_hits(dumps, 6, ", "), severity="high",
                          fix="log or return only the names you need (Object.keys(process.env) at most); rotate anything already in the logs"))
    else:
        res.append(result("railway.env-dump", "The environment is never logged or returned whole", "PASS", "production source: no whole-environment log or response"))
    for f in ("railway.json", "railway.toml"):
        t = walk.read(os.path.join(repo, f))
        if not t:
            continue
        start = ""
        if f.endswith(".json"):
            try:
                d = json.loads(t)
                start = (d.get("deploy") or {}).get("startCommand", "") or ""
            except ValueError:
                res.append(result("railway.config", "Railway config runs a production server", "UNKNOWN", f, reason="unparseable JSON"))
                continue
        else:
            m = re.search(r"""startCommand\s*=\s*["']([^"']+)""", t)
            start = m.group(1) if m else ""
        if start and DEV.search(start):
            res.append(result("railway.config", "Railway config runs a production server", "FAIL", "%s startCommand runs a dev server (%s)" % (f, DEV.search(start).group(0)), severity="low",
                              fix="start the built production server (npm start / node dist/...), not a dev server"))
        else:
            res.append(result("railway.config", "Railway config runs a production server", "PASS", "%s startCommand: no dev server%s" % (f, "" if start else " (builder default)")))
        break
    return ledger.emit(res, cannot_see=[
        "Railway variables: read count-only, `railway variables --kv | grep -c .` and names with `railway variables --kv | cut -d= -f1`; never plain `railway variables`",
        "Public networking (generated domain, TCP proxy) on or off: service Settings, Networking",
    ])


if __name__ == "__main__":
    sys.exit(main())
