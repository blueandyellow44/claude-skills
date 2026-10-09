---
name: outbound-fetch-guard
description: "Stop server-side request forgery: make every fetch of a URL that came from data (feeds, articles, images, webhooks, user links) go to public internet addresses only, checked at URL, DNS, connect and every redirect, with a size cap, and prove it with a local trap server. Use when the user says 'SSRF', 'the server fetches URLs', 'feed ingestion security', 'private network fetch', or when secure-launch reports fetch.request-url or fetch.data-url. Do NOT use it for fixed provider URLs (Stripe, Gemini) or for spend limits (abuse-and-spend)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# outbound-fetch-guard

Reference implementation: a news-scoring app's `src/lib/safeFetch.ts` (2026-10-07), with `safeFetch.test.ts` and `safeFetch.tls.test.ts`. Verified there on all 66 live feeds and 80 articles, unchanged output.

## Trigger

The server fetches a URL it did not write itself. A fixed provider URL (Stripe, Gemini) is not this; a feed list, an article link, a photo URL from data is.

## Inputs

- Every outbound call site: `python3 <base>/../../scripts/check_fetch.py REPO` lists request-supplied URLs (fetch.request-url) and raw data-URL fetches (fetch.data-url); `grep -n "fetch(\|https.get\|axios\|got(" src/` for anything it misses.

## Prerequisites

- Node (Workers have no raw DNS or socket hooks; on Workers, limit to an allow-list of hosts instead and say so).
- `scripts/ssrf_probe.py` for the trap cases.

## Procedure

1. **One fetch function** that every data-URL call goes through; no call site keeps a raw `fetch`.
2. **Checks, all of them:** scheme http/https only; default port only; an IP literal must be public; DNS answers must ALL be public (resolve once, connect to that answer via a custom `lookup`, so a rebinding second answer cannot slip in); every redirect re-checked from the top, with a hop limit; response size capped while streaming, not after.
3. **Public means** the reference block lists: IPv4 0/8, 10/8, 100.64/10, 127/8, 169.254/16 (cloud metadata), 172.16/12, 192.0.0/24, 192.0.2/24, 192.88.99/24, 192.168/16, 198.18/15, 198.51.100/24, 203.0.113/24, 224/4, 240/4; IPv6 only 2000::/3, minus mapped, NAT64, Teredo, 6to4, documentation, ULA, link-local, multicast. Anything unparseable is not public.
4. **Prove it** with `python3 scripts/ssrf_probe.py`: every direct case and every redirect case refused, `/big` cut at the cap. Keep a test policy that allows 127.0.0.1 only for the first hop so redirect cases can be exercised.
5. **Keep behavior:** run the real ingestion on the full live input list before and after and diff the outputs. The reference app found a TLS quirk this way (CNN refused fresh handshakes; shared keep-alive-off agents fixed it).

## Outputs

The guard, its tests, the trap results, and the before/after diff of real ingestion.

## Failure handling

- A real source breaks under the guard: find out why (redirect to a CDN on a private range? TLS session handling?) before loosening anything; never add a blanket allow.
- A dependency upgrade changes fetch internals: load the built code under the real runtime, not only the test runner.

## Verification

`python3 <base>/../../scripts/ssrf_probe.py --self-test`

Then the project's own guard tests (in the reference app, the safeFetch vitest files).

## Rules

1. Never fetch a real internal address to "check" it; the trap server stands in.
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
