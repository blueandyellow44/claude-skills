---
name: auth-gate-check
description: "Find auth gates that open on their own in one of your Workers or apps: a guard that skips itself when an env secret is missing (`if (!env.X) return next()`, `enabled: !!env.X`, a verification that only runs `if (env.X)`), an identity taken from a request header (cf-access-authenticated-user-email, x-teacher-id, x-user-*) with no JWT verification in the tree, a Worker on a custom domain or route that trusts Cloudflare Access at the edge and never verifies the Cf-Access-Jwt-Assertion itself, and better-auth email sign-up with no disableSignUp and no create hook. Use when the user says 'auth is off', 'fail closed', 'Access JWT', 'open sign-up', 'anyone can sign up', 'header identity', or when secure-launch reports auth.*. Do NOT use it for ownership checks on object writes (asvs-lite) or for secret values (secret-scan)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
---

# auth-gate-check

Built from the 2026-10-13 account audit and the same-day fixes: a ledger app whose session guard read `if (!c.env.BETTER_AUTH_SECRET) return next()` had been open to anyone since the secret was removed "for now" three months earlier; a CRM worker took email-and-password sign-up from anyone; a coaching app trusted the Access policy at the edge and verified nothing in the Worker; two Workers read `cf-access-authenticated-user-email` and compared it to an allow-list, which any request that bypassed the edge could forge. Each fix is the known-good fixture here.

## Trigger

A Worker or app has a session guard, an Access policy in front of it, an identity header, or better-auth; or an audit asks "what happens when the secret is unset".

## Inputs

- Repo path.
- The project's rulings on public surfaces (a demo that is public by design is a FAIL to accept in `security/accepted.json`, not to fix).

## Prerequisites

- secure-core.

## Procedure

1. `python3 <base>/../../scripts/check_auth_gates.py REPO`.
2. `auth.off-switch` FAIL: make the missing secret a 503 (`return c.json({ error: 'auth not configured' }, 503)`); the only bypass allowed is an explicit test environment the test runner sets (`NODE_ENV === 'test'`), never an unset secret. Then set the secret on the deployed Worker (`wrangler secret put NAME`, value from the clipboard, never typed into a transcript) and teach any sync script to send credentials.
3. `auth.header-identity` FAIL: verify `Cf-Access-Jwt-Assertion` with jose against `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`, with `issuer` (the team domain), `audience` (the Access application's AUD tag, read from the Access login redirect for that hostname), `algorithms: ['RS256']`, and read the email from the claim; compare it to the allow-list. Drop the bare header read.
4. `auth.access-jwt` UNKNOWN: this check cannot see the Zero Trust dashboard. Either add the in-Worker verification from step 3 (the only state the suite can prove), or record an acceptance with the reason the host is public by design. Never mark it PASS by hand.
5. `auth.open-signup` FAIL: `emailAndPassword: { enabled: true, disableSignUp: true }` plus a `databaseHooks.user.create.before` hook that throws for any email not on the allow-list (belt and suspenders: the hook also covers OAuth and magic-link paths added later). Set `NODE_ENV=production` in `[vars]` so better-auth's `baseURL` resolves to the real host.
6. Prove each with `mutation-proven-tests`: delete the 503 branch (the test must fail), send a forged header (401 expected), POST a sign-up for a stranger (403 expected).

## Outputs

Per check: the lines, the verdict, and for UNKNOWN the dashboard look that would close it (the Access application list, Zero Trust > Access > Applications).

## Failure handling

- The guard is gated on `NODE_ENV === 'test'` only: that is the allowed bypass; the check does not flag it. Confirm the deployed `[vars]` never set NODE_ENV to test.
- A Worker that reads the Access header AND verifies the JWT elsewhere: PASS with a "reference, not a proof" detail; confirm by hand the verification runs on every data route.
- `asvs-lite` also reports `app.header-identity` for `X-*-Id` headers in route handlers; this check widens it to the Access email header and to any file in the tree.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: `if (!c.env.BETTER_AUTH_SECRET) return next()`, the same with the secret destructured first (`const { ADMIN_TOKEN } = c.env; if (!ADMIN_TOKEN) return next()`), `enabled: !!env.TURNSTILE_SECRET_KEY`, `if (env.STRIPE_WEBHOOK_SECRET) { verify }`, a bare `cf-access-authenticated-user-email` read, an `x-teacher-id` read, an `x-forwarded-email` or `Remote-User` read (the auth-proxy family), a routed Worker with no assertion reference (UNKNOWN), an assertion read with no jwtVerify, `decodeJwt` with iss and aud compared by hand (no signature check), jose imported but never called, jwtVerify without issuer and audience in its options, better-auth email sign-up with neither `disableSignUp` nor a create hook, the same with a nested `password: { hash, verify }` option written before `enabled: true`, and a Worker-level sign-up refusal whose helper returns true when its secret is unset all FAIL (or are UNKNOWN as stated). Known-good: a 503 on a missing secret, a skipped analytics beacon (`if (!env.ANALYTICS_TOKEN) return next()`, nothing auth-shaped around it), jwtVerify with issuer and audience in its options or in an options const, `disableSignUp: true` with a `user.create.before` hook, a `user.create.before` hook built in an imported file (`databaseHooks: inviteOnlyHooks(env)`), and a Worker entry that refuses every `/api/auth/sign-up*` request with 403 and fails closed all PASS (bench 2026-11-01).

## Rules

1. A missing secret is never an open door; the fix is 503, not "set the secret and move on".
2. A FAIL on a surface the owner ruled public is accepted with the ruling's date, never silently fixed.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
