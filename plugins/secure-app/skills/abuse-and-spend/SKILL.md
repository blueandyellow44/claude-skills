---
name: abuse-and-spend
description: "Find every way a stranger can make one of your apps spend money or forward traffic, and what stops them: paid APIs (Anthropic, ElevenLabs, Deepgram, Google Maps and Routes, OpenAI) with no spend cap near the call, caps that mean unlimited when unset, routes that forward request input to a third party without bounds (the case of a map app's /api/route and /api/reverse), no per-client ceiling, and caller-controlled model or max_tokens. Use when the user says 'can someone run up my bill', 'open proxy', 'spend cap', 'rate limit', 'cost amplification', or when secure-launch reports spend.*. Do NOT use it for SSRF to private addresses (outbound-fetch-guard) or for zone rate-limit rules (cloudflare-pages-workers)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
---

# abuse-and-spend

Built from the break test (2026-10-05) and audit (2026-10-07) of a production map app: routes and reverse lookups outside its service area and routes over 40 points are now refused; a 60-a-minute per-client ceiling lives in memory (the privacy page promises nothing is stored about signed-out visitors); a zone rule backs it up. A sibling gift app runs paid generation signed out with no dollar cap BY RULING: when a project has ruled like that, report it, never "fix" it without the owner's word.

## Trigger

A paid API or a forwarding route exists, or a bill surprised someone.

## Inputs

- Repo path, the inventory's paid-API list, the project's rulings on signed-out use.

## Prerequisites

- secure-core.

## Procedure

1. `python3 <base>/../../scripts/check_spend.py REPO`.
2. For each `spend.cap.*` PASS, find the enforcement: the cap must be checked BEFORE the call and must refuse. A cap reference that is only logged is a FAIL by hand.
3. For `spend.unset-cap`: an unset or unparseable cap must pause the feature, with a visible message.
4. For `spend.open-proxy`: name the bound each forwarded value needs (area, length, count, point limit) and where to refuse.
5. For `spend.per-client`: per-client ceiling in code first (in memory when storage would break a privacy promise), zone rule second (the pages.dev alias bypasses zone rules).
6. Prove each control with `mutation-proven-tests`: remove the cap or bound in a worktree, the test must fail, and the mocked provider's call count must show nothing was spent.
7. Never burst-test a route that reaches a paid or outside service; burst only a cached URL (cloudflare-pages-workers).

## Outputs

Per provider: call sites, cap location, enforcement verdict; forwarding routes with their bounds; the limiter; LLM parameter control.

## Failure handling

- A ruling allows uncapped use: record it under accepted in `security/accepted.json` with the ruling's date, so it stays visible.
- An SDK call (no host string in the code): the inventory lists it from package.json; read the call sites by hand.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: an uncapped Anthropic call, `Number(env.DAILY_SPEND_CAP) || Infinity`, an unbounded OSRM forward, no limiter, and `model: body.model` all FAIL. Known-good: a cap checked before the call that pauses when unset, a service-area bound, a limiter, and fixed model and max_tokens all PASS.

## Rules

1. No burst against paid or outside services, ever.
2. A spend ruling is quoted, never reversed silently.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
