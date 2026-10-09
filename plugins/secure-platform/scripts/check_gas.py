#!/usr/bin/env python3
"""check_gas.py - Google Apps Script adapter.

  check_gas.py REPO

  gas.webapp-access  appsscript.json webapp.access ANYONE_ANONYMOUS FAILs high
                     (critical when executeAs is USER_DEPLOYING: strangers run
                     code as the deployer); ANYONE (any Google account) FAILs low;
                     DOMAIN, MYSELF and no web app PASS.
  gas.scopes         explicit oauthScopes with a full-access scope where a
                     narrow one exists (drive, gmail full, mail.google.com,
                     spreadsheets) FAIL low; no oauthScopes: UNKNOWN (scopes
                     are auto-detected and not reviewable from the repo).
  gas.keys-in-code   a key-shaped value or an apiKey literal in .gs/.html/.js
                     FAILs high: use PropertiesService.
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

BROAD = {
    "https://www.googleapis.com/auth/drive": "drive.file or drive.readonly",
    "https://mail.google.com/": "gmail.send or gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify": "gmail.send or gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets": "spreadsheets.currentonly",
    "https://www.googleapis.com/auth/documents": "documents.currentonly",
}
KEY_LITERAL = re.compile(r"""\w*(?:key|pass|password|passwd|secret|token|credential)\w*['"]?\s*[:=]\s*['"]([^'"\s]{16,})['"]""", re.I)


def _entropy(s):
    import math
    from collections import Counter
    c = Counter(s)
    return -sum(v / len(s) * math.log2(v / len(s)) for v in c.values())


def main():
    repo = os.path.abspath(sys.argv[1])
    manifests = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git") and not d.startswith(".")]
        manifests += [os.path.join(root, n) for n in names if n == "appsscript.json"]
    res = []
    for mp in manifests[:6]:
        rel = walk.rel(repo, mp)
        tag = "" if len(manifests) == 1 else "." + re.sub(r"[^A-Za-z0-9]+", "_", os.path.dirname(rel) or "root")
        try:
            m = json.load(open(mp))
        except ValueError:
            res.append(result("gas.manifest" + tag, "appsscript.json readable", "UNKNOWN", rel, reason="unparseable JSON"))
            continue
        wa = m.get("webapp")
        if not wa:
            res.append(result("gas.webapp-access" + tag, "Web app access is limited", "PASS", "%s: no webapp section (not deployed as a web app)" % rel))
        else:
            acc, ex = wa.get("access", ""), wa.get("executeAs", "")
            if acc == "ANYONE_ANONYMOUS":
                sev = "critical" if ex == "USER_DEPLOYING" else "high"
                res.append(result("gas.webapp-access" + tag, "Web app access is limited", "FAIL", "%s: access %s, executeAs %s" % (rel, acc, ex), severity=sev,
                                  fix="DOMAIN for one school's staff, or ANYONE (signed-in Google users) with an allow-list; never anonymous while executing as the deployer"))
            elif acc == "ANYONE":
                res.append(result("gas.webapp-access" + tag, "Web app access is limited", "FAIL", "%s: access ANYONE (any Google account)" % rel, severity="low",
                                  fix="DOMAIN if the audience is one organisation; if it must be ANYONE, check Session.getActiveUser() against an allow-list"))
            else:
                res.append(result("gas.webapp-access" + tag, "Web app access is limited", "PASS", "%s: access %s" % (rel, acc or "default (MYSELF)")))
        scopes = m.get("oauthScopes")
        if scopes is None:
            res.append(result("gas.scopes" + tag, "OAuth scopes are narrow", "UNKNOWN", rel, reason="no oauthScopes: auto-detected at authorization, not reviewable here; list them explicitly"))
        else:
            broad = ["%s (use %s)" % (s.rsplit("/", 1)[-1] or s, BROAD[s]) for s in scopes if s in BROAD]
            if broad:
                res.append(result("gas.scopes" + tag, "OAuth scopes are narrow", "FAIL", "%s: %s" % (rel, "; ".join(broad)), severity="low",
                                  fix="replace each full-access scope with the narrow one the code needs"))
            else:
                res.append(result("gas.scopes" + tag, "OAuth scopes are narrow", "PASS", "%s: %d explicit scope(s), none full-access" % (rel, len(scopes))))
    if manifests:
        hits = []
        for p in walk.files(repo, exts=(".gs", ".html", ".js"), tests=False):
            t = walk.read(p)
            for rx in ledger.SECRET_SHAPES:
                for m in rx.finditer(t):
                    hits.append("%s:%d" % (walk.rel(repo, p), walk.line_of(t, m.start())))
            for m in KEY_LITERAL.finditer(t):
                v = m.group(1)
                if _entropy(v) >= 3.5 and not re.match(r"^(?:https?://|/|\.|[A-Z_]+$)", v):
                    hits.append("%s:%d" % (walk.rel(repo, p), walk.line_of(t, m.start())))
        if hits:
            res.append(result("gas.keys-in-code", "No keys in Apps Script code", "FAIL", ledger.join_hits(sorted(set(hits)), 6, ", "), severity="high",
                              fix="store it with PropertiesService.getScriptProperties(), remove it from the file, rotate it"))
        else:
            res.append(result("gas.keys-in-code", "No keys in Apps Script code", "PASS", "no key-shaped value or key literal in .gs/.html/.js"))
    return ledger.emit(res, cannot_see=["The deployed version's access setting can differ from appsscript.json until a new deployment is made (clasp deploy)",
                                        "Script Properties contents: Apps Script editor, Project Settings (names only)"])


if __name__ == "__main__":
    sys.exit(main())
