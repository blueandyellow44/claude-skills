#!/usr/bin/env python3
"""check_cloudflare.py - Cloudflare Pages and Workers adapter, from the repo.

  check_cloudflare.py REPO

  cf.headers.framing / .hsts / .nosniff / .referrer
      each security header set for every path: in a `/*` block of a committed
      _headers file, by hono/secure-headers, or by code or next.config that sets
      it. Found nowhere FAILs (framing medium; others low; HSTS notes the
      HSTS-preloaded TLDs where plain http is never loaded).
  cf.vars-secrets
      a secret-looking name with a value in wrangler.toml/jsonc [vars] FAILs
      high: [vars] are plaintext and committed.
  cf.env-bindings
      a [env.<name>] block that reuses the production D1/KV/R2 id FAILs medium:
      the preview writes production data (found 2026-08-25).
What it cannot see is printed under cannot_see (zone rules, Access, WAF,
Pages project secrets, the pages.dev alias's exposure).
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

# A header that is present but says nothing does not count (Phase 5 audit #9).
VALUE_OK = {
    "framing": lambda v: bool(re.search(r"frame-ancestors\s+(?!\*\s*(?:;|$))[^;]+", v, re.I)) or v.strip().upper() in ("DENY", "SAMEORIGIN"),
    "hsts": lambda v: bool(re.search(r"max-age\s*=\s*(\d+)", v)) and int(re.search(r"max-age\s*=\s*(\d+)", v).group(1)) >= 15552000,
    "nosniff": lambda v: v.strip().lower() == "nosniff",
    "referrer": lambda v: v.strip().lower() not in ("unsafe-url", ""),
}
HEADER_LINE = {
    "framing": re.compile(r"^\s*(?:Content-Security-Policy|X-Frame-Options)\s*:\s*(.+)$", re.I | re.M),
    "hsts": re.compile(r"^\s*Strict-Transport-Security\s*:\s*(.+)$", re.I | re.M),
    "nosniff": re.compile(r"^\s*X-Content-Type-Options\s*:\s*(.+)$", re.I | re.M),
    "referrer": re.compile(r"^\s*Referrer-Policy\s*:\s*(.+)$", re.I | re.M),
}
HEADERS = {
    "framing": (re.compile(r"frame-ancestors|X-Frame-Options", re.I), "medium",
                "Content-Security-Policy: frame-ancestors 'self' <each origin that embeds the site> (run find_embedders.sh first)"),
    "hsts": (re.compile(r"Strict-Transport-Security", re.I), "low", "Strict-Transport-Security: max-age=31536000 (no preload: reversible)"),
    "nosniff": (re.compile(r"X-Content-Type-Options", re.I), "low", "X-Content-Type-Options: nosniff"),
    "referrer": (re.compile(r"Referrer-Policy", re.I), "low", "Referrer-Policy: strict-origin-when-cross-origin"),
}
SECRETISH = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSCODE|PRIVATE|CREDENTIAL|SALT|DSN", re.I)
PRELOADED = (".app", ".dev", ".page")


def headers_files(repo):
    out = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "out", "dist", "build") and not d.startswith(".")]
        if "_headers" in names:
            out.append(os.path.join(root, "_headers"))
    return out


def all_paths_block(text):
    """Header lines in blocks whose path covers every page (/* or /)."""
    out, cur = [], None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            cur = line.strip()
        elif cur in ("/*", "/", "https://:project.pages.dev/*") or (cur and cur.endswith("/*") and cur.count("/") <= 3 and "://" in cur):
            out.append(line.strip())
    return "\n".join(out)


def wrangler(repo):
    for f in ("wrangler.toml", "wrangler.jsonc", "wrangler.json"):
        t = walk.read(os.path.join(repo, f))
        if t:
            return f, t
    return None, ""


def toml_sections(t):
    """[(section, body)] for a TOML file, good enough for wrangler.toml."""
    out, cur, buf = [], "", []
    for line in t.splitlines():
        m = re.match(r"^\s*\[\[?([^\]]+)\]\]?\s*$", line)
        if m:
            out.append((cur, "\n".join(buf)))
            cur, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    out.append((cur, "\n".join(buf)))
    return out


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    hfiles = headers_files(repo)
    covered_text = "\n".join(all_paths_block(walk.read(p)) for p in hfiles)
    code_hits = {}
    secure_headers = list(walk.find(repo, r"secureHeaders\(", tests=False))
    for name, (rx, _, _) in HEADERS.items():
        for r, ln, _ in walk.find(repo, rx, exts=walk.CODE_EXT + (".mjs", ".cjs"), tests=False):
            code_hits.setdefault(name, "%s:%d" % (r, ln))
    for f in ("next.config.js", "next.config.mjs", "next.config.ts"):
        t = walk.read(os.path.join(repo, f))
        for name, (rx, _, _) in HEADERS.items():
            if rx.search(t) and "output: 'export'" not in t and 'output: "export"' not in t:
                code_hits.setdefault(name, f)
    _, wt = wrangler(repo)
    # Cloudflare Pages adds nosniff and Referrer-Policy to static assets by
    # default: measured 2026-10-08 on a production *.pages.dev project (no zone, so no
    # zone transform) with neither header in the repo. Not for Pages Functions
    # responses, not for Workers static assets.
    pages = any("pages_build_output_dir" in walk.read(os.path.join(repo, f))
                for f in os.listdir(repo) if f.startswith("wrangler") and f.endswith((".toml", ".json", ".jsonc")))
    deploy_texts = [walk.read(p) for p in walk.all_package_jsons(repo)]
    wfd = os.path.join(repo, ".github", "workflows")
    if os.path.isdir(wfd):
        deploy_texts += [walk.read(os.path.join(wfd, n)) for n in os.listdir(wfd)]
    sd = os.path.join(repo, "scripts")
    if os.path.isdir(sd):
        deploy_texts += [walk.read(os.path.join(sd, n)) for n in os.listdir(sd) if n.endswith((".sh", ".mjs", ".js", ".ts"))]
    # Comment lines do not deploy anything ("do NOT run wrangler pages deploy" in a coaching app's deploy.sh).
    live = ["\n".join(l for l in t.splitlines() if not l.lstrip().startswith(("#", "//", "*", "/*"))) for t in deploy_texts]
    worker = bool(re.search(r"""^\s*["']?main["']?\s*[=:]""", wt, re.M)) and "pages_build_output_dir" not in wt
    pages = pages or (not worker and any(re.search(r"""wrangler\S*["']?\s+pages\s+deploy""", t, re.I) for t in live))
    routes = re.findall(r"""pattern\s*[=:]\s*["']([^"']+)""", wt)
    preloaded = any(r.split("/")[0].endswith(PRELOADED) for r in routes)
    for name, (rx, sev, fix) in HEADERS.items():
        cid = "cf.headers." + name
        title = "%s header on every path" % {"framing": "Framing (frame-ancestors)", "hsts": "HSTS", "nosniff": "nosniff", "referrer": "Referrer-Policy"}[name]
        vals = [m.group(1) for m in HEADER_LINE[name].finditer(covered_text)]
        if vals and not any(VALUE_OK[name](v) for v in vals):
            res.append(result(cid, title, "FAIL", "_headers /* block sets it to a value that does not protect (%s)" % vals[0][:60], severity=sev, fix=fix))
        elif vals:
            src = [walk.rel(repo, p) for p in hfiles if rx.search(all_paths_block(walk.read(p)))]
            res.append(result(cid, title, "PASS", "%s (/* block)" % ledger.join_hits(src, 3, ", ")))
        elif secure_headers:
            res.append(result(cid, title, "PASS", "hono secureHeaders() at %s:%d (sets it by default)" % secure_headers[0][:2]))
        elif pages and name in ("nosniff", "referrer"):
            res.append(result(cid, title, "PASS", "Cloudflare Pages default on static assets (pages_build_output_dir set)",
                              detail="measured on a pages.dev alias 2026-10-08; Pages Functions responses do not get it, set it there in code"))
        elif name in code_hits:
            res.append(result(cid, title, "PASS", "set in code at %s" % code_hits[name], detail="set in code: confirm it applies to every response, including static assets"))
        else:
            where = ", ".join(walk.rel(repo, p) for p in hfiles) if hfiles else "no _headers file"
            res.append(result(cid, title, "FAIL", "%s; not set in code" % where, severity=sev, fix=fix,
                              detail="HSTS-preloaded TLD: browsers never load it over http, HSTS adds little" if name == "hsts" and preloaded else None))
    wf, wt = wrangler(repo)
    if wf:
        bad = []
        for sec, body in toml_sections(wt) if wf.endswith(".toml") else []:
            if sec == "vars" or sec.endswith(".vars"):
                for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(['\"])(.+?)\2", body, re.M):
                    if SECRETISH.search(m.group(1)) and not re.search(r"PUBLIC|PUBLISHABLE|SITE_KEY", m.group(1), re.I):
                        bad.append("%s [%s] %s" % (wf, sec, m.group(1)))
        if wf.endswith((".jsonc", ".json")):
            try:
                data = json.loads(re.sub(r"(?m)^\s*//.*$|/\*.*?\*/", "", wt, flags=re.S))
                for k, v in (data.get("vars") or {}).items():
                    if SECRETISH.search(k) and v and not re.search(r"PUBLIC|PUBLISHABLE|SITE_KEY", k, re.I):
                        bad.append("%s vars %s" % (wf, k))
            except ValueError:
                pass
        if bad:
            res.append(result("cf.vars-secrets", "No secrets in wrangler [vars]", "FAIL", ledger.join_hits(bad, 6, "; "), severity="high",
                              fix="move each to `wrangler secret put` / `wrangler pages secret put`, delete it from [vars], rotate it (it is in git history)"))
        else:
            res.append(result("cf.vars-secrets", "No secrets in wrangler [vars]", "PASS", "%s: no secret-looking name in vars" % wf))
        if wf.endswith(".toml"):
            secs = toml_sections(wt)
            prod_ids = set()
            for sec, body in secs:
                if not sec.startswith("env."):
                    prod_ids |= set(re.findall(r"(?:database_id|id|bucket_name)\s*=\s*['\"]([^'\"]+)", body))
            shared = []
            for sec, body in secs:
                if sec.startswith("env."):
                    for i in re.findall(r"(?:database_id|id|bucket_name)\s*=\s*['\"]([^'\"]+)", body):
                        if i in prod_ids:
                            shared.append("%s [%s] reuses a production binding id" % (wf, sec))
            if any(s.startswith("env.") for s, _ in secs):
                if shared:
                    res.append(result("cf.env-bindings", "Non-production environments use their own data", "FAIL", ledger.join_hits(sorted(set(shared)), 4, "; "), severity="medium",
                                      fix="give the preview its own D1/KV/R2 (or document the ruling that it shares production) before it runs writes"))
                else:
                    res.append(result("cf.env-bindings", "Non-production environments use their own data", "PASS", "%s: [env.*] binding ids differ from production" % wf))
    cannot = [
        "Cloudflare zone rules (rate limiting, WAF, Always Use HTTPS, zone HSTS): dashboard or a zone-write API token; the connector and wrangler were zone-read-only on 2026-10-07",
        "Cloudflare Access policies in front of any path: Zero Trust dashboard",
        "Pages/Worker secrets actually set in production: `npx wrangler pages secret list --project-name P` (names only)",
        "The *.pages.dev / *.workers.dev alias: zone rules do not apply there, so any limit that must hold belongs in code",
    ]
    return ledger.emit(res, cannot_see=cannot)


if __name__ == "__main__":
    sys.exit(main())
