#!/usr/bin/env python3
"""load_built.py - does the BUILT code load under plain Node?

  load_built.py REPO [--dir dist ...] [--entry dist/lib.js ...]

Lesson 2026-10-07 (a news-scoring app): @extractus/article-extractor 8.1.0 passed every
vitest test and broke under Node, because vitest resolves modules its own way
and the new version's exports map hid a subpath Node needed.

Two levels, both under Node itself, never vitest:
  1. built.resolve: every bare import and require in the built files (default
     dist/, build/, out/ with .js/.mjs/.cjs) is resolved with Node's own
     resolver from that file (import.meta.resolve for imports, require.resolve
     for requires). Nothing is executed. Any ERR_PACKAGE_PATH_NOT_EXPORTED or
     ERR_MODULE_NOT_FOUND FAILs.
  2. built.import: only for entries named with --entry or listed in
     security/load-check.json {"entries": [...]}: each is imported in a child
     Node with a 20 s timeout and an EMPTY environment (no secrets reach it).
     Only list side-effect-free modules there; a main that starts a server or
     runs a job does not belong in the list.
No built output: UNKNOWN (build first; this check never builds).
Bundled output with no bare imports (a Worker bundle) is a PASS with that
noted: there is nothing left for Node to resolve.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

IMPORT_RX = re.compile(r"""(?:^|[;\s}])(?:import\s+(?:[\w*{}\s,$]+\s+from\s+)?|export\s+[\w*{}\s,$]*\s+from\s+|import\()\s*['"]([^'"]+)['"]""", re.M)
REQUIRE_RX = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
BUILTIN_PREFIX = ("node:", "cloudflare:", "bun:", "data:", "http:", "https:", "virtual:")

RESOLVER = r"""
import {createRequire, builtinModules} from 'node:module';
import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
const items = JSON.parse(readFileSync(0, 'utf8'));
const out = [];
for (const it of items) {
  const base = it.spec.startsWith('@') ? it.spec.split('/').slice(0, 2).join('/') : it.spec.split('/')[0];
  if (builtinModules.includes(it.spec) || builtinModules.includes(base)) continue;
  try {
    if (it.kind === 'import') import.meta.resolve(it.spec, pathToFileURL(it.file).href);
    else createRequire(it.file).resolve(it.spec);
  } catch (e) { out.push({file: it.file, spec: it.spec, kind: it.kind, code: e.code || e.name}); }
}
process.stdout.write(JSON.stringify(out));
"""


def built_files(repo, dirs):
    out = []
    for d in dirs:
        root = os.path.join(repo, d)
        if not os.path.isdir(root):
            continue
        for r, ds, names in os.walk(root):
            # browser chunks (Next static output) are not code Node runs
            ds[:] = [x for x in ds if x not in ("node_modules", "static", "_next", "chunks", "assets", "client")]
            for n in names:
                if n.endswith((".js", ".mjs", ".cjs")) and not n.endswith(".min.js"):
                    out.append(os.path.join(r, n))
    return out[:3000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--dir", action="append")
    ap.add_argument("--entry", action="append", default=[])
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    node = shutil.which("node")
    if not node:
        return ledger.emit([result("built.resolve", "Built code resolves under Node", "UNKNOWN", repo, reason="node not installed")])
    dirs = a.dir or ["dist", "build", "out", "lib"]
    files = built_files(repo, dirs)
    res = []
    if not files:
        res.append(result("built.resolve", "Built code resolves under Node", "UNKNOWN", "looked in %s" % ", ".join(dirs),
                          reason="no built output found; run the build, then re-run (this check never builds)"))
    else:
        items = []
        for f in files:
            t = walk.read(f)
            for m in IMPORT_RX.finditer(t):
                s = m.group(1)
                if not s.startswith((".", "/")) and not s.startswith(BUILTIN_PREFIX):
                    items.append({"file": f, "spec": s, "kind": "import"})
            for m in REQUIRE_RX.finditer(t):
                s = m.group(1)
                if not s.startswith((".", "/")) and not s.startswith(BUILTIN_PREFIX):
                    items.append({"file": f, "spec": s, "kind": "require"})
        seen, uniq = set(), []
        for it in items:
            k = (os.path.dirname(it["file"]), it["spec"], it["kind"])
            if k not in seen:
                seen.add(k)
                uniq.append(it)
        if not uniq:
            res.append(result("built.resolve", "Built code resolves under Node", "PASS",
                              "%d built file(s), no bare imports left (bundled)" % len(files)))
        else:
            r = _resolve(node, uniq)
            if r is None:
                res.append(result("built.resolve", "Built code resolves under Node", "UNKNOWN", "node resolver", reason="resolver did not run"))
            elif r:
                ev = "; ".join("%s: %s %s (%s)" % (walk.rel(repo, x["file"]), x["kind"], x["spec"], x["code"]) for x in r[:6])
                res.append(result("built.resolve", "Built code resolves under Node", "FAIL", ev, severity="high",
                                  fix="pin the dependency to the last version that resolves, or fix the import path; do not trust the test runner for this",
                                  detail="%d of %d imports fail under Node's resolver" % (len(r), len(uniq))))
            else:
                res.append(result("built.resolve", "Built code resolves under Node", "PASS",
                                  "%d imports across %d built files resolve with Node %s" % (len(uniq), len(files), _node_version(node))))
    entries = list(a.entry)
    cfg = os.path.join(repo, "security", "load-check.json")
    if os.path.exists(cfg):
        try:
            entries += json.load(open(cfg)).get("entries", [])
        except ValueError:
            res.append(result("built.import", "Declared built modules import under Node", "UNKNOWN", "security/load-check.json", reason="unparseable JSON"))
    for e in entries:
        p = os.path.join(repo, e)
        cid = "built.import.%s" % re.sub(r"[^A-Za-z0-9_.-]", "_", e)
        if not os.path.exists(p):
            res.append(result(cid, "%s imports under Node" % e, "UNKNOWN", e, reason="file not found; build first"))
            continue
        try:
            r = subprocess.run([node, "--input-type=module", "-e", "await import(%s)" % json.dumps("file://" + os.path.abspath(p))],
                               capture_output=True, text=True, timeout=20, env={"PATH": os.environ.get("PATH", "")}, cwd=os.path.dirname(p))
        except subprocess.TimeoutExpired:
            res.append(result(cid, "%s imports under Node" % e, "UNKNOWN", e, reason="import did not finish in 20 s (it runs something; remove it from the entry list)"))
            continue
        if r.returncode == 0:
            res.append(result(cid, "%s imports under Node" % e, "PASS", "node import of %s exited 0" % e))
        else:
            code = re.search(r"\b(ERR_[A-Z_]+|SyntaxError|TypeError|ReferenceError)\b", r.stderr)
            res.append(result(cid, "%s imports under Node" % e, "FAIL", "%s: %s" % (e, code.group(1) if code else "exit %d" % r.returncode),
                              severity="high", fix="fix the import or pin the dependency that broke it, then re-run under Node"))
    return ledger.emit(res)


def _resolve(node, items):
    """Failures from Node's own resolver, or None when the resolver itself did not run."""
    try:
        r = subprocess.run([node, "--experimental-import-meta-resolve", "--no-warnings", "--input-type=module", "-e", RESOLVER],
                           input=json.dumps(items), capture_output=True, text=True, timeout=120)
        return json.loads(r.stdout)
    except (subprocess.TimeoutExpired, ValueError):
        return None


def _node_version(node):
    return subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    sys.exit(main())
