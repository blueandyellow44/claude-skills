#!/usr/bin/env python3
"""check_nextjs.py - Next.js (and OpenNext on Cloudflare) adapter.

  check_nextjs.py REPO

  next.server-actions        an exported 'use server' function with no auth
                             call in its body FAILs high: every server action
                             is a public POST endpoint.
  next.public-env-secrets    a NEXT_PUBLIC_ variable named like a secret
                             (SECRET, SERVICE_ROLE, PRIVATE, PASSWORD, TOKEN)
                             FAILs high: it ships in the browser bundle.
  next.static-export-headers a static export (output: 'export') that relies on
                             next.config headers() FAILs medium: headers() is
                             ignored by a static export, so the security
                             headers never reach the browser.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import surface  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

FN = re.compile(r"export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*(?::[^{]+)?\{|export\s+const\s+(\w+)\s*=\s*async\s*\([^)]*\)\s*(?::[^=]+)?=>\s*\{")
PUBLIC_SECRET = re.compile(r"NEXT_PUBLIC_\w*(?:SECRET|SERVICE_ROLE|PRIVATE|PASSWORD|TOKEN)\w*")


def body_at(t, start):
    depth, i = 0, t.index("{", start)
    for j in range(i, min(len(t), i + 20000)):
        if t[j] == "{":
            depth += 1
        elif t[j] == "}":
            depth -= 1
            if depth == 0:
                return t[i:j + 1]
    return t[i:i + 4000]


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    cfg_name, cfg = None, ""
    for f in ("next.config.ts", "next.config.mjs", "next.config.js"):
        cfg = walk.read_code(os.path.join(repo, f))
        if cfg:
            cfg_name = f
            break
    static_export = bool(re.search(r"""output\s*:\s*['"]export['"]""", cfg))

    actions, unguarded = 0, []
    if not static_export:
        for p in walk.files(repo, exts=(".ts", ".tsx", ".js", ".jsx"), tests=False, served=True):
            t = walk.read_code(p)
            file_level = re.match(r"""\s*(?:/\*.*?\*/\s*|//[^\n]*\n\s*)*['"]use server['"]""", t, re.S)
            if not file_level and "'use server'" not in t and '"use server"' not in t:
                continue
            for m in FN.finditer(t):
                b = body_at(t, m.start())
                if not file_level and not re.match(r"""\{\s*['"]use server['"]""", b):
                    continue
                actions += 1
                if not surface.AUTH_RX.search(b):
                    unguarded.append("%s:%d %s" % (walk.rel(repo, p), walk.line_of(t, m.start()), m.group(1) or m.group(2)))
        if unguarded:
            res.append(result("next.server-actions", "Server actions check who is calling", "FAIL", ledger.join_hits(unguarded, 8, "; "), severity="high",
                              fix="call the session check (and ownership) at the top of every server action; actions are public POST endpoints"))
        elif actions:
            res.append(result("next.server-actions", "Server actions check who is calling", "PASS", "%d server action(s), each with an auth call" % actions))

    pub = ["%s:%d %s" % (r, ln, m.group(0)) for r, ln, m in walk.find(repo, PUBLIC_SECRET, exts=walk.CODE_EXT + (".env", ".example", ".toml", ".json"), tests=False, served=True)]
    for f in (".env", ".env.local", ".env.production", ".env.example", ".dev.vars.example"):
        for i, line in enumerate(walk.read_code(os.path.join(repo, f)).splitlines(), 1):
            m = PUBLIC_SECRET.search(line.split("=")[0])
            if m:
                pub.append("%s:%d %s" % (f, i, m.group(0)))
    if pub:
        res.append(result("next.public-env-secrets", "No secret in a NEXT_PUBLIC_ variable", "FAIL", ledger.join_hits(sorted(set(pub)), 6, "; "), severity="high",
                          fix="drop the NEXT_PUBLIC_ prefix, read it server-side only, rotate it (it has shipped to browsers)"))
    else:
        res.append(result("next.public-env-secrets", "No secret in a NEXT_PUBLIC_ variable", "PASS", "no NEXT_PUBLIC_ name with SECRET/SERVICE_ROLE/PRIVATE/PASSWORD/TOKEN"))

    if static_export and re.search(r"async\s+headers\s*\(|headers\s*:\s*async", cfg):
        has_file = any(os.path.exists(os.path.join(repo, d, "_headers")) for d in ("public", ".", "static"))
        if has_file:
            res.append(result("next.static-export-headers", "Security headers reach a static export", "PASS", "static export with a _headers file (headers() in %s is ignored, the file is not)" % cfg_name))
        else:
            res.append(result("next.static-export-headers", "Security headers reach a static export", "FAIL", "%s: output 'export' plus headers(); no public/_headers" % cfg_name,
                              severity="medium", fix="move the headers into public/_headers (Cloudflare Pages reads it); headers() does nothing in a static export"))
    return ledger.emit(res, cannot_see=["Next middleware matchers are read as text: a matcher that skips a path is not evaluated",
                                        "OpenNext bindings and the deployed Worker's secrets: `npx wrangler secret list` (names only)"])


if __name__ == "__main__":
    sys.exit(main())
