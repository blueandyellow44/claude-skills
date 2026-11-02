---
name: cloudflare-account
description: "Audit a Cloudflare ACCOUNT, not a repo: read every zone's SSL mode (Full strict), minimum TLS, Always Use HTTPS, HSTS and DNSSEC through the API, find CNAMEs pointing at Pages projects that no longer exist, account members without two-factor, Pages previews carrying production secrets, KV namespaces nothing binds, and Workers reachable only on workers.dev while holding D1, KV, R2 or secrets. Reads with a token from CLOUDFLARE_API_TOKEN (never printed) or judges a saved snapshot offline. Use when the user says 'audit my Cloudflare account', 'zone settings', 'dangling CNAME', 'subdomain takeover', '2FA', 'preview secrets', 'orphan KV', 'workers.dev exposed', or when the repo adapter's cannot-see list points here. Do NOT use it for a repo's own headers and wrangler config (cloudflare-pages-workers) or for Access JWT verification in code (auth-gate-check)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# cloudflare-account

Built from the 2026-10-13 read-only audit of a 20-zone account (findings Z-1 to Z-6): every zone on the account defaults (SSL Full, TLS 1.0, Always Use HTTPS off, HSTS off, DNSSEC off), one proxied CNAME at a Pages project that had been deleted, the one member with two-factor off per the API, a Pages preview environment carrying the production Stripe, Gemini and OAuth secrets, five `*_preview` KV namespaces bound by nothing, and data-holding Workers served only on workers.dev where no zone rule or Access policy can reach them. The repo adapter (`cloudflare-pages-workers`) lists all of these under "cannot see"; this skill sees them.

## Trigger

A launch, a new zone, a deleted Pages project, a new member, or the repo adapter's cannot-see list.

## Inputs

- A read-only API token in `CLOUDFLARE_API_TOKEN`: Zone Read, Zone Settings Read, DNS Read, Workers Routes Read, Cloudflare Pages Read, Account Settings Read, Workers KV Storage Read, Workers Scripts Read. Create it at dash.cloudflare.com/profile/api-tokens in the owner's own browser and move it with `secret-handling` (never typed into a transcript).
- Or a snapshot written by an earlier `fetch` run (`--snapshot account.json`), which is what the tests use.

## Prerequisites

- secure-core.
- The owner's word before any setting changes: every fix below is a dashboard change and a standing one.

## Procedure

1. Fetch: `python3 <base>/../../scripts/check_cloudflare_account.py fetch --out /tmp/account.json`. It prints which calls were unauthorized and the exact permission each needs; add the permission to the token and fetch again rather than reading around the gap. Only GETs are issued.
2. Judge: `python3 <base>/../../scripts/check_cloudflare_account.py --snapshot /tmp/account.json`. Every check a call could not feed is UNKNOWN naming the permission; never fold one into PASS.
3. `cfacct.ssl.*`, `cfacct.tls.*`, `cfacct.https.*`: SSL/TLS > Overview > Full (strict) (safe when every origin is Pages or Workers); Edge Certificates > Minimum TLS 1.2 and Always Use HTTPS on. Twenty zones is twenty dashboard visits or one API loop with a Zone Settings Edit token on the owner's word.
4. `cfacct.hsts.*`: enable at the zone only on zones whose every host answers https (6 months, no preload, includeSubDomains only if every subdomain is https). Enabled with max-age 0 is HSTS switched off and FAILs. An empty zone is PASS with an info detail, not a finding.
5. `cfacct.dnssec.*`: enable, then add the DS record at the registrar; a zone whose registrar is Cloudflare takes the DS automatically.
6. `cfacct.dangling-cname` FAIL: delete the record or repoint it the same day; the project name in the target is one `wrangler pages project create` away from anyone.
7. `cfacct.members-2fa` FAIL: the member turns it on at dash.cloudflare.com/profile; then enforce at Manage Account > Members. The dashboard is ground truth if it disagrees with the API field. UNKNOWN: a pending invitee carries no 2FA field until they accept; re-run after acceptance.
8. `cfacct.pages-preview-secrets` FAIL: give the preview environment test keys or no key; if a ruling says previews share production on purpose (a "deploy to test" flow), accept it in `security/accepted.json` with the date.
9. `cfacct.kv-orphans` (FAIL info): a delete list for the owner; `wrangler dev` leaves `*_preview` twins behind.
10. `cfacct.workers-dev-exposed` FAIL: `workers_dev = false` in that Worker's wrangler config and a zone route or custom domain, or delete a stale Worker; `auth-gate-check` on the Worker's repo covers the in-code side.

## Outputs

The snapshot file (no secret values in it: the API never returns them), the ledger, the list of unauthorized calls with their permission names, and the dashboard changes proposed for the owner.

## Failure handling

- 9109 or 10000 on a call: UNKNOWN with the permission name; the fetch exit code is 3 so a wrapper cannot read it as clean.
- A zone with no DNS records: HSTS is PASS with an info detail; the zone is still judged on SSL, TLS, HTTPS and DNSSEC because those are set at the zone.
- A Worker whose subdomain or settings call failed: counted as "partially read" in the detail, never silently PASS.
- The members endpoint on a user token may also need the user's Memberships Read; the reason names Account Settings Read, which is the account-token name.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad snapshot: `ssl = full`, `min_tls_version = 1.0`, `always_use_https = off`, HSTS disabled on a zone with records, DNSSEC disabled, a CNAME at a deleted Pages project, a member with two-factor false, a preview env carrying a production secret_text, an unbound KV namespace, a workers.dev-only Worker with a D1 binding, and one 9109 error all produce FAIL (or UNKNOWN naming the permission). Known-good snapshot: every zone strict / 1.2 / on / HSTS on / active, matching CNAMEs, 2FA on, previews with no shared secret, every namespace bound, every data Worker routed: all PASS; an empty zone's HSTS is PASS with an info detail. Fetch mode is proven against a local mock of the API: it writes the snapshot, follows pagination, and names the unauthorized call. Phase 8 regressions: a member whose response has no `two_factor_authentication_enabled` field (a pending invitation) makes `cfacct.members-2fa` UNKNOWN naming the member, never PASS, and a member with the field false still FAILs beside a pending one; a Hyperdrive binding counts as data for `cfacct.workers-dev-exposed`; HSTS `enabled` with `max_age` 0 FAILs while the known-good 15552000 PASSes.

## Rules

1. Read-only: this skill issues GETs only; every change is the owner's, in the dashboard, on his word.
2. The token value is never printed, logged, or written to the snapshot.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
