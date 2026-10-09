---
name: dependency-audit
description: "Audit a repo's supply chain without changing it: production npm audit with a reachable-or-not verdict per advisory recorded in security/advisory-triage.json, lockfile presence per package folder, GitHub Actions pinned to commit SHAs, secrets scoped to the one workflow step that uses them, and wrangler pinned. Use when the user says 'npm audit', 'dependency check', 'are the actions pinned', 'supply chain', or as part of secure-launch. Do NOT use it to apply updates (dependency-updater does that, and majors are the owner's call), for licenses (engineering-audit:dependency-auditor), or for secrets (secret-scan)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# dependency-audit

The dependency half of the 2026-10-07 `secret-dependency-scan`, plus the CI pattern of a news-scoring app (secrets scoped per step, wrangler pinned) as checks.

## Trigger

Before a launch or deploy, after a dependency change, or when an advisory email arrives.

## Inputs

- Repo path. An existing `security/advisory-triage.json` if the repo has one.

## Prerequisites

- `npm` (network read of the registry). `pip-audit` for Python projects with a requirements.txt (UNKNOWN without it).

## Procedure

1. `python3 <base>/../../scripts/check_deps.py REPO` and `python3 <base>/../../scripts/check_pinning.py REPO`.
2. For EACH high or critical FAIL, decide reachability from how the app is built and what it imports: a Next static export never runs the Next server; an unused `hono/jsx` or MapLibre `setHTML` path is unreachable; build-only tools (postcss, nanoid) do not ship. Grep the code for the vulnerable API before calling it unreachable.
3. Record the verdict in `security/advisory-triage.json` (a repo change: on the owner's word): `{"advisories": [{"package", "reachable": true|false, "reason", "reviewed": "YYYY-MM-DD"}]}`. Unreachable becomes PASS with the reason shown; reachable stays FAIL until fixed.
4. Fixes: a compatible fix (`npm audit fix`) is proposed with the lockfile diff; a MAJOR fix is a separate decision for the owner, never applied here. Before trusting any bump, run `built-code-load-check` (a news-scoring app kept `@extractus/article-extractor` at 8.0.20 because 8.1.0 broke under plain Node while every test passed).
5. Pinning FAILs: give the exact SHA for each action (`gh api repos/OWNER/ACTION/commits/TAG --jq .sha`) and the step each secret belongs to.

## Outputs

Ledger JSON per check; per advisory: package, severity, reachable with the reason, fix version, major or not; unpinned actions with file:line; broad secrets with their level.

## Failure handling

- Offline or npm error: UNKNOWN with npm's message. An audit report with no vulnerabilities map is UNKNOWN, never clean.
- pnpm/yarn lockfile without that tool installed: UNKNOWN naming the tool.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: an untriaged critical with a major fix, a high, untriaged moderates, a package folder with no lockfile, a triage marked reachable, tag-pinned actions, secrets in workflow- and job-level env, `npx wrangler@latest` all FAIL; an npm error report is UNKNOWN (exit 3). Known-good: everything triaged unreachable with reasons, SHA-pinned actions, step-scoped secrets and a lockfile-pinned wrangler all PASS.

## Rules

1. Never install, bump or `audit fix` anything in this skill.
2. Unreachable is a claim with a reason and a date, checked against the code, never a default.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
