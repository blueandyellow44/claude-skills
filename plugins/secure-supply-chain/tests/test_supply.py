#!/usr/bin/env python3
"""secure-supply-chain tests. Known-bad first. Network-free: audits come from saved JSON."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "secure-core", "lib"))
import testkit as T  # noqa: E402

S = os.path.join(HERE, "..", "scripts")

# ---------- check_deps ----------
AUDIT_BAD = {"vulnerabilities": {
    "next": {"severity": "critical", "fixAvailable": {"name": "next", "version": "16.0.0", "isSemVerMajor": True},
             "via": [{"source": 1101, "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc"}]},
    "@extractus/article-extractor": {"severity": "high", "fixAvailable": {"name": "@extractus/article-extractor", "version": "8.1.0", "isSemVerMajor": False},
             "via": [{"source": 1102, "url": "https://github.com/advisories/GHSA-dddd-eeee-ffff"}]},
    "nanoid": {"severity": "moderate", "fixAvailable": True, "via": [{"source": 1103, "url": "https://github.com/advisories/GHSA-gggg-hhhh-jjjj"}]},
}}
bad = T.tree({"package.json": "{}", "package-lock.json": "{}", "audit.json": json.dumps(AUDIT_BAD), "web/package.json": "{}"})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), bad, "--audit-json", os.path.join(bad, "audit.json"))
T.status_is("deps bad", c, "deps.audit.root.next", "FAIL", out)
T.expect("deps: a major fix is named as a separate decision", "MAJOR" in c.get("deps.audit.root.next", {}).get("fix", ""))
T.status_is("deps bad", c, "deps.audit.root.@extractus/article-extractor", "FAIL", out)
T.status_is("deps bad", c, "deps.audit.root.moderate", "FAIL", out)
T.status_is("deps bad", c, "deps.lockfile.web", "FAIL", out)

good = T.tree({"package.json": "{}", "package-lock.json": "{}", "audit.json": json.dumps(AUDIT_BAD),
               "security/advisory-triage.json": json.dumps({"advisories": [
                   {"package": "next", "advisory": "GHSA-aaaa-bbbb-cccc", "reachable": False, "reason": "static export: the Next server never runs", "reviewed": "2026-10-08"},
                   {"package": "@extractus/article-extractor", "advisory": "1102", "reachable": False, "reason": "parser path not imported", "reviewed": "2026-10-08"},
                   {"package": "nanoid", "advisory": "GHSA-gggg-hhhh-jjjj", "reachable": False, "reason": "build-only", "reviewed": "2026-10-08"}]})})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), good, "--audit-json", os.path.join(good, "audit.json"))
T.expect("deps: everything triaged unreachable, with reasons shown, is all PASS", rc == 0 and all(v["status"] == "PASS" for v in c.values()) and "static export" in json.dumps(c), out[-400:])
reach = T.tree({"package.json": "{}", "package-lock.json": "{}", "audit.json": json.dumps(AUDIT_BAD),
                "security/advisory-triage.json": json.dumps({"advisories": [{"package": "next", "advisory": "GHSA-aaaa-bbbb-cccc", "reachable": True, "reason": "SSR runs", "reviewed": "2026-10-08"}]})})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), reach, "--audit-json", os.path.join(reach, "audit.json"))
T.expect("deps: triaged REACHABLE stays FAIL", c.get("deps.audit.root.next", {}).get("status") == "FAIL" and "REACHABLE" in c["deps.audit.root.next"].get("detail", ""))
err = T.tree({"package.json": "{}", "package-lock.json": "{}", "audit.json": json.dumps({"error": {"summary": "getaddrinfo ENOTFOUND registry.npmjs.org"}})})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), err, "--audit-json", os.path.join(err, "audit.json"))
T.status_is("deps offline", c, "deps.audit.root", "UNKNOWN", out)
T.expect("deps: offline audit exits 3, never 0", rc == 3)

# ---------- check_pinning ----------
WF_BAD = """name: deploy
on: push
env:
  CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
jobs:
  build:
    runs-on: ubuntu-latest
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: some-org/deploy-action@main
      - run: npx wrangler@latest pages deploy out
      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
"""
bad = T.tree({".github/workflows/deploy.yml": WF_BAD, "package.json": "{}"})
rc, c, out = T.run(os.path.join(S, "check_pinning.py"), bad)
T.status_is("pinning bad", c, "actions.pinned", "FAIL", out)
T.expect("pinning: a third-party tag makes it medium", c.get("actions.pinned", {}).get("severity") == "medium")
T.status_is("pinning bad", c, "actions.secret-scope", "FAIL", out)
T.expect("pinning: both the workflow- and job-level env are named", "workflow-level" in c["actions.secret-scope"]["evidence"] and "job-level" in c["actions.secret-scope"]["evidence"])
T.status_is("pinning bad", c, "tooling.wrangler", "FAIL", out)
SHA1 = "a" * 40
WF_GOOD = """name: deploy
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@%s # v4.2.2
      - run: npm ci
      - name: deploy
        run: npx wrangler pages deploy out
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
""" % SHA1
good = T.tree({".github/workflows/deploy.yml": WF_GOOD, "package.json": json.dumps({"devDependencies": {"wrangler": "4.148.0"}})})
rc, c, out = T.run(os.path.join(S, "check_pinning.py"), good)
for cid in ("actions.pinned", "actions.secret-scope", "tooling.wrangler"):
    T.status_is("pinning good", c, cid, "PASS", out)

# ---------- load_built ----------
def pkgtree(entry_src):
    return T.tree({
        "node_modules/fakepkg/package.json": json.dumps({"name": "fakepkg", "exports": {".": "./index.js"}}),
        "node_modules/fakepkg/index.js": "export default 1\n",
        "node_modules/fakepkg/sub.js": "export default 2\n",
        "package.json": json.dumps({"type": "module"}),
        "dist/server.js": entry_src,
    })
bad = pkgtree("import x from 'fakepkg/sub';\nconsole.log(x)\n")
rc, c, out = T.run(os.path.join(S, "load_built.py"), bad)
T.status_is("built bad", c, "built.resolve", "FAIL", out)
T.expect("built: names the exports-map error", "ERR_PACKAGE_PATH_NOT_EXPORTED" in c.get("built.resolve", {}).get("evidence", ""))
good = pkgtree("import x from 'fakepkg';\nimport fs from 'node:fs';\nexport const y = x;\n")
rc, c, out = T.run(os.path.join(S, "load_built.py"), good, "--entry", "dist/server.js")
T.status_is("built good", c, "built.resolve", "PASS", out)
T.status_is("built good", c, "built.import.dist_server.js", "PASS", out)
broken_entry = pkgtree("import x from 'fakepkg';\nthrow new TypeError('boom at import');\n")
rc, c, out = T.run(os.path.join(S, "load_built.py"), broken_entry, "--entry", "dist/server.js")
T.status_is("built entry throws", c, "built.import.dist_server.js", "FAIL", out)
none = T.tree({"package.json": "{}", "src/index.ts": "export {}"})
rc, c, out = T.run(os.path.join(S, "load_built.py"), none)
T.status_is("no build", c, "built.resolve", "UNKNOWN", out)
T.expect("built: no build output exits 3, never 0", rc == 3)

# ---------- pnpm audit report shape (a classroom app, Phase 4) ----------
PNPM = {"actions": [], "advisories": {"1": {"module_name": "undici", "severity": "high", "patched_versions": ">=6.21.1"},
                                      "2": {"module_name": "esbuild", "severity": "moderate", "patched_versions": ">=0.25.0"}},
        "metadata": {"vulnerabilities": {"high": 1, "moderate": 1}}}
pn = T.tree({"package.json": "{}", "pnpm-lock.yaml": "lockfileVersion: 9\n", "audit.json": json.dumps(PNPM)})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), pn, "--audit-json", os.path.join(pn, "audit.json"))
T.status_is("pnpm format", c, "deps.audit.root.undici", "FAIL", out)
T.status_is("pnpm format", c, "deps.audit.root.moderate", "FAIL", out)
pn_clean = T.tree({"package.json": "{}", "pnpm-lock.yaml": "x\n", "audit.json": json.dumps({"actions": [], "advisories": {}, "metadata": {}})})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), pn_clean, "--audit-json", os.path.join(pn_clean, "audit.json"))
T.status_is("pnpm clean", c, "deps.audit.root.moderate", "PASS", out)

# ---------- Phase 5 audit #13: a triage covers one advisory, never every future one in the package ----------
newer = json.loads(json.dumps(AUDIT_BAD))
newer["vulnerabilities"]["next"]["via"].append({"source": 1201, "url": "https://github.com/advisories/GHSA-zzzz-yyyy-xxxx"})
nr = T.tree({"package.json": "{}", "package-lock.json": "{}", "audit.json": json.dumps(newer),
             "security/advisory-triage.json": json.dumps({"advisories": [
                 {"package": "next", "advisory": "GHSA-aaaa-bbbb-cccc", "reachable": False, "reason": "static export", "reviewed": "2026-10-08"}]})})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), nr, "--audit-json", os.path.join(nr, "audit.json"))
T.status_is("audit #13: a new advisory in a triaged package", c, "deps.audit.root.next", "FAIL", out)
T.expect("audit #13: the untriaged advisory is named", "GHSA-zzzz-yyyy-xxxx" in c.get("deps.audit.root.next", {}).get("detail", ""))
pkg_only = T.tree({"package.json": "{}", "package-lock.json": "{}", "audit.json": json.dumps(AUDIT_BAD),
                   "security/advisory-triage.json": json.dumps({"advisories": [{"package": "next", "reachable": False, "reason": "r", "reviewed": "2026-10-08"}]})})
rc, c, out = T.run(os.path.join(S, "check_deps.py"), pkg_only, "--audit-json", os.path.join(pkg_only, "audit.json"))
T.status_is("audit #13: a package-level triage with no advisory id covers nothing", c, "deps.audit.root.next", "FAIL", out)

# ---------- Phase 5 audit: composite actions and inline env maps ----------
comp = T.tree({".github/workflows/ci.yml": "on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    env: { TOKEN: ${{ secrets.TOKEN }} }\n    steps:\n      - uses: ./.github/actions/setup\n",
               ".github/actions/setup/action.yml": "runs:\n  using: composite\n  steps:\n    - uses: some-org/thing@v2\n"})
rc, c, out = T.run(os.path.join(S, "check_pinning.py"), comp)
T.status_is("audit: a composite action's unpinned uses is seen", c, "actions.pinned", "FAIL", out)
T.status_is("audit: an inline job-level env map with a secret is seen", c, "actions.secret-scope", "FAIL", out)

# ---------- second audit: a caret range with no lockfile is not pinned ----------
car = T.tree({".github/workflows/d.yml": "jobs:\n  d:\n    steps:\n      - run: npx wrangler deploy\n", "package.json": json.dumps({"devDependencies": {"wrangler": "^4.0.0"}})})
rc, c, out = T.run(os.path.join(S, "check_pinning.py"), car)
T.status_is("audit 2: wrangler ^4 with no lockfile", c, "tooling.wrangler", "FAIL", out)
lockd = T.tree({".github/workflows/d.yml": "jobs:\n  d:\n    steps:\n      - run: npx wrangler deploy\n", "package.json": json.dumps({"devDependencies": {"wrangler": "^4.0.0"}}),
                "package-lock.json": json.dumps({"packages": {"node_modules/wrangler": {"version": "4.148.0"}}})})
rc, c, out = T.run(os.path.join(S, "check_pinning.py"), lockd)
T.expect("a caret range locked by package-lock.json PASSes and names the locked version", c.get("tooling.wrangler", {}).get("status") == "PASS" and "4.148.0" in c["tooling.wrangler"]["evidence"], out[-200:])

T.finish()
