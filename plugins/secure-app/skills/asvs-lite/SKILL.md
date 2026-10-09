---
name: asvs-lite
description: "A short OWASP ASVS 5.0 pass for one of your web apps, built from the 2026-10-07 audit of a production map app: automated checks for credentialed wildcard CORS, stack traces in responses, unguarded debug or seed routes, a sign-out that only clears the browser, and object write routes with no ownership reference, then a manual checklist for what a line scan cannot judge (input bounds, session lifetime, OAuth state, ownership proof). Use when the user says 'ASVS', 'app security check', 'is sign-out real', 'can one user edit another's data', or as the app layer of secure-launch. Do NOT use it for the full audit with live repro (launch-security-audit), for spend and proxies (abuse-and-spend), or for headers at the edge (cloudflare-pages-workers)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
---

# asvs-lite

## Trigger

Before a launch or after auth, session or route changes.

## Inputs

- Repo path; the project's decision record (rulings change what counts: if an app browses signed out by ruling, "add sign-in to the map" is never a fix).

## Prerequisites

- secure-core. Read the ASVS 5.0 chapter file before citing a requirement number (github.com/OWASP/ASVS, `5.0/en`).

## Procedure

1. `python3 <base>/../../scripts/check_app.py REPO`.
2. For each FAIL, open the cited file:line and the router. `app.object-writes` sees only the handler and `app.use(prefix, auth)` middleware; a guard applied another way (a wrapper, a sub-app) is a false positive: fix the check, then re-run.
3. Manual checklist, each answered with file:line or "not covered":
   - V2 input bounds: every numeric or list input clamped (counts, lengths, coordinates); free-use counters cannot be reset by the client.
   - V6/V10 sign-in: OAuth `state` checked, return path restricted to the own origin.
   - V7 sessions: cookie flags (HttpOnly, Secure, SameSite), lifetime, server-side end on sign-out (7.4.1).
   - V8 authorization: ownership on EVERY object route, read and write; prove each with `mutation-proven-tests`. A PASS from `app.object-writes` is a reference, not a proof.
   - V13 configuration: no debug routes, no verbose errors, secrets only in secret stores.
   - V16 errors: stack server-side only.
4. Report confirmed (reproduced or proven by mutation) apart from hypotheses.

## Outputs

The five automated results and the checklist answers with evidence.

## Failure handling

- Unknown router style: handlers come back empty and object-writes PASSes vacuously (its evidence says "0 object write route(s)"). Treat 0 as "not mapped" and list routes by hand.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad (shaped like the map app before its repair): reflected origin with credentials, `err.stack` in onError, `/api/debug/env`, a cookie-only sign-out, and an unowned `DELETE /api/walks/:id` all FAIL. Known-good: an origin list, a generic error, a revoked-session insert on sign-out and an owner check all PASS; auth middleware over `/api/*` counts as a guard.

## Rules

1. A line-scan PASS is never reported as "ownership holds".
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
