---
name: nextjs-opennext
description: "Next.js (16, on Cloudflare via OpenNext) adapter of secure-launch: every exported server action calls a session check (each is a public POST endpoint), no secret travels in a NEXT_PUBLIC_ variable, and a static export does not rely on next.config headers() (ignored there). States what it cannot see: middleware matcher semantics and the deployed Worker's secrets. Use when the user says 'check the Next app', 'server actions security', 'NEXT_PUBLIC leak', or when secure-launch detects next. Do NOT use it for Cloudflare edge headers (cloudflare-pages-workers) or generic app checks (asvs-lite)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# nextjs-opennext

## Trigger

A repo with a `next` dependency, before a launch or after server actions or env changes.

## Inputs

- Repo path.

## Prerequisites

- secure-core.

## Procedure

1. `python3 <base>/../../scripts/check_nextjs.py REPO`.
2. `next.server-actions` FAIL: open each action. A check in a helper the action calls first is fine (then the check is a false positive: widen the auth vocabulary in `secure-core/lib/surface.py` AUTH_RX and add a test).
3. `next.public-env-secrets` FAIL: the value has shipped to every browser that loaded the site. Rotate first (`secret-rotation`), then rename.
4. `next.static-export-headers` FAIL: move the headers to `public/_headers`; re-probe the live site.
5. Read `middleware.ts` matchers by hand for any path the inventory marked `none found`.

## Outputs

The three results and the matcher review.

## Failure handling

- Monorepo: run on the Next app's folder.
- Pages router: server actions do not exist there; the check emits nothing for them.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: an unguarded `'use server'` delete, `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY`, and a static export with only headers() all FAIL. Known-good: an action that calls `requireUser()` with an owner filter, an anon key, and a static export with `public/_headers` PASS.

## Rules

1. When the owner rules that this skill should not do something, add that rule here in the same turn.
