---
name: ai-route-metering
description: "Meter every route that reaches a paid model API (Anthropic, OpenAI, Gemini, Vertex, ElevenLabs, Deepgram, Replicate, fal, Perplexity, OpenRouter) in one of your Workers: a shared KV or D1 daily counter reserved BEFORE the call as the hard cap, keyed on the day (never on a caller-supplied id), plus a Workers rate-limit binding as a best-effort backstop. Ships a drop-in template (templates/ai-guard.ts). Use when the user says 'daily cap', 'AI budget', 'meter the AI routes', 'rate-limit binding', 'someone could loop my model route', or when secure-launch reports meter.*. Do NOT use it for spend caps in dollars read from config (abuse-and-spend) or for zone rate-limit rules (cloudflare-pages-workers)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Grep
  - Write
---

# ai-route-metering

Built from the 2026-10-13 account audit and fixes. Three public Workers let an anonymous caller run paid model calls with no counter: a client's dashboard API and its demo twin (the daily budget covered one route of six and incremented AFTER the call), and a dormant course's feedback route on Opus. The fix landed the same day as a shared helper, reserved before every call, and a rate-limit binding; the template here is that helper with the project names removed.

**The binding is best-effort; the counter is the hard cap.** Cloudflare's rate-limit binding is kept per edge machine and is eventually consistent. Measured 2026-10-13: the dashboard API's 20-a-minute binding first answered 429 after about 30 requests; the coaching app's 60-a-minute demo limiter fired at request 69 on one connection and never when each request opened a fresh connection. A KV counter read and written before the call bounds the day whatever the binding does; its read/put race overshoots by a request or two, never by much.

## Trigger

A paid model API is called from a route a stranger can reach, or `abuse-and-spend` found `spend.cap.*` and the cap is a request count rather than dollars.

## Inputs

- Repo path.
- The daily number the owner will accept (requests, not dollars; 150 on the dashboard API).
- Whether the Worker has a KV namespace already (the counter needs one) or D1.

## Prerequisites

- secure-core.
- A KV namespace bound to the Worker, or a D1 database with a usage table.

## Procedure

1. `python3 <base>/../../scripts/check_metering.py REPO`.
2. `meter.<provider>` FAIL "no counter": copy `<base>/../../templates/ai-guard.ts` into the Worker as `src/lib/ai-guard.ts`, adapt `GuardEnv` to the project's Env, add `AI_DAILY_LIMIT` to `[vars]` and the `[[ratelimits]]` block to wrangler config, then in every function that makes the paid call put `await reserveAiBudget(env)` on the line ABOVE the `fetch` or `messages.create`, and in the route return `budgetExhaustedResponse(err)` on `BudgetExhaustedError`. Call `checkIpLimit` first in the route, before any KV read.
3. "counter touched only after the call": move the reservation above the call. A burst of parallel requests all read the same count and all go upstream when the write comes afterwards.
4. "keyed only on a caller-supplied id": key the counter on the UTC day (one shared budget), or on `cf-connecting-ip` when a per-client count is wanted; keep any caller id as a second counter where the stricter reading wins (a classroom app keys its caps on a SHA-256 of the connecting address as well as the teacher id since 2026-10-13).
5. `meter.ratelimit-binding` FAIL: add `[[ratelimits]]` with `name`, a `namespace_id` unique in the account, and `simple = { limit = 20, period = 60 }`; call `env.<NAME>.limit({ key })` keyed on `cf-connecting-ip`. Say in the commit that it is best-effort.
6. Cap every caller-supplied string that reaches the prompt (`exceedsQueryCap`, 120 characters): a long name is a long prompt is a bigger bill.
7. Prove it with `mutation-proven-tests`: remove the `reserveAiBudget` line, the test that drives the route past the limit with a mocked provider must fail and the mock's call count must show the overshoot.

## Outputs

Per provider: every call site, the function that reserves, the line of the reservation, the binding; and a one-line statement in the ledger that the binding is best-effort.

## Failure handling

- A compiled `.js` sibling of a `.ts` route is tracked in git and still carries the old unmetered code: the check reports the `.js` line. Delete the stale sibling or untrack it; a wrangler `main` that points at the `.ts` does not make the `.js` safe to leave.
- The call sits in a helper with no reservation and every route that calls the helper reserves first: the check follows up to three caller levels and PASSes; deeper chains are not followed, so move the reservation into the helper.
- The counter is a D1 row: the SQL must name usage, count, budget, quota or spend for the check to see it; otherwise rename or accept with the line as evidence.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a `fetch` of api.anthropic.com in a function with no counter (FAIL high), `buildDailyDigest()` above the call (a name containing Daily counts nothing; FAIL high), a Python `def` with no counter (FAIL high, naming the def), a KV `put` of the count after the fetch (FAIL medium), a counter keyed on `${teacherId}` read from a header or on `${deviceId}` destructured from the body (FAIL medium), a wrangler config with no `[[ratelimits]]` (FAIL medium), and a `[[ratelimits]]` binding declared but never `.limit()`ed in code (FAIL medium) all FAIL. Known-good: `reserveAiBudget(env)` above the call in the same function or in the calling route, a FastAPI `def` that calls `reserve_daily_call(store)` or `store.incr("llm:count:" + day)` before the call, a `[[ratelimits]]` block whose binding the route calls, and an SDK `messages.create` after a KV get/put keyed on the day all PASS (bench 2026-11-01).

## Rules

1. The counter is reserved before the call, never after; "the binding will catch it" is not a cap.
2. No burst test against a paid route; prove the cap with a mocked provider.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
