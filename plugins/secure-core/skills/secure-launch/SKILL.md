---
name: secure-launch
description: "Run the whole secure-launch suite on one repo and write ONE findings ledger: detect the stack, map the attack surface, run every applicable check (secrets, dependencies and pinning, built-code load, app-layer bounds, outbound fetch, paid-API spend, and the Cloudflare, Next.js/OpenNext, Fly/Supabase, Apps Script and Railway adapters), each reported as PASS, FAIL or UNKNOWN with evidence and a one-line fix. Use when the user says '/secure-launch', 'is this safe to ship', 'security check before deploy', 'run the security suite', or before any first launch. Do NOT use it for the deep manual audit with live repro (that is launch-security-audit, which calls this) or on someone else's site."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# secure-launch

## Trigger

Before a launch, before a deploy that changes routes, auth, dependencies or headers, or when the user asks how safe a repo is.

## Inputs

- Repo path (required). Optional: live URLs (`--url`, read-only HEAD probes), build or untracked folders to include in the secret scan (`--extra-dir out`), an output folder (`--out`).

## Prerequisites

- All six secure-launch plugins next to each other (a missing one is reported as UNKNOWN for its checks, never skipped silently).
- `gitleaks` for the secret scan, `npm` for the dependency audit, `node` for the built-code load check. Each missing tool makes its checks UNKNOWN with the install line.

## Procedure

1. Say the ground rules: read-only on the repo, no deploy, no burst, no form, no credential, no secret value printed.
2. `python3 <base>/../../scripts/secure_launch.py REPO --out OUT [--url https://host/] [--extra-dir out]`. When the repo must stay untouched, `OUT` is outside it.
3. Read `OUT/findings.md`. FAILs first by severity, then every UNKNOWN with its reason. An UNKNOWN is work not done, not a pass: either make it runnable (install the tool, build the code) and re-run, or carry it into the report as uncovered.
4. Check every FAIL by hand against the code before reporting it. A false positive is a defect in the suite: fix the check and re-run.
5. Report in chat: per severity, each finding with its evidence path and fix; then the UNKNOWNs; then what the suite cannot see (dashboard-only settings, zone rules, Access policies, live data).
6. A FAIL or UNKNOWN the owner rules acceptable goes into `security/accepted.json` with the exact evidence string, the owner's reason and the date. It stays visible (accepted until the expiry, 90 days by default); a critical FAIL cannot be accepted.

## Outputs

`OUT/findings.json` and `OUT/findings.md` (counts of FAIL, UNKNOWN, PASS on separate lines; adapters that ran or why not), plus `inventory.json` and `inventory.md`.

## Failure handling

- A check crashes or prints unusable output: it becomes one UNKNOWN naming the script and the error. Fix the check; never delete the row.
- Network down: the dependency audit is UNKNOWN; everything static still runs.
- Exit 3 means no FAIL but something unmeasured. Never read it as clean.

## Verification

`bash <base>/../../tests/run_tests.sh`

The suite-wide integration proof (every plugin's known-bad and known-good fixtures, then the orchestrator on a fixture with a plugin removed) runs from the marketplace root with tests/run_all.sh.

## Rules

1. No verdict without a measured run. UNKNOWN is never folded into PASS or FAIL.
2. Never print a secret value; the ledger refuses credential-shaped text.
3. Read-only on the repo unless the owner asks for the ledger to be written into it.
4. When the owner rules that this skill should not do something, add that rule here in the same turn.
