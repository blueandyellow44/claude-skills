---
name: security-inventory
description: "Map a repo's attack surface from its code before judging it: every route and whether an auth or ownership call appears in its handler, the sign-in mechanism, every outbound fetch (constant host or variable URL), every paid API and whether a spend cap sits next to the call, secrets by NAME and where they are read, data stores, and deploy targets. Writes security/inventory.json plus a markdown summary. Use when the user says 'what does this app expose', 'attack surface', 'map the routes', 'what paid APIs does it call', or as the first step of secure-launch. Do NOT use it to decide whether something is safe (that is the checks' job) or on a repo the user does not own."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# security-inventory

## Trigger

A repo is about to be audited, launched, or handed to someone, and the question is "what is exposed". Not for verdicts: the inventory states what exists; `secure-launch` judges it.

## Inputs

- Repo path. Optional `--out` folder (default `REPO/security`; use the suite's `validation/<repo>/` when the repo must not be written to).

## Prerequisites

- Python 3. The `secure-core` plugin (this one).

## Procedure

1. `python3 <base>/../../scripts/inventory.py REPO --out OUT`.
2. Read `OUT/inventory.md`. Start with routes marked `none found`: no auth or ownership call appears inside that handler. That is a lead, not a finding: middleware mounted elsewhere (Hono `app.use`, Next `middleware.ts`) is invisible to a line scan, so open the router before saying a route is public.
3. Paid APIs with `spend cap reference: NONE FOUND` go to the `abuse-and-spend` skill.
4. Variable-URL outbound fetches go to the `outbound-fetch-guard` skill.
5. Secrets are listed by name only. If a value is ever needed, stop: the `secret-handling` skill governs that.

## Outputs

`inventory.json` (stack, routes with `gate`, outbound fetches with kind and host, paid APIs with call sites and cap references, secrets read, data stores, deploy targets, auth mechanism) and `inventory.md`.

## Failure handling

- A router pattern it does not know (a custom framework): routes come back empty. Say "routes not mapped" rather than "no routes", and list them by hand from the entry file.
- A monorepo: run it on each app folder as well as the root.

## Verification

`bash <base>/../../tests/run_tests.sh`

Finds exactly the three production routes of a Hono fixture and not the test-only one, marks the uncapped Anthropic call, sees a spend cap when one is added, and maps an empty repo to nothing.

## Rules

1. Names, never values. The inventory never opens `.dev.vars` or `.env`.
2. `none found` is never written up as "public" without reading the router.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
