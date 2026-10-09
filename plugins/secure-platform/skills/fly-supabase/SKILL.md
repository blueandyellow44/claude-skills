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

Known-bad: a service key in [env], a raw 5432 port, force_https false, a table without RLS, the service-role key in a 'use client' component all FAIL; the RLS evidence names only the table without it. Known-good: all four PASS. Supabase with no migrations is UNKNOWN.

## Rules

1. When the owner rules that this skill should not do something, add that rule here in the same turn.
