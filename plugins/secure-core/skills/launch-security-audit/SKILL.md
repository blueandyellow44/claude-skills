---
name: launch-security-audit
description: "Security audit of a web app before or after launch, mapped to OWASP ASVS: bounded plan, attack-surface map (public endpoints, sign-in, ownership checks, payments, spending limits, uploads, secrets, outside calls), inventory of the tests and automation that actually run, read-only production probes, local reproduction with synthetic accounts and mocked paid services, and a report that keeps confirmed findings apart from hypotheses and untested areas. Use when the user says 'security audit', 'audit X for security', 'is X safe to launch', 'pen test', 'ASVS', or hands a security-audit brief. The deep manual pass of the secure-launch suite; it runs secure-launch for the automated checks and adds live repro. Do NOT use it for a quick pre-deploy check (secure-launch alone)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
  - Edit
  - Write
---

# launch-security-audit

Proven twice on 2026-10-07: a map app (Hono on Cloudflare Pages, D1, Stripe, Google sign-in) and a news-scoring app (Node ingestion, GitHub Actions publishing). Both runs found the same shape of problem: protections that existed but that nothing would notice disappearing.

## Trigger

The user asks for a security audit, a launch-safety check, an ASVS pass, or a break test of a site they own. Not for someone else's site.

## Inputs

- The repo path and the live hosts (production, preview, any `*.pages.dev` alias).
- The project's decision record: its docs, decision notes, and `git log` of files to be touched. Rulings change what counts as a finding (in the map app, signed-out browsing is ruled, so "add sign-in to the map routes" is never a fix; its gift-mode sibling runs paid work signed out by ruling).
- Any earlier audit's claims. Treat each as a claim about a moment, not a fact now.

## Prerequisites

- Ground rules stated before the first tool call: no push, no deploy, no real charges, no real user data, no disruptive production tests, unless the owner names the action.
- `gitleaks` (`brew install gitleaks`) for the secret scan; `npm audit` or the stack's equivalent.
- The harness tracker open, one item per step.

## Procedure

1. **Plan, bounded.** One tracker item per step below. Say what is out of scope (dashboard settings, other sites) up front.
2. **Map the attack surface from the code, not from docs.** List every route (`grep` the router for `get|post|put|delete|use`). For each: who may call it (anonymous, signed-in, owner only, webhook signature), what it spends (paid API through which gate), what it stores, what it fetches from outside. Map each to the ASVS 5.0 chapters (checked against github.com/OWASP/ASVS `5.0/en`, 2026-10-07): V1 encoding and sanitization, V2 validation and business logic (spending caps, free-use counts), V3 web frontend security (headers, framing), V4 API and web service, V5 file handling (uploads), V6 authentication, V7 session management (7.4.1: sign-out must stop the session working), V8 authorization (ownership), V9 self-contained tokens (signed cookies), V10 OAuth and OIDC (state, return path), V11 cryptography, V12 secure communication, V13 configuration (secrets), V14 data protection, V15 secure coding and architecture (dependencies), V16 security logging and error handling. Read the chapter file for exact requirement numbers before citing one.
3. **Inventory what actually runs.** For every test file, find the command, CI job or deploy step that runs it. A test file no command runs is a finding (in the map app, `proxyBounds.test.ts` and `signinReturn.test.ts` existed and ran nowhere). Read the deploy scripts: do they run tests? (Neither of the map app's scripts did.)
4. **Resolve old claims against live state, read-only.** One GET per claim, never a burst: out-of-area or oversized inputs to the proxies, debug pages, `/api/me` signed out. Name the host each check hit. Use the secure-platform plugin's `scripts/probe_headers.sh` (or `secure_launch.py --url`) for headers and the http-to-https redirect.
5. **Automated checks:** run the `secure-launch` skill with `--out` outside the repo; it covers the `secret-scan` and `dependency-audit` skills, the platform adapters and the app-layer checks. Every UNKNOWN it reports is carried into this audit's "not covered" list unless you run it by hand.
6. **Reproduce each suspicion locally.** In-process against the real handler with fakes for the database and storage, synthetic accounts (signed cookies made with a test secret), every paid provider mocked and counted. Write each repro to assert the SAFE behavior, so it fails now and passes after the fix. Keep repros in the scratchpad until a fix lands.
7. **Prove the controls that held.** Run the `mutation-proven-tests` skill on each control you report as holding. "It held" without a test that fails when it is removed is a hypothesis.
8. **Report in chat** (format under Outputs). Then propose the next bounded repair scope, one change per finding, with deploy order (migrations before code).

## Outputs

In chat, in this order: answers to the brief's open questions; confirmed findings (each with affected code `file:line`, impact, reproduction, remediation, ASVS chapter); controls that held, with their test evidence; scan results; hypotheses not reproduced; exactly what was not covered and why; next repair scope. Severity is honest: name money exposure separately from a broken product rule.

## Failure handling

- A production check would need a burst, a payment or a real account: do not run it; list it under not covered.
- A tool is read-only (the Cloudflare MCP connector and wrangler's login were both zone-read-only on 2026-10-07): say so, and use the owner's logged-in browser dashboard only on the owner's word for that change.
- The scan detector cannot be proven on a planted key: the scan result is reported as not run, never as clean.
- A parallel session edited the same files: diff before trusting your mental model of them.

## Verification

`bash <base>/../../tests/run_tests.sh`

The ledger this audit relies on refuses unmeasured verdicts; each plugin's scripts are tested on known-bad fixtures first (tests/run_all.sh at the marketplace root).

## Rules

1. Confirmed means reproduced. Everything else is a hypothesis or untested, and is labeled so.
2. Never print a secret value, including in a redacted-looking excerpt.
3. A fix that reverses a ruling needs the owner's word first; propose it with the ruling quoted.
4. When the owner rules that this skill should not do something, add that rule here in the same turn.
