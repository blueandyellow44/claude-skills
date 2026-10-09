#!/usr/bin/env python3
"""check_fly_supabase.py - Fly.io and Supabase adapter.

  check_fly_supabase.py REPO

  fly.env-secrets        a secret-looking name in fly.toml [env] FAILs high
                         ([env] is plaintext and committed; use fly secrets).
  fly.exposure           a public service on a raw TCP port (no http/tls
                         handler) FAILs medium; force_https = false FAILs low.
  supabase.rls           every table a migration creates in the public schema
                         has ENABLE ROW LEVEL SECURITY in some migration; a
                         missing one FAILs high. No migrations: UNKNOWN.
  supabase.service-role  the service-role key referenced from browser code
                         ('use client', NEXT_PUBLIC_/VITE_, components/,
                         public/, src/client) FAILs critical.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _corepath  # noqa: F401,E402
import ledger  # noqa: E402
import walk  # noqa: E402
from ledger import result  # noqa: E402

SECRETISH = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSCODE|PRIVATE|CREDENTIAL|DSN|DATABASE_URL", re.I)
CREATE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?((?:\"?public\"?\.)?\"?[A-Za-z_][\w]*\"?)(?!\s*\.)", re.I)
DISABLE = re.compile(r"alter\s+table\s+(?:only\s+)?(?:if\s+exists\s+)?((?:\"?public\"?\.)?\"?[A-Za-z_][\w]*\"?)\s+disable\s+row\s+level\s+security", re.I)
# A policy whose condition is always true, on anything but SELECT (no FOR clause means ALL).
OPEN_POLICY = re.compile(r"create\s+policy\s+[^;]*?\bon\s+((?:\"?public\"?\.)?\"?[A-Za-z_][\w]*\"?)(?![^;]*\bfor\s+select\b)([^;]*?)(?:using|with\s+check)\s*\(\s*(?:true|\(\s*true\s*\)|1\s*=\s*1|true\s+is\s+true|'t'|'true')\s*\)", re.I | re.S)
PUBLIC_ADMIN = re.compile(r"\b(?:NEXT_PUBLIC_|VITE_|PUBLIC_|EXPO_PUBLIC_)\w*(?:SERVICE|ADMIN|SECRET)\w*")
ENABLE = re.compile(r"alter\s+table\s+(?:only\s+)?(?:if\s+exists\s+)?((?:\"?public\"?\.)?\"?[A-Za-z_][\w]*\"?)\s+enable\s+row\s+level\s+security", re.I)
SERVICE = re.compile(r"service_role|SERVICE_ROLE_KEY|SUPABASE_SERVICE_KEY|sb_secret_", re.I)
CLIENT_PATH = re.compile(r"(?:^|/)(?:components|public|client|frontend|web/src|src/client|src/components)/|(?:^|/)app/.*page\.(?:tsx|jsx)$")


def norm(name):
    n = name.replace('"', "").lower()
    return n.split(".", 1)[1] if n.startswith("public.") else n


def main():
    repo = os.path.abspath(sys.argv[1])
    res = []
    fly = walk.read_code(os.path.join(repo, "fly.toml"))
    if fly:
        env_sec = re.search(r"^\[env\]\s*$(.*?)(?=^\[|\Z)", fly, re.M | re.S)
        bad = [m.group(1) for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=", env_sec.group(1), re.M)] if env_sec else []
        bad = [b for b in bad if SECRETISH.search(b)]
        if bad:
            res.append(result("fly.env-secrets", "No secrets in fly.toml [env]", "FAIL", "fly.toml [env]: %s" % ", ".join(bad), severity="high",
                              fix="`fly secrets set NAME=...` (from the clipboard), delete it from [env], rotate it"))
        else:
            res.append(result("fly.env-secrets", "No secrets in fly.toml [env]", "PASS", "fly.toml [env]: no secret-looking name"))
        exp = []
        for blk in re.findall(r"^\[\[services\]\](.*?)(?=^\[\[services\]\]|^\[(?!\[services\.ports\])|\Z)", fly, re.M | re.S):
            for port in re.findall(r"\[\[services\.ports\]\](.*?)(?=\[\[services\.ports\]\]|\Z)", blk, re.S):
                handlers = re.search(r"handlers\s*=\s*\[([^\]]*)\]", port)
                num = re.search(r"port\s*=\s*(\d+)", port)
                if not handlers or not re.search(r"http|tls", handlers.group(1)):
                    exp.append("fly.toml services port %s with no http/tls handler" % (num.group(1) if num else "?"))
        if re.search(r"force_https\s*=\s*false", fly):
            exp.append("fly.toml force_https = false")
        if exp:
            res.append(result("fly.exposure", "Only web ports are public, over https", "FAIL", "; ".join(exp), severity="medium",
                              fix="remove raw TCP services from public exposure (use fly proxy / private networking) and set force_https = true"))
        else:
            res.append(result("fly.exposure", "Only web ports are public, over https", "PASS", "fly.toml: public ports use http/tls handlers"))

    migs = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in ("node_modules",) and not d.startswith(".")]  # never .claude/worktrees copies
        if re.search(r"(?:supabase|migrations)", root.replace(repo, "")):
            migs += [os.path.join(root, n) for n in names if n.endswith(".sql")]
    uses_supabase = bool(migs) or os.path.isdir(os.path.join(repo, "supabase")) or any(walk.find(repo, r"@supabase/supabase-js|from supabase import|create_client\(", tests=False))
    if uses_supabase:
        # Replay migrations in order: the last word on each table counts (enable then a later disable is OFF).
        created, rls, open_pol = {}, {}, []
        for m_path in sorted(migs):
            t = re.sub(r"--[^\n]*", "", walk.read(m_path))  # SQL comments never enable anything
            t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
            events = []
            for m in CREATE.finditer(t):
                nm = m.group(1)
                if "." in nm.replace('"', "") and not nm.replace('"', "").lower().startswith("public."):
                    continue
                created.setdefault(norm(nm), "%s:%d" % (walk.rel(repo, m_path), walk.line_of(t, m.start())))
            events += [(m.start(), norm(m.group(1)), True) for m in ENABLE.finditer(t)]
            events += [(m.start(), norm(m.group(1)), False) for m in DISABLE.finditer(t)]
            for _, tbl, on in sorted(events):
                rls[tbl] = on
            open_pol += ["%s:%d %s: policy always true%s" % (walk.rel(repo, m_path), walk.line_of(t, m.start()), norm(m.group(1)),
                                                              " to authenticated" if "authenticated" in m.group(0).lower() else "") for m in OPEN_POLICY.finditer(t)]
        enabled = {k for k, v in rls.items() if v}
        if not migs:
            res.append(result("supabase.rls", "Row level security on every public table", "UNKNOWN", "no SQL migrations in the repo",
                              reason="RLS lives in the database; with no migrations to read, check the Supabase dashboard (Table Editor, RLS badge)"))
        else:
            missing = [v + " " + k for k, v in created.items() if k not in enabled] + open_pol
            if missing:
                res.append(result("supabase.rls", "Row level security on every public table", "FAIL", ledger.join_hits(missing, 8, "; "), severity="high",
                                  fix="ALTER TABLE <t> ENABLE ROW LEVEL SECURITY plus explicit policies, in a new migration; no write policy using (true)",
                                  detail="migrations replayed in order: a later DISABLE counts; a write policy using (true) opens the table"))
            else:
                res.append(result("supabase.rls", "Row level security on every public table", "PASS", "%d table(s) created, RLS enabled on each in %d migration(s)" % (len(created), len(migs))))
        client_refs = ["%s:%d %s" % (r, ln, m.group(0)) for r, ln, m in walk.find(repo, PUBLIC_ADMIN, exts=walk.CODE_EXT + (".example", ".toml"), tests=False)]
        for f in (".env", ".env.local", ".env.production", ".env.example", ".dev.vars.example"):
            for i, line in enumerate(walk.read(os.path.join(repo, f)).splitlines(), 1):
                m = PUBLIC_ADMIN.search(line.split("=")[0])
                if m:
                    client_refs.append("%s:%d %s" % (f, i, m.group(0)))
        client_files = set()
        for p in walk.files(repo, tests=False):
            r = walk.rel(repo, p)
            if r.endswith(".py"):
                continue  # Python never runs in a browser
            t = walk.read_code(p)
            for m in SERVICE.finditer(t):
                line = t[t.rfind("\n", 0, m.start()) + 1: t.find("\n", m.end())]
                if CLIENT_PATH.search(r) or re.search(r"""^\s*['"]use client['"]""", t) or re.search(r"(?:NEXT_PUBLIC_|VITE_|PUBLIC_)\w*SERVICE", line):
                    client_refs.append("%s:%d" % (r, walk.line_of(t, m.start())))
            if CLIENT_PATH.search(r) or re.search(r"""^\s*['"]use client['"]""", t):
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
            res.append(result("supabase.service-role", "Service-role key never in browser code", "FAIL", ledger.join_hits(client_refs, 6, ", "), severity="critical",
                              fix="use the service-role key only server-side; the browser gets the anon/publishable key; rotate the service key"))
        else:
            res.append(result("supabase.service-role", "Service-role key never in browser code", "PASS", "no service-role reference in client paths or public env names"))
    return ledger.emit(res, cannot_see=["Fly secrets actually set: `fly secrets list` (names and digests, no values)",
                                        "Supabase policies' contents and tables created outside migrations: dashboard or `supabase db dump --schema public` read by hand",
                                        "Whether Supabase Auth allows open signups: a policy `to authenticated` is only as narrow as who can sign up (Authentication, Providers)"])


if __name__ == "__main__":
    sys.exit(main())
