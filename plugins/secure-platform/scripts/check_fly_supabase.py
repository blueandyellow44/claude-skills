#!/usr/bin/env python3
"""check_fly_supabase.py - Fly.io and Supabase adapter.

  check_fly_supabase.py REPO

  fly.env-secrets        a secret-looking name in fly.toml [env] FAILs high
                         ([env] is plaintext and committed; use fly secrets).
                         A name is a secret by its words (KEY, TOKEN, SECRET,
                         PASSWORD, PRIVATE, CREDENTIAL, DSN, a database URL) or
                         by a key-shaped value; public-by-design names (ANON_KEY,
                         PUBLISHABLE_KEY, SITE_KEY, PUBLIC_KEY) and names that
                         hold a setting about a secret (TOKEN_ISSUER, KEY_ID,
                         PRIVATE_KEY_PATH, SESSION_TOKEN_TTL_SECONDS) are not.
                         Every fly.toml in the repo is read (one app per folder
                         in a monorepo); with several, the id carries the folder.
  fly.exposure           a public [[services.ports]] port is a web port only
                         when its handlers include "http"; a raw TCP port, a
                         tls-only or pg_tls handler, or any database port (5432,
                         3306, 6379, 27017, ...) FAILs medium; force_https =
                         false FAILs low.
  supabase.rls           every table a migration creates in the public schema
                         has ENABLE ROW LEVEL SECURITY in some migration; a
                         missing one FAILs high. A public view without
                         security_invoker (or a materialized view) bypasses the
                         tables' RLS and FAILs. A write policy whose condition
                         is always true (true, 1=1) or true for every signed-in
                         user (auth.uid() is not null, auth.role() =
                         'authenticated') FAILs; owner-bound conditions
                         (auth.uid() = user_id) and SELECT policies pass.
                         Schemas are parsed: private.audit_log is not a public
                         table. No migrations: UNKNOWN.
  supabase.service-role  the service-role key referenced from browser code
                         FAILs critical: 'use client' files, components/,
                         public/, client/ paths, a public env prefix
                         (NEXT_PUBLIC_/VITE_/PUBLIC_) on the key, every src/
                         file of a Vite SPA (the whole bundle ships), a module
                         a browser file imports, or a vite.config `define` that
                         inlines the key. An App Router page.tsx without 'use
                         client' is a Server Component and is not browser code.
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
from names import secret_name  # noqa: E402  (one secret-name vocabulary for every adapter)

DB_PORTS = {5432, 5433, 6432, 3306, 3307, 6379, 27017, 27018, 9200, 9300, 11211, 5672, 9042, 7000, 7001, 2379, 8086, 1433, 1521}
# "pg_tls" and friends: a handler whose protocol is a database wire protocol, not the web
NON_WEB_HANDLERS = re.compile(r"^(?:pg|mysql|redis|mongo|tcp|proxy_proto|proxy_protocol)\w*$", re.I)


# ---- SQL ----
IDENT = r"(\"?[A-Za-z_]\w*\"?)(?:\s*\.\s*(\"?[A-Za-z_]\w*\"?))?"
CREATE = re.compile(r"\bcreate\s+(?:(?:global\s+|local\s+)?(?:temp|temporary|unlogged)\s+)?table\s+(?:if\s+not\s+exists\s+)?" + IDENT, re.I)
CREATE_VIEW = re.compile(r"\bcreate\s+(?:or\s+replace\s+)?(?:(materialized)\s+)?(?:recursive\s+)?view\s+(?:if\s+not\s+exists\s+)?" + IDENT, re.I)
ALTER_RLS = re.compile(r"\balter\s+table\s+(?:only\s+)?(?:if\s+exists\s+)?" + IDENT + r"\s+(enable|disable)\s+row\s+level\s+security", re.I)
ALTER_VIEW_INVOKER = re.compile(r"\balter\s+(?:materialized\s+)?(?:view|table)\s+(?:if\s+exists\s+)?" + IDENT + r"\s+set\s*\(\s*security_invoker\s*(?:=\s*)?(true|on|false|off)?\s*\)", re.I)
INVOKER_ON = re.compile(r"security_invoker\s*(?:=\s*)?(?:true|on)\b|\bsecurity_invoker\s*(?:,|\))", re.I)
POLICY = re.compile(r"\bcreate\s+policy\s+(?:\"[^\"]*\"|\w+)\s+on\s+" + IDENT, re.I)
POLICY_CMD = re.compile(r"\bfor\s+(select|insert|update|delete|all)\b", re.I)
# conditions true for anyone, or for every signed-in user, after normalization (see _normalize_cond)
ALWAYS_TRUE = re.compile(r"^(?:true|1=1|true is true|'t'|'true'|'1')$")
ANY_SIGNED_IN = re.compile(r"^(?:auth\.(?:uid|jwt|role|email)\(\) is not null|auth\.role\(\) ?= ?'(?:authenticated|anon|service_role)'|"
                           r"auth\.uid\(\) ?(?:<>|!=) ?''|current_user ?= ?'authenticated'|coalesce\(auth\.uid\(\)[^)]*\) is not null)$")


def _paren(text, start):
    """The text inside the balanced parentheses that open at or after `start`."""
    i = text.find("(", start)
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
    return None


def _normalize_cond(expr):
    e = re.sub(r"\s+", " ", expr.strip().lower())
    while e.startswith("(") and e.endswith(")") and _paren(e, 0) == e[1:-1]:
        e = e[1:-1].strip()
    e = re.sub(r"\(\s*select\s+(auth\.\w+\(\))\s*\)", r"\1", e)  # (select auth.uid()) is the cached form
    e = re.sub(r"\s*=\s*", "=", e) if re.match(r"^1\s*=\s*1$", e) else e
    return e


def open_policy_reason(expr):
    """'always true', 'any signed-in user' or None for a policy condition."""
    e = _normalize_cond(expr)
    if ALWAYS_TRUE.match(e):
        return "always true"
    if ANY_SIGNED_IN.match(e):
        return "true for any signed-in user"
    return None


def qual(m, i=1):
    """(schema, table) from an IDENT match at groups i, i+1; schema defaults to public."""
    a, b = m.group(i), m.group(i + 1)
    a = a.replace('"', "")
    if b:
        return a.lower(), b.replace('"', "")
    return "public", a


def statements(sql):
    """(start_index, statement_text) for each ;-terminated statement, comments removed."""
    t = re.sub(r"--[^\n]*", lambda mm: " " * len(mm.group(0)), sql)  # SQL comments never enable anything
    t = re.sub(r"/\*.*?\*/", lambda mm: "".join(c if c == "\n" else " " for c in mm.group(0)), t, flags=re.S)
    out, start = [], 0
    for m in re.finditer(r";", t):
        out.append((start, t[start:m.start()]))
        start = m.end()
    if t[start:].strip():
        out.append((start, t[start:]))
    return t, out


def replay(repo, migs):
    """Replay migrations in order: the last word on each table counts (enable then a later disable is OFF)."""
    created, rls, views, view_ok, open_pol = {}, {}, {}, {}, []
    for m_path in sorted(migs):
        t, stmts = statements(walk.read(m_path))
        rel = walk.rel(repo, m_path)
        for st_start, st in stmts:
            at = lambda off: "%s:%d" % (rel, walk.line_of(t, st_start + off))
            m = CREATE.search(st)
            if m:
                schema, name = qual(m)
                if schema == "public":
                    created.setdefault(name, at(m.start()))
                continue
            m = CREATE_VIEW.search(st)
            if m:
                schema, name = qual(m, 2)
                if schema == "public":
                    head = st[m.end():]
                    head = head[:re.search(r"\bas\b", head, re.I).start()] if re.search(r"\bas\b", head, re.I) else head
                    views[name] = (at(m.start()), bool(m.group(1)))
                    view_ok[name] = bool(INVOKER_ON.search(head)) and not m.group(1)
                continue
            m = ALTER_VIEW_INVOKER.search(st)
            if m:
                schema, name = qual(m)
                if schema == "public" and name in views:
                    view_ok[name] = (m.group(3) or "true").lower() in ("true", "on")
                continue
            m = ALTER_RLS.search(st)
            if m:
                schema, name = qual(m)
                if schema == "public":
                    rls[name] = m.group(3).lower() == "enable"
                continue
            m = POLICY.search(st)
            if m:
                schema, name = qual(m)
                if schema != "public":
                    continue
                cmd = POLICY_CMD.search(st)
                if cmd and cmd.group(1).lower() == "select":
                    continue  # a public-read or members-read SELECT policy is a design choice, not a hole
                for kw in ("using", "with check"):
                    k = re.search(r"\b" + kw + r"\s*\(", st, re.I)
                    if not k:
                        continue
                    expr = _paren(st, k.end() - 1)
                    why = open_policy_reason(expr or "")
                    if why:
                        open_pol.append("%s %s: policy %s%s" % (at(m.start()), name, why, " to authenticated" if re.search(r"\bto\s+authenticated\b", st, re.I) else ""))
                        break
    return created, rls, views, view_ok, open_pol


# ---- browser code ----
PUBLIC_ADMIN = re.compile(r"\b(?:NEXT_PUBLIC_|VITE_|PUBLIC_|EXPO_PUBLIC_)\w*(?:SERVICE|ADMIN|SECRET)\w*")
SERVICE = re.compile(r"service_role|SERVICE_ROLE_KEY|SUPABASE_SERVICE_KEY|sb_secret_", re.I)
# Paths that are browser code whatever the framework. An App Router page.tsx is NOT here:
# it is a Server Component unless it says 'use client'.
CLIENT_PATH = re.compile(r"(?:^|/)(?:components|public|client|frontend|web/src|src/client|src/components)/")
SERVER_PATH = re.compile(r"(?:^|/)(?:server|api|functions|worker|workers|edge|scripts|supabase|netlify)(?:/|$)|\.server\.[cm]?[jt]sx?$|(?:^|/)server\.[cm]?[jt]s$")
USE_CLIENT = re.compile(r"""^\s*['"]use client['"]""")
META_FRAMEWORKS = {"@sveltejs/kit", "astro", "nuxt", "@remix-run/dev", "vinxi", "@tanstack/start", "@tanstack/react-start", "@solidjs/start", "vike", "@analogjs/platform"}
DEFINE_INLINE = re.compile(r"\bdefine\s*:\s*\{[^}]*?(?:SERVICE_ROLE|SERVICE_KEY|sb_secret_)", re.S)


def vite_spa(repo):
    """True when src/ is a browser bundle: Vite present and no meta-framework that keeps server files in src/."""
    deps = {}
    for p in walk.all_package_jsons(repo):
        try:
            deps.update(walk.deps(json.load(open(p, encoding="utf-8"))))
        except (OSError, ValueError):
            pass
    has_vite = "vite" in deps or bool(walk.exists_any(repo, "vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.mts"))
    return has_vite and not (META_FRAMEWORKS & set(deps))


def fly_checks(repo, fly_paths):
    res = []
    for fp in fly_paths:
        rel = walk.rel(repo, fp)
        tag = "" if len(fly_paths) == 1 else "." + re.sub(r"[^A-Za-z0-9]+", "_", os.path.dirname(rel) or "root")
        fly = walk.read(fp)
        env_sec = re.search(r"^\[env\]\s*$(.*?)(?=^\[|\Z)", fly, re.M | re.S)
        bad = []
        if env_sec:
            for m in re.finditer(r"""^\s*([A-Za-z_]\w*)\s*=\s*(?:"([^"\n]*)"|'([^'\n]*)'|([^\n#]*))""", env_sec.group(1), re.M):
                val = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else (m.group(4) or "").strip())
                if secret_name(m.group(1), val):
                    bad.append(m.group(1))
        if bad:
            res.append(result("fly.env-secrets" + tag, "No secrets in fly.toml [env]", "FAIL", "%s [env]: %s" % (rel, ", ".join(bad)), severity="high",
                              fix="`fly secrets set NAME=...` (from the clipboard), delete it from [env], rotate it"))
        else:
            res.append(result("fly.env-secrets" + tag, "No secrets in fly.toml [env]", "PASS", "%s [env]: no secret-looking name" % rel))
        exp = []
        for port in re.finditer(r"^\s*\[\[services\.ports\]\]\s*$(.*?)(?=^\s*\[|\Z)", fly, re.M | re.S):
            blk = port.group(1)
            hm = re.search(r"handlers\s*=\s*\[([^\]]*)\]", blk)
            handlers = [h.lower() for h in re.findall(r"""["']([^"']+)["']""", hm.group(1))] if hm else []
            num = re.search(r"^\s*port\s*=\s*(\d+)", blk, re.M)
            pnum = int(num.group(1)) if num else None
            web = "http" in handlers and not any(NON_WEB_HANDLERS.match(h) for h in handlers)
            if pnum in DB_PORTS:
                exp.append("%s services port %s is a database port (handlers: %s)" % (rel, pnum, ", ".join(handlers) or "none"))
            elif not web:
                exp.append("%s services port %s has no http handler (handlers: %s)" % (rel, pnum if pnum is not None else "?", ", ".join(handlers) or "none"))
        if re.search(r"force_https\s*=\s*false", fly):
            exp.append("%s force_https = false" % rel)
        if exp:
            res.append(result("fly.exposure" + tag, "Only web ports are public, over https", "FAIL", "; ".join(exp), severity="medium",
                              fix="remove raw TCP and database services from public exposure (fly proxy / private networking, .internal addresses) and set force_https = true"))
        else:
            res.append(result("fly.exposure" + tag, "Only web ports are public, over https", "PASS", "%s: public ports use http handlers" % rel))
    return res


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    fly_paths = sorted(walk.files(repo, exts=("fly.toml",)))
    if not fly_paths and os.path.isfile(os.path.join(repo, "fly.toml")):
        fly_paths = [os.path.join(repo, "fly.toml")]
    res += fly_checks(repo, fly_paths)

    migs = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in ("node_modules",) and not d.startswith(".")]  # never .claude/worktrees copies
        if re.search(r"(?:supabase|migrations)", root.replace(repo, "")):
            migs += [os.path.join(root, n) for n in names if n.endswith(".sql")]
    uses_supabase = bool(migs) or os.path.isdir(os.path.join(repo, "supabase")) or any(walk.find(repo, r"@supabase/supabase-js|from supabase import|create_client\(", tests=False))
    if uses_supabase:
        created, rls, views, view_ok, open_pol = replay(repo, migs)
        enabled = {k for k, v in rls.items() if v}
        if not migs:
            res.append(result("supabase.rls", "Row level security on every public table", "UNKNOWN", "no SQL migrations in the repo",
                              reason="RLS lives in the database; with no migrations to read, check the Supabase dashboard (Table Editor, RLS badge)"))
        else:
            missing = [v + " " + k for k, v in created.items() if k not in enabled]
            missing += ["%s %s: %s" % (views[k][0], k, "materialized view (no RLS applies, no security_invoker)" if views[k][1] else "view without security_invoker (runs as its owner, bypasses RLS)")
                        for k in views if not view_ok.get(k)]
            missing += open_pol
            if missing:
                res.append(result("supabase.rls", "Row level security on every public table", "FAIL", ledger.join_hits(missing, 8, "; "), severity="high",
                                  fix="ALTER TABLE <t> ENABLE ROW LEVEL SECURITY plus owner-bound policies (auth.uid() = owner_id), in a new migration; views get `with (security_invoker = true)` or move to a private schema; no write policy using (true) or auth.uid() is not null",
                                  detail="migrations replayed in order: a later DISABLE counts; a public view without security_invoker serves the tables' rows regardless of RLS; a write policy true for every signed-in user is the same hole as using (true)"))
            else:
                res.append(result("supabase.rls", "Row level security on every public table", "PASS", "%d table(s) created, RLS enabled on each, %d view(s) with security_invoker, in %d migration(s)" % (len(created), len(views), len(migs))))
        client_refs = ["%s:%d %s" % (r, ln, m.group(0)) for r, ln, m in walk.find(repo, PUBLIC_ADMIN, exts=walk.CODE_EXT + (".example", ".toml"), tests=False)]
        for f in (".env", ".env.local", ".env.production", ".env.example", ".dev.vars.example"):
            for i, line in enumerate(walk.read(os.path.join(repo, f)).splitlines(), 1):
                m = PUBLIC_ADMIN.search(line.split("=")[0])
                if m:
                    client_refs.append("%s:%d %s" % (f, i, m.group(0)))
        spa = vite_spa(repo)
        for cfg in ("vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.mts"):
            t = walk.read_code(os.path.join(repo, cfg))
            m = DEFINE_INLINE.search(t)
            if m:
                client_refs.append("%s:%d define inlines a service-role variable into the browser bundle" % (cfg, walk.line_of(t, m.end())))

        def is_browser(rel, text):
            if USE_CLIENT.search(text):
                return True
            if SERVER_PATH.search(rel):
                return False
            return bool(CLIENT_PATH.search(rel)) or (spa and rel.startswith("src/"))

        client_files = set()
        for p in walk.files(repo, tests=False):
            r = walk.rel(repo, p)
            if r.endswith(".py"):
                continue  # Python never runs in a browser
            t = walk.read_code(p)
            browser = is_browser(r, t)
            for m in SERVICE.finditer(t):
                line = t[t.rfind("\n", 0, m.start()) + 1: t.find("\n", m.end())]
                if browser or re.search(r"(?:NEXT_PUBLIC_|VITE_|PUBLIC_)\w*SERVICE", line):
                    client_refs.append("%s:%d" % (r, walk.line_of(t, m.start())))
            if browser:
                client_files.add(p)
        # one level of imports from browser code: a shared module holding the service key ships too
        for cf in client_files:
            for imp in re.finditer(r"""(?:from|import)\s*['"](\.{1,2}/[^'"]+)['"]""", walk.read_code(cf)):
                base = os.path.normpath(os.path.join(os.path.dirname(cf), imp.group(1)))
                for ext in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"):
                    if os.path.isfile(base + ext) and SERVICE.search(walk.read_code(base + ext)):
                        client_refs.append("%s (imported by %s)" % (walk.rel(repo, base + ext), walk.rel(repo, cf)))
                        break
        if client_refs:
            res.append(result("supabase.service-role", "Service-role key never in browser code", "FAIL", ledger.join_hits(sorted(set(client_refs)), 6, ", "), severity="critical",
                              fix="use the service-role key only server-side; the browser gets the anon/publishable key; rotate the service key"))
        else:
            res.append(result("supabase.service-role", "Service-role key never in browser code", "PASS", "no service-role reference in client paths, a Vite src/ bundle, a vite define, or public env names"))
    return ledger.emit(res, cannot_see=["Fly secrets actually set: `fly secrets list` (names and digests, no values)",
                                        "Supabase policies' contents and tables created outside migrations: dashboard or `supabase db dump --schema public` read by hand",
                                        "Whether Supabase Auth allows open signups: a policy `to authenticated` is only as narrow as who can sign up (Authentication, Providers)"])


if __name__ == "__main__":
    sys.exit(main())
