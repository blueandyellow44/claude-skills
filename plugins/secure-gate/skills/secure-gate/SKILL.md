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

Known-bad: a FAIL, an UNKNOWN alone, an empty ledger (also with `--tests-from` and a passing test command: the empty check runs before the tests, so a green test never stands in for a scan), a stale ledger, a ledger from another repo or from a run that did not finish, an undeclared or failing test command, a critical FAIL with an acceptance, an acceptance whose evidence differs, an expired or undated acceptance all refuse; hand-edited counts, an invalid status, a repo field that is missing or relative (`""` or `.` would resolve to the working directory, which is the repo in CI and in the hook), a git repo whose ledger has no git binding or a binding to another commit or tree, a `generated_at` with no time zone (a message, never a traceback) or more than five minutes in the future are gate errors; a failing test stops the deploy before the build; the pre-push hook refuses. Known-good: all PASS passes; the same repo named with a trailing slash passes; a plain folder with no git field passes; two minutes of clock skew passes; an accepted UNKNOWN passes and is still printed and annotated; the orchestrator's default run (ledger into `REPO/security`, untracked) followed by the gate-by-hand step passes, while a source file added after that run is refused; the vendored orchestrator resolves every plugin; the CI template passes the suite's own pinning and secret-scope checks.

What the gate cannot see, stated plainly: a FAIL row hand-edited to PASS with plausible evidence and the counts recomputed. The ledger carries no signature, and any digest the orchestrator could add is one a tamperer recomputes with the same open code, so the gate does not pretend to one. The control is where the ledger is written: in CI and in the hook it is written in-job, outside the checkout, and a ledger found in the tree is never the one the gate reads (the three templates all do this). The benchmark keeps this case as a known miss on purpose.

## Rules

1. Nothing is installed in any repo without the owner naming it.
2. UNKNOWN is never a pass; acceptance is explicit, dated, and visible.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
