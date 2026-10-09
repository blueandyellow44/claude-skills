---
name: pages-preview
description: "Deploy the SF City Walks working tree to the PREVIEW at test.wallywalks.app (Cloudflare Pages project wallywalks-app, branch test) and prove it: build, swap wrangler.wallywalks-app.toml in, deploy, restore wrangler.toml and prove it with git diff, verify the served build identity and /api/me, and run the cache checklist. Use when the owner says 'deploy to test', 'put it on the test link', 'can you deploy to cloudflare' for testing, 'phone test build', 'is test up to date'. Never deploys production: 'deploy to wallywalks.app' is a separate step on the owner's word and this skill refuses it."
allowed-tools:
  - Bash
  - Read
---

# pages-preview

## Goal

The owner opens test.wallywalks.app on a phone and sees exactly the build that was just made, with production untouched and the repo's config back as it was.

## Why this exists

The deploy is a config swap (`wrangler pages deploy` reads `wrangler.toml`, which is deliberately an unprovisioned placeholder), and two caches have each served stale results for days: browsers kept car routes for a week, and the zone rewrote sprite cache headers to four hours. One rule living in one session is how these get missed. For Wrangler itself, use `cloudflare:wrangler`.

## Preconditions

- The owner's word for a preview deploy in this session. A general "keep going" is not it.
- Branch `wallywalks-app`. Read the project's deploy-target notes first; obligatory.
- `npm run deploy:cf` is a deliberate hard stop. Do not use it or work around it.
- `CITY_WALKS_REPO` names the map repo (the script refuses to run without it).

## Steps

1. **Cache checklist, before building.** If the route source or the step shape changed since the last deploy: bump `ROUTE_API_VERSION` in `lib/customWalks.ts` AND the worker cache key (`route-foot-vN`) in the API worker's catch-all route file under `functions/api/`. Browsers cache `/api/route` answers 7 days per URL; the edge caches by key. Changing one without the other leaves stale routes on phones.
2. **Dry run.** `"${CLAUDE_PLUGIN_ROOT}/skills/pages-preview/scripts/preview_deploy.sh"` prints every step and changes nothing. Read it.
3. **Deploy.** Same script with `--go`. It refuses unless `wrangler.toml` equals HEAD (a staged edit counts as a difference), saves the exact bytes, builds, copies `wrangler.wallywalks-app.toml` over `wrangler.toml`, runs `npx wrangler pages deploy out --project-name wallywalks-app --branch test`, puts the saved bytes back (also on failure) and proves it with a byte comparison. Exit 5 means the config was NOT restored; the saved copy's path is printed.
4. **Verify what is served.** Every check sets the exit code: the hashed `/_next/static` chunk and css names the served homepage loads equal those in `out/index.html` (exit 7 if neither page names any); the Ferry Building and City Hall sprites match local by sha256; `/api/me` answers 200 (404 is the build before sign-in); sprite `cache-control` is `no-cache`. The script also fingerprints production's homepage before and after and exits 8 if it changed during the run. That shows production's asset set did not change across this run, not that production is untouched in any wider sense.
5. **Preview environment.** Preview and production have separate secrets. Sign-in needs `GOOGLE_CLIENT_SECRET` and `BETTER_AUTH_SECRET` in the preview environment; generation needs the Gemini secret there (it answered 503 on a preview without it, 2026-10-03). The preview shares production's D1 and R2 bindings: use disposable data and delete it.
6. **Report** from the owner's screen: the URL, what they will see, what was verified and what was not.

## Rules

1. Reading the project's deploy-target notes is obligatory before step 1.
2. Production is refused. The script exits 3 on `main`, `master`, `production`, `prod` and `wallywalks-app`, and on any name that is not `test` or `phone-test-<lowercase letters, digits, hyphens>`. Do not hand-run the production command from this skill.
3. `wrangler.toml` must be byte-identical to its pre-run state, and equal to HEAD, when the skill ends: check `git diff HEAD -- wrangler.toml`, not plain `git diff`, which misses a staged change. Anything else is the first thing reported.
4. Never push to a git remote from here; that needs its own word.
5. A new custom domain is added from the Cloudflare DASHBOARD. The API path skips the automatic DNS record.
6. A mismatch right after deploy can be propagation. Re-run the check once after a minute before reporting either result; report what was measured.
7. When the owner rules out something this skill does, add it here in the same turn.

## Output

The deployment URL, each verification line with its result, the exit code, the byte-comparison proof for `wrangler.toml`, and the one sentence the owner needs to try it. The script's `--go` path has not been run since it was rewritten on 2026-10-04 (tests use mocks); say so on its first real run and read its output closely.
