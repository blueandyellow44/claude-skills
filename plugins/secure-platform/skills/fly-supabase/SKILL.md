---
name: fly-supabase
description: "Fly.io and Supabase adapter of secure-launch: no secret in fly.toml [env], only web ports public and over https, row level security enabled on every public table a migration creates, and the service-role key never referenced from browser code. States what it cannot see: secrets actually set on Fly, and policies or tables made outside migrations. Use when the user says 'check RLS', 'is the service key exposed', 'Fly security', or when secure-launch detects fly or supabase. Do NOT use it to write policies (propose them) or for Cloudflare (cloudflare-pages-workers)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# fly-supabase

## Trigger

A repo with `fly.toml`, a `supabase/` folder, migrations, or `@supabase/supabase-js`.

## Inputs

- Repo path. Migrations may live in `supabase/migrations/` or elsewhere (for example `infra/supabase/migrations/`); the check finds `.sql` under any path containing supabase or migrations.

## Prerequisites

- secure-core. Never `fly secrets list` piped anywhere that prints values (it prints names and digests only, which is fine).

## Procedure

1. `python3 <base>/../../scripts/check_fly_supabase.py REPO`.
2. `supabase.rls` FAIL: list each table; propose `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` plus the policies the app needs, as a new migration applied the project's way (for example `supabase db query --linked`), on the owner's word.
3. `supabase.service-role` FAIL: rotate the key (`secret-rotation`) before anything else.
4. `fly.exposure` FAIL: confirm with `fly ips list` and `fly services list` (read-only) before proposing changes.

## Outputs

The four results, plus the read-only Fly confirmations.

## Failure handling

- No migrations: `supabase.rls` is UNKNOWN; read the dashboard's RLS badges.
- RLS enabled with an allow-all policy: the check cannot see policy contents; read them.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a service key in [env], a raw 5432 port, force_https false, a table without RLS, the service-role key in a 'use client' component all FAIL; the RLS evidence names only the table without it. Known-good: all four PASS. Supabase with no migrations is UNKNOWN. Phase 8 regressions (each a former benchmark miss): a public 5432 with the `pg_tls` handler and a tls-only handler FAIL while 80 http and 443 tls+http PASS; `SUPABASE_ANON_KEY`, `TOKEN_ISSUER`, `PRIVATE_KEY_PATH`, `SESSION_TOKEN_TTL_SECONDS`, `TURNSTILE_SITE_KEY` and `KEYBOARD_LAYOUT` in [env] PASS while `SUPABASE_SERVICE_KEY`, `DATABASE_URL`, `JWT_SECRET` and a key-shaped value under an innocent name FAIL with every name listed and no value printed; a fly.toml under services/api/ is read (two files get folder-tagged ids); a public view without `security_invoker` and a materialized view FAIL, `with (security_invoker = true)` or a later `alter view ... set (security_invoker = on)` PASS; write policies `auth.uid() is not null`, `auth.role() = 'authenticated'` and `(select auth.uid()) is not null` FAIL while `auth.uid() = author_id` and a signed-in-only SELECT PASS; `private.audit_log` is not a public table; a define-inlined service key read from src/ of a Vite SPA FAILs naming both the define and the file, any src/ file of a Vite SPA is browser code, SvelteKit server files in src/ are not; an App Router page.tsx without 'use client' PASSes and the same page with it FAILs.

## Rules

1. When the owner rules that this skill should not do something, add that rule here in the same turn.
