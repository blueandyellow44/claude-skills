---
name: cloudflare-pages-workers
description: "The Cloudflare Pages and Workers adapter of secure-launch (formerly edge-hardening): check from the repo that framing, HSTS, nosniff and Referrer-Policy reach every path, that no secret sits in wrangler [vars], and that a preview environment does not write production data; then harden at the edge without breaking it: framing (CSP frame-ancestors) after finding every page of yours that embeds the site, HSTS, server-side session revocation on sign-out, an in-code per-client rate limit that keeps the privacy page true, a zone rate-limit rule through the dashboard, and a burst test against a cached URL. Use when the user says 'security headers', 'clickjacking', 'HSTS', 'rate limit', 'sign-out does not sign out', 'harden the site', or as a repair step of launch-security-audit. Do NOT use it for app-layer checks (asvs-lite) or for a Next.js app's own config (nextjs-opennext)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# cloudflare-pages-workers

Built on a production map app, 2026-10-07 (one deployment, three commits, and a zone rule limiting geo lookups per IP).

## Trigger

An audit found missing headers, a sign-out that only clears the browser, or an unthrottled endpoint that reaches someone else's server.

## Inputs

- Hosts, including `*.pages.dev` aliases (zone rules do not cover them; code does).
- The privacy page's promises (what is stored about signed-out visitors).
- Your other sites, to search for embeds.

## Prerequisites

- `scripts/probe_headers.sh`, `scripts/find_embedders.sh` and `scripts/check_cloudflare.py` (this plugin), and secure-core.
- The owner's word for any zone setting (a standing change). The Cloudflare MCP connector and wrangler login were zone-read-only on 2026-10-07; a zone rule then goes in through the dashboard in the owner's logged-in browser (one tab, closed after).

## Procedure

0. **Check the repo:** `python3 <base>/../../scripts/check_cloudflare.py REPO` (cf.headers.*, cf.vars-secrets, cf.env-bindings, plus what it cannot see: zone rules, Access, live secrets, the alias).
1. **Probe:** `bash <base>/../../scripts/probe_headers.sh https://host/ https://alias.pages.dev/` (or `secure_launch.py --url`). Note: `.app`, `.dev`, `.page` are HSTS-preloaded, so zone HSTS and Always Use HTTPS add nothing there if http already 301s.
2. **Framing.** `scripts/find_embedders.sh <host> ~/<each site repo>`. Write ONE `/*` block in `public/_headers` (Cloudflare concatenates matching blocks per header): `Content-Security-Policy: frame-ancestors 'self' <each embedder origin, www too> http://127.0.0.1:* http://localhost:*` and `Strict-Transport-Security: max-age=31536000` (no includeSubDomains, no preload: reversible). A file shared by several Pages projects must allow every project's embedders (in one case a walking-tour app was framed on a portfolio site's demos page). Check on a local build in a real browser: framed from 127.0.0.1 renders; framed from `[::1]` is blocked.
3. **Sign-out that signs out (signed-cookie sessions).** Table `revoked_sessions(hash PRIMARY KEY, expires_at)`; sign-out drops the browser cookie FIRST, then inserts the SHA-256 of the exact cookie with the session's expiry and prunes expired rows; the session reader refuses a listed cookie and fails CLOSED if the list cannot be read. Keyed by the cookie, so cookies issued before the change are covered and nobody is signed out by the deploy. Migration before code.
4. **Per-client ceiling in code.** Count only the calls about to leave for an outside server (cache misses), keyed by signed-in account else the connecting IP, in isolate memory (never written: a DB counter of IPs would break "nothing about you is stored"). Generous (60 a minute): a venue shares one IP. Answer 429 in the shape the client already handles (in the map app, `throttled: true` shows "busy").
5. **Zone rule as a global backstop** (on the owner's word): Free plan allows one: path in the outside-call endpoints, 100 requests per 10 s per IP, block 10 s. Check the dashboard's 30-day match count first (99 on the map app). Read it back through the API.
6. **Burst test, harmless:** one identical CACHED URL, 120 requests, 30 in parallel; expect about 100 x 200 then 429, and 200 again after the block. Never a burst of distinct URLs (each would go upstream).

## Outputs

Headers before and after on every host; the embedders kept working; the revocation tests (copy refused after sign-out, other sessions unaffected, forged cookie not recorded, fails closed); the limiter tests; the zone rule as read back; the burst counts.

## Failure handling

- Zone write refused by the API: dashboard on the owner's word, or leave the code limit as the only one and say the pages.dev alias is the gap either way.
- An existing bulk test trips the new limiter: reset the limiter in that test, explain why in a comment.
- A deploy of the revocation without the migration: every signed-in request reads as signed out; roll back from the dashboard, apply, redeploy.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: headers only on `/api/*`, a secret in [vars], a preview reusing the production D1 id all FAIL, and a live page without headers FAILs per header. Known-good: a `/*` block with all four, hono `secureHeaders()`, separate preview ids PASS; a URL that does not answer is UNKNOWN. Embed search finds an iframe and skips node_modules.

## Rules

1. Zone settings, dashboard rules and deploys only on the owner's word naming them.
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
