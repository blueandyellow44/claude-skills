#!/usr/bin/env python3
"""check_deps.py - production dependency advisories, with reachability triage.

  check_deps.py REPO [--audit-json FILE]   (--audit-json: parse a saved `npm audit --json`, for tests)

Per package folder with a lockfile (root plus workspaces, never node_modules):
  - deps.lockfile.<dir>: a package.json with no lockfile FAILs (each install
    resolves different versions).
  - deps.audit.<dir>.<package>: one result per high or critical production
    advisory. FAIL unless security/advisory-triage.json records it as not
    reachable with a reason and a review date, which makes it PASS with that
    reasoning shown. Reachable or untriaged stays FAIL.
  - deps.audit.<dir>.moderate: moderate and low advisories, one result.
A major-version fix is named as such; nothing is ever installed or bumped.
npm missing, offline, or an unparseable audit: UNKNOWN with the reason.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

LOCKS = {"package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lockb": "bun", "bun.lock": "bun"}


def triage(repo):
    p = os.path.join(repo, "security", "advisory-triage.json")
    if not os.path.exists(p):
        return {}
    try:
        data = json.load(open(p))
    except ValueError:
        return {}
    # Keyed by advisory (GHSA id, URL or npm source number), never by package alone: a new advisory
    # in an already-triaged package is untriaged (Phase 5 audit #13).
    out = {}
    for a in data.get("advisories", []):
        if a.get("package") and a.get("advisory") and a.get("reason") and a.get("reviewed") and "reachable" in a:
            out.setdefault(a["package"], {})[str(a["advisory"])] = a
    return out


def advisories(v):
    """One alias set per advisory npm attaches to a package: {GHSA id, its URL, npm source number}.
    pnpm's folded entries carry a single advisory_id."""
    out = []
    for via in v.get("via") or []:
        if isinstance(via, dict):
            al = set()
            if via.get("url"):
                al |= {via["url"], via["url"].rstrip("/").rsplit("/", 1)[-1]}
            if via.get("source") is not None:
                al.add(str(via["source"]))
            if al:
                out.append(al)
    if v.get("advisory_id"):
        out.append({str(v["advisory_id"])})
    return out


def triage_state(tri, pkg, v):
    """('unreachable', entries) when every advisory is triaged unreachable; ('reachable', entries) when
    any triaged one is reachable; ('untriaged', missing ids) otherwise, including no advisory id at all."""
    entries = tri.get(pkg, {})
    advs = advisories(v)
    if not advs:
        return "untriaged", ["(no advisory id in the report)"]
    hits, missing = [], []
    for al in advs:
        e = next((entries[a] for a in al if a in entries), None)
        if e is None:
            short = sorted((x for x in al if not x.startswith("http")), key=lambda x: (not x.startswith("GHSA"), x)) or sorted(al)
            missing.append(short[0])
        else:
            hits.append(e)
    if missing:
        return "untriaged", missing
    if any(h.get("reachable") is not False for h in hits):
        return "reachable", hits
    return "unreachable", hits


def package_dirs(repo):
    dirs = []
    for p in walk.files(repo, exts=("package.json",), tests=False):
        d = os.path.dirname(p)
        if d not in dirs:
            dirs.append(d)
    return dirs[:12]


def audit(folder, tool, saved):
    if saved:
        return _validated(json.load(open(saved)), "saved audit")
    if tool != "npm":
        if not shutil.which(tool):
            return None, "%s lockfile but %s is not installed" % (tool, tool)
        if tool == "bun":
            return None, "bun has no audit command"
    if not shutil.which("npm"):
        return None, "npm not installed"
    cmd = ["npm", "audit", "--omit=dev", "--json"] if tool == "npm" else [tool, "audit", "--prod", "--json"]
    try:
        r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None, "%s audit timed out" % tool
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return None, "%s audit gave no JSON (offline?): %s" % (tool, (r.stderr.strip().splitlines() or [""])[-1][:160])
    return _validated(data, "%s audit" % tool)


SEV_RANK = {"info": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}


def _from_advisories(data):
    """pnpm (and npm 6) report advisories keyed by id; fold them into npm 7's per-package map,
    keeping every advisory id and the highest severity."""
    out = {}
    for key, adv in (data.get("advisories") or {}).items():
        name, sev = adv.get("module_name"), adv.get("severity", "low")
        if not name:
            continue
        entry = out.setdefault(name, {"severity": sev, "fixAvailable": False, "via": []})
        if SEV_RANK.get(sev, 0) > SEV_RANK.get(entry["severity"], 0):
            entry["severity"] = sev
        patched = adv.get("patched_versions") or ""
        entry["fixAvailable"] = entry["fixAvailable"] or (bool(patched) and patched != "<0.0.0")
        entry["via"].append({"source": adv.get("id", key), "url": adv.get("url") or ""})
    return out


def _validated(data, label):
    """An audit report without a vulnerabilities map measured nothing: never read it as clean."""
    if isinstance(data, dict) and "vulnerabilities" not in data and isinstance(data.get("advisories"), dict):
        data = dict(data, vulnerabilities=_from_advisories(data))
    if not isinstance(data, dict) or not isinstance(data.get("vulnerabilities"), dict):
        err = data.get("error") if isinstance(data, dict) else None
        detail = str(err.get("summary", err) if isinstance(err, dict) else err or "no vulnerabilities map in the report")
        return None, "%s did not measure anything: %s" % (label, detail[:160])
    return data, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--audit-json")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    tri = triage(repo)
    res = []
    for d in package_dirs(repo):
        rel = walk.rel(repo, d) if d != repo else "."
        tag = "root" if rel == "." else rel.replace("/", "_")
        locks = [f for f in LOCKS if os.path.exists(os.path.join(d, f))]
        if not locks:
            res.append(result("deps.lockfile.%s" % tag, "Lockfile present in %s" % rel, "FAIL", "%s/package.json with no lockfile" % rel,
                              severity="medium", fix="commit a lockfile and install with npm ci so every build resolves the same versions"))
            continue
        res.append(result("deps.lockfile.%s" % tag, "Lockfile present in %s" % rel, "PASS", "%s/%s" % (rel, locks[0])))
        data, why = audit(d, LOCKS[locks[0]], a.audit_json)
        if data is None:
            res.append(result("deps.audit.%s" % tag, "Production advisories in %s" % rel, "UNKNOWN", "%s/%s" % (rel, locks[0]), reason=why))
            continue
        vulns = data.get("vulnerabilities") or {}
        minor = []
        for pkg, v in sorted(vulns.items()):
            sev = v.get("severity", "low")
            fix = v.get("fixAvailable")
            major = isinstance(fix, dict) and fix.get("isSemVerMajor")
            fixtxt = ("fix is a MAJOR bump to %s %s: a separate decision, never auto-applied" % (fix.get("name"), fix.get("version"))) if major \
                else ("compatible fix available: npm audit fix (review the lockfile diff)" if fix else "no fix published: triage reachability")
            if sev in ("high", "critical"):
                cid = "deps.audit.%s.%s" % (tag, pkg)
                state, info = triage_state(tri, pkg, v)
                if state == "unreachable":
                    res.append(result(cid, "%s advisories in %s are unreachable" % (pkg, rel), "PASS",
                                      "security/advisory-triage.json (reviewed %s)" % info[0]["reviewed"],
                                      detail="triaged per advisory: " + "; ".join(e["reason"] for e in info)))
                else:
                    res.append(result(cid, "No %s advisory in production dependency %s" % (sev, pkg), "FAIL", "%s/%s: %s audit, production deps" % (rel, locks[0], LOCKS[locks[0]]),
                                      severity="critical" if sev == "critical" else "high", fix=fixtxt,
                                      detail=("triaged REACHABLE: " + info[0]["reason"]) if state == "reachable"
                                      else "untriaged advisory %s: record reachability per advisory id in security/advisory-triage.json" % ledger.join_hits(info, 3, ", ")))
            else:
                minor.append("%s (%s%s)" % (pkg, sev, ", major fix" if major else ""))
        untriaged_minor = [m for m in minor if triage_state(tri, m.split(" ")[0], vulns.get(m.split(" ")[0], {}))[0] != "unreachable"]
        if untriaged_minor:
            res.append(result("deps.audit.%s.moderate" % tag, "No untriaged moderate/low advisories in %s" % rel, "FAIL", "%s: %s" % (rel, ledger.join_hits(untriaged_minor, 8, ", ")),
                              severity="low", fix="triage each in security/advisory-triage.json (reachable or not, with the reason); take compatible fixes"))
        else:
            res.append(result("deps.audit.%s.moderate" % tag, "No untriaged moderate/low advisories in %s" % rel, "PASS",
                              "%s: npm audit --omit=dev, %d moderate/low, all triaged unreachable" % (rel, len(minor)) if minor else "%s: npm audit --omit=dev found none" % rel))
    if os.path.exists(os.path.join(repo, "requirements.txt")):
        if shutil.which("pip-audit"):
            r = subprocess.run(["pip-audit", "-r", "requirements.txt"], cwd=repo, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                res.append(result("deps.python", "No Python advisories", "PASS", "pip-audit -r requirements.txt"))
            else:
                res.append(result("deps.python", "No Python advisories", "FAIL", "pip-audit -r requirements.txt", severity="medium",
                                  fix="upgrade or triage each pip-audit finding"))
        else:
            res.append(result("deps.python", "No Python advisories", "UNKNOWN", "requirements.txt", reason="pip-audit not installed (uv tool install pip-audit)"))
    elif os.path.exists(os.path.join(repo, "pyproject.toml")):
        res.append(result("deps.python", "No Python advisories", "UNKNOWN", "pyproject.toml",
                          reason="pyproject without requirements.txt: run pip-audit inside the project's environment"))
    if not res:
        res.append(result("deps.none", "Dependency audit", "UNKNOWN", repo, reason="no package.json or Python manifest found"))
    return ledger.emit(res)


if __name__ == "__main__":
    sys.exit(main())
