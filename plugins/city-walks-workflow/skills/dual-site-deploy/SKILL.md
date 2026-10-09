---
name: dual-site-deploy
description: "Deploy each production site built from this repo from its OWN branch: wallywalks.app (the product, branch wallywalks-app) and any second site built from the same code on its own branch and worktree, with scripts/deploy-site.mjs: refuse the wrong branch and a dirty tree, build the site its own way, check the built page, swap and always restore wrangler.toml, check the live site. Use when the owner says 'deploy', 'deploy to production' or names a site. The test preview is pages-preview."
allowed-tools:
  - Bash
  - Read
---

# dual-site-deploy

## Standing facts

- Each site is its own project: its own branch, Pages project, build command, data and secrets. Keep them apart even though they share the map code.
- wallywalks.app: branch `wallywalks-app` in the map repo, Pages project `wallywalks-app`, `npm run build`. Google sign-in, caps, Stripe packs, no Google content.
- A second site: its own branch in its own worktree under `.claude/worktrees/`, its own Pages project and build command (`scripts/deploy-site.mjs` names them). It may run without sign-in, caps or billing; then it carries NO payment secret, ever.
- A product change reaches another site only by a deliberate merge into that site's branch on the owner's word for that change. Never merge payment, pricing or sign-in work into a site that runs without them.
- The plugin's `site_guard` hook blocks a hand-typed deploy from the wrong branch or of the wrong build. List the sites beyond wallywalks.app in the file named by `CITY_WALKS_SITES`.

## Steps

1. Only on the owner's word naming the site. Commit first: the script refuses uncommitted tracked changes and the wrong branch.
2. wallywalks.app: in the map repo on `wallywalks-app`, `node scripts/deploy-site.mjs app`. Another site: in its worktree on its branch, `node scripts/deploy-site.mjs <site>`. Data first where needed: rendered audio and media to that site's bucket, D1 migrations to that site's database.
3. Read the script's live checks (page, mode, a sample story); for a site without billing also confirm `/api/billing` reports no pack. Confirm in the user's own Chrome when the change is visual.
4. Tag a wallywalks.app production deploy `deploy-prod-YYYY-MM-DD[letter]`; record the deployment id in that site's own project notes the same turn.

## Rules

1. Never deploy one site's `out/` to the other project, never deploy a site from the other site's branch, and never edit wrangler.toml by hand for a deploy (the script restores it and proves it). Never merge or retire one branch into the other.
2. A paid or personal resource that only one site has (its own database, its own media bucket) is never copied to the other site.
3. When the owner rules out something this skill does, add it here in the same turn.
