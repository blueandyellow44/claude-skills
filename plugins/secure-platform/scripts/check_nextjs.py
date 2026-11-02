#!/usr/bin/env python3
"""check_nextjs.py - Next.js (and OpenNext on Cloudflare) adapter.

  check_nextjs.py REPO

  next.server-actions        a server action with no ENFORCED auth check in its
                             body FAILs high: every server action is a public
                             POST endpoint. An action is an exported function
                             in a file-level 'use server' module, or any
                             function (exported or an inline closure inside a
                             component) whose body opens with 'use server'.
                             Enforced means a guard by name (requireUser,
                             verifySession, 401/403, an owner filter) or a
                             session read (getSession, auth(), currentUser)
                             followed by a rejection: if (!session) with a
                             throw, return or redirect. Reading the session and
                             only logging it does not count.
  next.public-env-secrets    a NEXT_PUBLIC_ variable whose name is shaped like a
                             secret (SECRET, SERVICE_ROLE, PRIVATE, PASSWORD,
                             TOKEN, or a KEY / API_KEY suffix) FAILs high: it
                             ships in the browser bundle. Public-by-design names
                             PASS: *_PUBLISHABLE_KEY, *_SITE_KEY, *_ANON_KEY,
                             *_PUBLIC_KEY, MAPBOX_TOKEN (the allowlist and why
                             live in secure-core/lib/names.py).
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
from names import secret_name  # noqa: E402  (one secret-name vocabulary for every adapter)
from ledger import result  # noqa: E402

# group 1/2: export prefix and name of a function declaration; group 3/4: the same for `const name = async (...) => {`.
FN = re.compile(r"(export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*(?::[^{]+)?\{"
                r"|(export\s+)?const\s+(\w+)\s*=\s*async\s*\([^)]*\)\s*(?::[^=]+)?=>\s*\{")
PUBLIC_VAR = re.compile(r"NEXT_PUBLIC_[A-Za-z0-9_]+")
# Auth names that only READ who is calling; on their own they enforce nothing.
SESSION_READ = re.compile(r"^(?:getSession|getServerSession|auth\(\)|currentUser|readSession|sessionFrom|getUser\(|signedInUser|userFromRequest)$", re.I)
# What turns a session read into a check: a null guard, or a rejection (throw, redirect, notFound, unauthorized, forbidden).
GUARD = re.compile(r"if\s*\(\s*!\s*\w*(?:session|user|auth|uid|account|member|viewer)|if\s*\(\s*\w*(?:session|user)\w*(?:\?\.\w+)*\s*[!=]==?\s*(?:null|undefined)"
                   r"|\bthrow\b|\bredirect\s*\(|\bnotFound\s*\(|\bunauthorized\s*\(|\bforbidden\s*\(", re.I)


def body_at(t, open_index):
    """The balanced { ... } block that opens at open_index."""
    depth, i = 0, open_index
    for j in range(i, min(len(t), i + 20000)):
        if t[j] == "{":
            depth += 1
        elif t[j] == "}":
            depth -= 1
            if depth == 0:
                return t[i:j + 1]
    return t[i:i + 4000]


def enforced(body):
    """An auth guard by name, or a session read plus a rejection of a missing session."""
    hits = [m.group(0) for m in surface.AUTH_RX.finditer(body)]
    if not hits:
        return False
    if any(not SESSION_READ.match(h) for h in hits):
        return True
    return bool(GUARD.search(body))


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
                exported = bool(m.group(1) or m.group(3))
                name = m.group(2) or m.group(4)
                b = body_at(t, m.end() - 1)
                inline = bool(re.match(r"""\{\s*['"]use server['"]""", b))
                # a file-level directive exports its actions; an inline directive makes any function an action
                if not inline and not (file_level and exported):
                    continue
                actions += 1
                if not enforced(b):
                    unguarded.append("%s:%d %s" % (walk.rel(repo, p), walk.line_of(t, m.start()), name))
        if unguarded:
            res.append(result("next.server-actions", "Server actions check who is calling", "FAIL", ledger.join_hits(unguarded, 8, "; "), severity="high",
                              fix="call the session check at the top of every server action and reject a missing session (throw or redirect); actions are public POST endpoints"))
        elif actions:
            res.append(result("next.server-actions", "Server actions check who is calling", "PASS", "%d server action(s), each with an enforced auth check" % actions))

    pub = ["%s:%d %s" % (r, ln, m.group(0)) for r, ln, m in walk.find(repo, PUBLIC_VAR, exts=walk.CODE_EXT + (".env", ".example", ".toml", ".json"), tests=False, served=True)
           if secret_name(m.group(0)[len("NEXT_PUBLIC_"):], browser=True)]
    for f in (".env", ".env.local", ".env.production", ".env.example", ".dev.vars.example"):
        for i, line in enumerate(walk.read_code(os.path.join(repo, f)).splitlines(), 1):
            m = PUBLIC_VAR.search(line.split("=")[0])
            if m and secret_name(m.group(0)[len("NEXT_PUBLIC_"):], browser=True):
                pub.append("%s:%d %s" % (f, i, m.group(0)))
    if pub:
        res.append(result("next.public-env-secrets", "No secret in a NEXT_PUBLIC_ variable", "FAIL", ledger.join_hits(sorted(set(pub)), 6, "; "), severity="high",
                          fix="drop the NEXT_PUBLIC_ prefix, read it server-side only, rotate it (it has shipped to browsers)"))
    else:
        res.append(result("next.public-env-secrets", "No secret in a NEXT_PUBLIC_ variable", "PASS", "no NEXT_PUBLIC_ name shaped like a secret (SECRET/SERVICE_ROLE/PRIVATE/PASSWORD/TOKEN/KEY; publishable, site and anon keys allowed)"))

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
