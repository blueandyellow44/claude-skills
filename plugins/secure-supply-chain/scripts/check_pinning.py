#!/usr/bin/env python3
"""check_pinning.py - CI and build tooling that can change under you.

  check_pinning.py REPO

  - actions.pinned: every `uses: owner/repo@ref` in .github/workflows pinned to
    a full 40-character commit SHA. Third-party actions on a tag FAIL medium;
    GitHub's own (actions/*, github/*) FAIL low.
  - actions.secret-scope: a `${{ secrets.X }}` in a workflow-level or job-level
    `env:` block FAILs medium: every step of the job, including third-party
    actions, can read it. The scoped pattern gives each secret only to its step.
  - tooling.wrangler: a deploy that runs `npx wrangler` with no wrangler in
    package.json, `wrangler@latest`, a `latest`/`*` range, or the wrangler
    action without `wranglerVersion` FAILs low (a new wrangler can change a
    deploy with no commit). Only emitted when wrangler is used.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^'\"\s#]+)", re.M)
SHA = re.compile(r"@[0-9a-f]{40}$")


def workflows(repo):
    """Workflows plus local composite actions (.github/actions/*/action.yml), which run third-party actions too."""
    out = []
    d = os.path.join(repo, ".github", "workflows")
    if os.path.isdir(d):
        out += [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.endswith((".yml", ".yaml"))]
    ad = os.path.join(repo, ".github", "actions")
    for root, _, names in os.walk(ad):
        out += [os.path.join(root, n) for n in sorted(names) if n in ("action.yml", "action.yaml")]
    return out


def env_level(lines, i):
    """'workflow', 'job' or 'step' for an `env:` line at index i."""
    ind = len(lines[i]) - len(lines[i].lstrip())
    if ind == 0:
        return "workflow"
    j = i - 1
    while j >= 0:
        l = lines[j]
        if l.strip() and not l.lstrip().startswith("#"):
            jind = len(l) - len(l.lstrip())
            if jind < ind:
                if l.lstrip().startswith("- "):
                    return "step"
                # a mapping key: is it a job id (a direct child of `jobs:`)?
                k = j - 1
                while k >= 0:
                    kl = lines[k]
                    if kl.strip() and not kl.lstrip().startswith("#") and len(kl) - len(kl.lstrip()) < jind:
                        return "job" if kl.strip() == "jobs:" else "step"
                    k -= 1
                return "job"
        j -= 1
    return "workflow"


def block(lines, i):
    ind = len(lines[i]) - len(lines[i].lstrip())
    out = []
    for l in lines[i + 1:]:
        if l.strip() and len(l) - len(l.lstrip()) <= ind:
            break
        out.append(l)
    return "\n".join(out)


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    wfs = workflows(repo)
    unpinned, broad = [], []
    for p in wfs:
        t = walk.read(p)
        r = walk.rel(repo, p)
        for m in USES.finditer(t):
            u = m.group(1)
            if u.startswith(("./", "docker://")) or "@" not in u:
                continue
            if not SHA.search(u):
                first = u.split("/")[0] in ("actions", "github")
                unpinned.append((first, "%s:%d %s" % (r, walk.line_of(t, m.start()), u)))
        lines = t.split("\n")
        for i, l in enumerate(lines):
            inline = re.match(r"^\s*env:\s*\{.*\$\{\{\s*secrets\.", l)
            if inline or (re.match(r"^\s*env:\s*$", l) and "${{ secrets." in block(lines, i)):
                lvl = env_level(lines, i)
                if lvl != "step":
                    broad.append("%s:%d (%s-level env)" % (r, i + 1, lvl))
    if not wfs:
        res.append(result("actions.pinned", "GitHub Actions pinned to commit SHAs", "PASS", "no .github/workflows in the repo"))
    elif unpinned:
        third = [u for f, u in unpinned if not f]
        res.append(result("actions.pinned", "GitHub Actions pinned to commit SHAs", "FAIL", ledger.join_hits([u for _, u in unpinned], 8, "; "),
                          severity="medium" if third else "low",
                          fix="pin each to its full commit SHA with the tag in a comment (uses: owner/action@<sha> # v4.2.0)",
                          detail="%d unpinned (%d third-party)" % (len(unpinned), len(third))))
    else:
        res.append(result("actions.pinned", "GitHub Actions pinned to commit SHAs", "PASS", "%d workflow(s), every uses: on a 40-char SHA" % len(wfs)))
    if wfs:
        if broad:
            res.append(result("actions.secret-scope", "Secrets scoped to the step that uses them", "FAIL", ledger.join_hits(broad, 8, "; "), severity="medium",
                              fix="move each secrets.X from the workflow/job env: into the env: of the one step that needs it"))
        else:
            res.append(result("actions.secret-scope", "Secrets scoped to the step that uses them", "PASS", "%d workflow(s): no secrets in workflow- or job-level env" % len(wfs)))

    pkgs = {}
    for p in walk.all_package_jsons(repo):
        try:
            import json
            pkgs[walk.rel(repo, p)] = walk.deps(json.load(open(p)))
        except (OSError, ValueError):
            pass
    pinned_in_pkg = {k: v["wrangler"] for k, v in pkgs.items() if "wrangler" in v}
    problems, uses_wrangler = [], bool(pinned_in_pkg)
    locked = {}
    for k, v in pinned_in_pkg.items():
        lock = os.path.join(repo, os.path.dirname(k), "package-lock.json")
        try:
            import json as _j
            lv = ((_j.load(open(lock)).get("packages") or {}).get("node_modules/wrangler") or {}).get("version")
        except (OSError, ValueError):
            lv = None
        if not lv:  # pnpm and yarn lockfiles name the resolved version too
            base = os.path.join(repo, os.path.dirname(k))
            for lf, rx in (("pnpm-lock.yaml", r"(?m)^\s+wrangler:\s*\n\s+specifier:[^\n]*\n\s+version:\s*'?(\d+\.\d+\.\d+)|/wrangler@(\d+\.\d+\.\d+)|^\s{2}wrangler@(\d+\.\d+\.\d+)"),
                           ("yarn.lock", r'(?m)^"?wrangler@[^\n]*:\n\s+version "?(\d+\.\d+\.\d+)')):
                m = re.search(rx, walk.read(os.path.join(base, lf)))
                if m:
                    lv = next(g for g in m.groups() if g)
                    break
        if lv:
            locked[k] = lv
        elif v.strip() in ("latest", "*", "") or v.startswith(("http", "git")) or not re.match(r"^\d+\.\d+\.\d+$", v.strip()):
            problems.append("%s: wrangler %r with no package-lock.json pinning it" % (k, v))
    for p in wfs:
        t = walk.read(p)
        r = walk.rel(repo, p)
        for m in re.finditer(r"npx\s+(?:--yes\s+|-y\s+)?wrangler(@[\w.\-]+)?", t):
            uses_wrangler = True
            ver = m.group(1)
            if ver == "@latest" or (not ver and not pinned_in_pkg):
                problems.append("%s:%d npx wrangler%s (no pinned version)" % (r, walk.line_of(t, m.start()), ver or ""))
        for m in re.finditer(r"uses:\s*['\"]?cloudflare/wrangler-action@\S+", t):
            uses_wrangler = True
            if "wranglerVersion" not in block(t.split("\n"), walk.line_of(t, m.start()) - 1):
                problems.append("%s:%d wrangler-action without wranglerVersion" % (r, walk.line_of(t, m.start())))
    if uses_wrangler:
        if problems:
            res.append(result("tooling.wrangler", "Deploy tool pinned to an exact version", "FAIL", ledger.join_hits(problems, 6, "; "), severity="low",
                              fix="pin wrangler in package.json (installed by npm ci) or as npx wrangler@<exact version>"))
        else:
            res.append(result("tooling.wrangler", "Deploy tool pinned to an exact version", "PASS",
                              ("wrangler locked at %s" % ", ".join("%s (%s)" % (lv, k) for k, lv in locked.items())) if locked else
                              ("wrangler pinned exactly in %s" % ", ".join(pinned_in_pkg)) if pinned_in_pkg else "every npx wrangler call carries an exact version"))
    return ledger.emit(res)


if __name__ == "__main__":
    sys.exit(main())
