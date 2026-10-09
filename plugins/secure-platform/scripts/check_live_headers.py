#!/usr/bin/env python3
"""check_live_headers.py - ledger form of probe_headers.sh for live URLs.

  check_live_headers.py REPO --url https://host/ [--url ...]

Read-only: one HEAD per URL and one plain-http GET per host, no body, cookie
or credential (probe_headers.sh). Each header becomes live.<host>.<name>;
a URL that does not answer is UNKNOWN for that host, never a pass.
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
from ledger import result  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = [("framing control", "framing", "medium"), ("HSTS", "hsts", "low"), ("nosniff", "nosniff", "low"),
         ("referrer-policy", "referrer", "low"), ("http -> https redirect", "https-redirect", "medium"), ("http redirects to https", "https-redirect", "medium")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--url", action="append", required=True)
    a = ap.parse_args()
    res = []
    for url in a.url:
        host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
        r = subprocess.run(["bash", os.path.join(HERE, "probe_headers.sh"), url], capture_output=True, text=True, timeout=60)
        if "NO ANSWER" in r.stdout:
            res.append(result("live.%s" % host, "%s answers" % host, "UNKNOWN", url, reason="no answer to a HEAD request"))
            continue
        seen = set()
        for line in r.stdout.splitlines():
            m = re.match(r"^\s+(ok|MISSING)\s+(.*)$", line)
            if not m:
                continue
            for label, key, sev in NAMES:
                if m.group(2).startswith(label) and key not in seen:
                    seen.add(key)
                    cid = "live.%s.%s" % (host, key)
                    if m.group(1) == "ok":
                        res.append(result(cid, "%s on %s" % (key, host), "PASS", "HEAD %s: %s" % (url, m.group(2)[:120])))
                    else:
                        res.append(result(cid, "%s on %s" % (key, host), "FAIL", "HEAD %s: %s" % (url, m.group(2)[:120]), severity=sev,
                                          fix="set it in _headers (/* block) or the app's response middleware, then re-probe"))
        if not seen:
            res.append(result("live.%s" % host, "%s probed" % host, "UNKNOWN", url, reason="probe output not understood"))
    return ledger.emit(res)


if __name__ == "__main__":
    sys.exit(main())
