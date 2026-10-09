"""ledger.py - the one findings format every secure-launch check speaks.

A check result is PASS, FAIL or UNKNOWN. There is no fourth state and no
default: a result with any other status, a PASS without evidence, a FAIL
without a severity or a fix, or an UNKNOWN without a reason is rejected, so a
check cannot report a verdict it did not measure.

UNKNOWN means "not run, or could not run". It is counted on its own line
everywhere and is never folded into PASS or FAIL. `security/accepted.json` can
mark a specific check id as accepted (with a reason and a ruling date); an
accepted result keeps its status and stays in the report, it only stops the
gate from refusing on it.

Check scripts call `emit(results)` and print one JSON object on stdout.
"""
import datetime
import json
import os
import re
import sys

STATUSES = ("PASS", "FAIL", "UNKNOWN")
SEVERITIES = ("critical", "high", "medium", "low", "info")
SUITE_VERSION = "0.2.3"

# Values that look like credentials. Used to refuse writing them anywhere: a
# check must report a location, never a value. Patterns match key SHAPES only.
SECRET_SHAPES = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-(?:proj-)?[0-9A-Za-z_\-]{32,}"),
    re.compile(r"[sr]k_(?:live|test)_[0-9A-Za-z]{16,}"),
    re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),
    re.compile(r"github_pat_[0-9A-Za-z_]{40,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"),
    re.compile(r"eyJ[0-9A-Za-z_\-]{10,}\.eyJ[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"[a-z][a-z0-9+.\-]*://[^/\s:@'\"]+:[^@\s/'\"]{6,}@"),   # URL with a password
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]
_TOKEN = re.compile(r"[A-Za-z0-9+_\-]{32,}")  # no "/": paths are not keys


def _high_entropy(text):
    """A 32+ char run mixing upper, lower and digits with high entropy: a key with no known shape."""
    import math
    from collections import Counter
    for m in _TOKEN.finditer(text or ""):
        s = m.group(0)
        if not (any(c.isupper() for c in s) and any(c.islower() for c in s) and any(c.isdigit() for c in s)):
            continue
        c = Counter(s)
        if -sum(v / len(s) * math.log2(v / len(s)) for v in c.values()) > 4.3:
            return True
    return False


class LedgerError(ValueError):
    pass


def result(id, title, status, evidence, severity=None, fix=None, reason=None, detail=None):
    """Build one check result. Validation happens in validate()."""
    r = {"id": id, "title": title, "status": status, "evidence": evidence}
    if severity:
        r["severity"] = severity
    if fix:
        r["fix"] = fix
    if reason:
        r["reason"] = reason
    if detail:
        r["detail"] = detail
    return r


def git_state(repo):
    """HEAD plus a fingerprint of the working tree, shared by the orchestrator and the gate.
    Python bytecode is left out: running the vendored scripts writes __pycache__ inside a
    committed .secure-launch/, which changed the status between ledger and gate on the first
    real CI run (a coaching app's PR, 2026-10-09)."""
    import hashlib
    import subprocess
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0:
        return None
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True).stdout
    kept = sorted(l for l in st.splitlines() if "__pycache__/" not in l and not l.endswith((".pyc", ".pyo")))
    return {"head": head.stdout.strip(), "status": hashlib.sha1("\n".join(kept).encode()).hexdigest()[:12]}


def join_hits(hits, n=6, sep="; "):
    """Evidence for a list of hits. When truncated it ends with the total and a
    fingerprint of the FULL list, so an acceptance bound to this evidence stops
    matching the moment a new hit appears (Phase 5 audit, second pass)."""
    import hashlib
    hits = [str(h) for h in hits]
    shown = sep.join(hits[:n])
    if len(hits) <= n:
        return shown
    fp = hashlib.sha1("\n".join(sorted(hits)).encode()).hexdigest()[:10]
    return "%s (+%d more; %d total, fingerprint %s)" % (shown, len(hits) - n, len(hits), fp)


def contains_secret_shape(text):
    return any(p.search(text or "") for p in SECRET_SHAPES) or _high_entropy(text)


def validate(r):
    if not isinstance(r, dict):
        raise LedgerError("result is not an object: %r" % (r,))
    for k in ("id", "title", "status", "evidence"):
        if not r.get(k):
            raise LedgerError("%s: missing %s" % (r.get("id", "?"), k))
    st = r["status"]
    if st not in STATUSES:
        raise LedgerError("%s: status %r is not PASS, FAIL or UNKNOWN" % (r["id"], st))
    if st == "FAIL":
        if r.get("severity") not in SEVERITIES:
            raise LedgerError("%s: FAIL needs a severity in %s" % (r["id"], SEVERITIES))
        if not r.get("fix"):
            raise LedgerError("%s: FAIL needs a one-line fix" % r["id"])
    if st == "UNKNOWN" and not r.get("reason"):
        raise LedgerError("%s: UNKNOWN needs the reason it could not run" % r["id"])
    blob = json.dumps(r)
    if contains_secret_shape(blob):
        raise LedgerError("%s: result text contains a credential-shaped value; report the location only" % r["id"])
    return r


def emit(results, out=sys.stdout, cannot_see=None):
    """Validate and print one JSON object for the orchestrator. Exit code: 0
    all PASS, 1 any FAIL, 3 no FAIL but some UNKNOWN (so a caller that only
    reads exit codes still cannot mistake UNKNOWN for PASS)."""
    for r in results:
        validate(r)
    payload = {"checks": results}
    if cannot_see:
        payload["cannot_see"] = list(cannot_see)
    json.dump(payload, out, indent=1)
    out.write("\n")
    statuses = {r["status"] for r in results}
    if "FAIL" in statuses:
        return 1
    if "UNKNOWN" in statuses or not results:
        return 3
    return 0


ACCEPT_DAYS = 90


def load_accepted(repo, today=None):
    """security/accepted.json: {"accepted": [{"id", "reason", "ruled": "YYYY-MM-DD",
    "evidence": <the exact evidence string ruled on>, "expires"?: "YYYY-MM-DD"}]}.
    An acceptance covers ONE result: same id AND same evidence, so a new leak
    under the same id is not covered. It expires (default 90 days after the
    ruling). Expired entries are dropped, never honored."""
    p = os.path.join(repo, "security", "accepted.json")
    if not os.path.exists(p):
        return {}
    try:
        data = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LedgerError("security/accepted.json unreadable: %s" % exc)
    today = today or datetime.date.today()
    out = {}
    for a in data.get("accepted", []):
        if not (a.get("id") and a.get("reason") and a.get("ruled") and a.get("evidence")):
            raise LedgerError("accepted entry needs id, reason, ruled (YYYY-MM-DD) and the evidence it was ruled on: %r" % (a.get("id"),))
        try:
            ruled = datetime.date.fromisoformat(a["ruled"])
            expires = datetime.date.fromisoformat(a["expires"]) if a.get("expires") else ruled + datetime.timedelta(days=ACCEPT_DAYS)
        except ValueError:
            raise LedgerError("accepted %s: ruled/expires must be YYYY-MM-DD" % a["id"])
        if ruled > today:
            raise LedgerError("accepted %s: ruled %s is in the future" % (a["id"], a["ruled"]))
        expires = min(expires, ruled + datetime.timedelta(days=ACCEPT_DAYS))  # never longer than 90 days
        if expires < today:
            continue
        a = dict(a, expires=expires.isoformat())
        out[(a["id"], a["evidence"])] = a
    return out


def acceptance(accepted, r):
    """The acceptance covering this exact result, or None. Critical FAILs are never acceptable."""
    if r["status"] == "FAIL" and r.get("severity") == "critical":
        return None
    return accepted.get((r["id"], r["evidence"]))


def counts(results):
    c = {s: 0 for s in STATUSES}
    for r in results:
        c[r["status"]] += 1
    return c


def build(repo, results, stack, adapters, accepted=None, cannot_see=None):
    accepted = accepted or {}
    for r in results:
        validate(r)
        a = acceptance(accepted, r)
        if a:
            r["accepted"] = {"reason": a["reason"], "ruled": a["ruled"], "expires": a["expires"]}
    return {
        "suite_version": SUITE_VERSION,
        "repo": os.path.realpath(repo),
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "stack": stack,
        "adapters": adapters,
        "counts": counts(results),
        "results": results,
        "cannot_see": sorted(set(cannot_see or [])),
    }


SEV_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


def to_markdown(ledger):
    c = ledger["counts"]
    lines = [
        "# Security findings: %s" % os.path.basename(ledger["repo"]),
        "",
        "Generated %s by secure-launch %s. **%d FAIL, %d UNKNOWN, %d PASS.** UNKNOWN means not run or could not run; it is not a pass."
        % (ledger["generated_at"], ledger["suite_version"], c["FAIL"], c["UNKNOWN"], c["PASS"]),
        "",
        "Stack detected: %s" % (", ".join(ledger["stack"]) or "nothing recognised"),
        "",
    ]
    for status in ("FAIL", "UNKNOWN", "PASS"):
        rows = [r for r in ledger["results"] if r["status"] == status]
        if not rows:
            continue
        rows.sort(key=lambda r: (SEV_ORDER.get(r.get("severity", "info"), 9), r["id"]))
        lines += ["## %s (%d)" % (status, len(rows)), ""]
        for r in rows:
            head = "- **%s** `%s`" % (r["title"], r["id"])
            if status == "FAIL":
                head += " [%s]" % r["severity"]
            if r.get("accepted"):
                head += " (accepted %s: %s)" % (r["accepted"]["ruled"], r["accepted"]["reason"])
            lines.append(head)
            lines.append("  - evidence: %s" % r["evidence"])
            if r.get("reason"):
                lines.append("  - why unknown: %s" % r["reason"])
            if r.get("fix") and status != "PASS":
                lines.append("  - fix: %s" % r["fix"])
            if r.get("detail"):
                lines.append("  - %s" % r["detail"])
        lines.append("")
    if ledger.get("cannot_see"):
        lines += ["## What this run cannot see", "", "Not checks, so not counted. Each needs a human look (dashboard, live data) before calling the repo covered.", ""]
        lines += ["- %s" % s for s in ledger["cannot_see"]] + [""]
    lines += ["## Adapters", ""] + ["- %s: %s" % (k, v) for k, v in sorted(ledger["adapters"].items())]
    return "\n".join(lines) + "\n"
