// ai-guard.ts: the two guards every route that reaches a paid model API runs
// before the call. Generalized from a production dashboard API (2026-10-13).
//
// 1. Per-IP limiter: a Cloudflare rate-limit binding (AI_LIMITER). Free to
//    check, so it runs first, before any KV read. It is BEST-EFFORT: the
//    binding is kept per edge machine and is eventually consistent. Measured
//    on 2026-10-13: a 20-a-minute limit first answered 429 after about 30
//    requests; a 60-a-minute limit on another Worker fired at request 69 on
//    one connection and never when each request opened a fresh connection.
// 2. Daily counter in KV: ONE shared budget (`ai:count:<UTC day>`) across every
//    AI route, reserved BEFORE the upstream call (read, +1, put), so a burst
//    cannot outrun the cap. This is the hard cap. The read/put race can
//    overshoot by a request or two, never by much. The key is the DAY, never
//    a caller-supplied id: a counter keyed on a header or body field resets
//    every time the caller rotates the id.
//
// wrangler.toml:
//   [vars]
//   AI_DAILY_LIMIT = "150"
//   [[ratelimits]]
//   name = "AI_LIMITER"
//   namespace_id = "1001"
//   simple = { limit = 20, period = 60 }
//   [[kv_namespaces]]
//   binding = "CACHE"
//   id = "<your namespace id>"
//
// Use in a route:
//   const limited = await checkIpLimit(request, env)
//   if (limited) return limited
//   if (exceedsQueryCap(name)) return queryTooLongResponse()
//   try {
//     await reserveAiBudget(env)          // immediately before the paid call
//     const res = await fetch('https://api.anthropic.com/v1/messages', ...)
//   } catch (err) {
//     if (err instanceof BudgetExhaustedError) return budgetExhaustedResponse(err)
//     throw err
//   }

export type GuardEnv = {
  CACHE: KVNamespace
  AI_LIMITER: RateLimit
  AI_DAILY_LIMIT?: string
}

export const MAX_QUERY_CHARS = 120
const DEFAULT_AI_DAILY_LIMIT = 150
const COUNT_TTL_SECONDS = 60 * 60 * 48

function json(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers)
  headers.set('content-type', 'application/json; charset=utf-8')
  return new Response(JSON.stringify(body), { ...init, headers })
}

export class BudgetExhaustedError extends Error {
  constructor(
    public readonly used: number,
    public readonly limit: number,
  ) {
    super('daily AI budget reached')
  }
}

function utcDay(): string {
  return new Date().toISOString().slice(0, 10)
}

// Caller-supplied strings that reach the prompt are capped: a long name is a
// long prompt is a bigger bill.
export function exceedsQueryCap(...values: Array<string | null | undefined>): boolean {
  return values.some((v) => typeof v === 'string' && v.length > MAX_QUERY_CHARS)
}

export function queryTooLongResponse(): Response {
  return json({ error: `query too long (max ${MAX_QUERY_CHARS} characters)` }, { status: 400 })
}

// Returns a 429 response when this client IP has exceeded the per-minute
// limiter, otherwise null. Best-effort: see the note at the top.
export async function checkIpLimit(request: Request, env: GuardEnv): Promise<Response | null> {
  const ip = request.headers.get('cf-connecting-ip') || 'unknown'
  const { success } = await env.AI_LIMITER.limit({ key: ip })
  if (success) return null
  return json(
    { error: 'too many requests', message: 'Too many requests from this address. Try again in a minute.' },
    { status: 429 },
  )
}

export type DailyBudget = { ok: boolean; used: number; limit: number; today: string }

// Reserves one unit of a named daily counter. `used` is the count after
// reservation when ok, or the current count when the cap is already hit.
export async function reserveDailyBudget(env: GuardEnv, prefix: string, limit: number): Promise<DailyBudget> {
  const today = utcDay()
  const key = `${prefix}:count:${today}`
  const current = parseInt((await env.CACHE.get(key)) ?? '0', 10) || 0
  if (current >= limit) return { ok: false, used: current, limit, today }
  await env.CACHE.put(key, String(current + 1), { expirationTtl: COUNT_TTL_SECONDS })
  return { ok: true, used: current + 1, limit, today }
}

// An unset or unparseable limit falls back to the DEFAULT, never to unlimited.
export function aiDailyLimit(env: GuardEnv): number {
  const parsed = parseInt(env.AI_DAILY_LIMIT ?? '', 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_AI_DAILY_LIMIT
}

// Reserves a unit of the shared AI budget or throws BudgetExhaustedError.
// Call this immediately before the paid request so cache hits never consume
// budget.
export async function reserveAiBudget(env: GuardEnv): Promise<void> {
  const budget = await reserveDailyBudget(env, 'ai', aiDailyLimit(env))
  if (!budget.ok) throw new BudgetExhaustedError(budget.used, budget.limit)
}

export function budgetExhaustedResponse(err: BudgetExhaustedError): Response {
  return json(
    {
      error: 'daily AI budget reached',
      message: `Daily AI budget reached (${err.limit} requests). Resets at midnight UTC.`,
      used: err.used,
      limit: err.limit,
    },
    { status: 429 },
  )
}
