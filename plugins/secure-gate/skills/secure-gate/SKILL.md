---
name: secure-gate
description: "Make the secure-launch ledger enforce something: a gate that refuses on any FAIL and on any UNKNOWN not accepted by the owner in security/accepted.json, plus three drop-in templates (a GitHub Actions workflow with SHA-pinned actions and a checksum-verified gitleaks, a deploy-script gate generalized from a production app's deploy script that refuses before building, and a pre-push hook), vendored into a repo by install_gate.py. Use when the user says 'add the security gate to X', 'block deploys on security failures', 'CI for security', 'pre-push check'. Do NOT install anything without the owner naming the repo and the action; do NOT use it to run the checks themselves (secure-launch)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# secure-gate

## Trigger

The owner names a repo and asks for the gate in CI, in its deploy script, or as a pre-push hook.

## Inputs

- The repo, which of the three templates, and the repo's security test command (its mutation-proven tests), written to `security/gate.json` as `{"test_command": "npm run test:api"}`.

## Prerequisites

- The owner's word naming the repo and the action: these are repo changes and, for the hook, a standing change.
- A clean ledger to start from: run `secure-launch` first; every FAIL either fixed or accepted with the owner's reason, every UNKNOWN made runnable or accepted.

## Procedure

1. `python3 <base>/../../scripts/install_gate.py REPO --dry-run --with-ci` (add `--with-pre-push`, `--with-deploy-gate` as asked); show the owner the file list.
2. On the owner's word, run it without `--dry-run`. It never overwrites and never commits.
3. Write `security/gate.json` with the test command, and `security/accepted.json` with any accepted items: `{"id", "evidence" (copied exactly from the ledger), "reason", "ruled": "YYYY-MM-DD", "expires"?}`. An acceptance covers that one result, expires after 90 days, and a critical FAIL can never be accepted.
4. Add CODEOWNERS on `.secure-launch/`, `security/` and `.gitleaks*`: a pull request can otherwise edit what judges it.
5. CI: check who merges in that repo first. A repo where someone else reviews and merges gets a branch and a PR for them to merge. A repo the owner runs alone can take a direct commit to `main`, pushed on the owner's word, with no PR; the workflow runs on pushes to `main`, so the check still runs.
6. Deploy gate: add the two lines from the template's header to the top of the deploy script; prove it in place: make a test fail, run the deploy, the build must not start.
7. Pre-push: the owner links it, or it is linked on the owner's word: `ln -s ../../.secure-launch/pre-push .git/hooks/pre-push`.
8. Gate by hand at any time: `python3 <base>/../../scripts/gate.py LEDGER --repo REPO --tests-from security/gate.json`.

## Outputs

Files written, the gate's first run output, and the proof that a failing test stops the deploy.

## Failure handling

- The gate refuses on UNKNOWN in CI because a tool is missing there: install the tool in the workflow (gitleaks is already there; pip-audit if Python), or accept the id with a reason. Never delete the check.
- A vendored copy goes stale: `.secure-launch/VERSION` names the suite commit; re-vendor by deleting `.secure-launch/` and re-running install (on the owner's word).

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a FAIL, an UNKNOWN alone, an empty ledger, a stale ledger, a ledger from another repo or from a run that did not finish, an undeclared or failing test command, a critical FAIL with an acceptance, an acceptance whose evidence differs, an expired or undated acceptance all refuse; hand-edited counts and an invalid status are gate errors; a failing test stops the deploy before the build; the pre-push hook refuses. Known-good: all PASS passes; an accepted UNKNOWN passes and is still printed and annotated; the vendored orchestrator resolves every plugin; the CI template passes the suite's own pinning and secret-scope checks.

## Rules

1. Nothing is installed in any repo without the owner naming it.
2. UNKNOWN is never a pass; acceptance is explicit, dated, and visible.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
