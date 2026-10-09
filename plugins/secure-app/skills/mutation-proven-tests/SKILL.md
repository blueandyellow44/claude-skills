---
name: mutation-proven-tests
description: "Prove that tests catch the removal of each security protection, and that they run before every deploy: write a regression test per protection (ownership, sign-in, bounds, limits, signature checks), remove the protection in a throwaway worktree with scripts/mutation_check.py, require DETECTED, show the old suite let it SURVIVE, then wire the tests into the standard test command, the deploy script and CI (secrets scoped per step, tools pinned). Use when the user says 'regression test', 'prove the tests catch it', 'mutation test', 'make sure this cannot regress', or as step 7 and the repair of launch-security-audit. Do NOT use it to find what is unprotected (asvs-lite and secure-launch do that); it proves a protection that exists."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# mutation-proven-tests

On 2026-10-07 removing every ownership check from a production map app left `test:api` green (115 of 115); a news-scoring app caught 24 of 24 deliberately removed protections only after its repair. A passing test proves nothing until it has been seen to fail.

## Trigger

A protection is reported as holding, a fix lands, or the owner asks that something never regress.

## Inputs

- The protection: file, the exact line or expression that enforces it.
- The test command (the one CI or the deploy runs, not a one-off).

## Prerequisites

- A git repo with the protection committed at HEAD (the worktree is made from HEAD).
- Test harness that drives the real handler in-process with fakes (for example `tests/api/helpers/fakeCloudflare.ts`, D1 on node:sqlite with the real migrations).

## Procedure

1. **Write the test as the attacker.** Two synthetic accounts; the second tries the forbidden action; assert the refusal AND that nothing was spent, stored or sent (count mocked provider calls and ledger rows, not just the status code).
2. **Prove it.** For each protection:
   `python3 scripts/mutation_check.py --repo R --file F --find "<the check>" --replace "<check removed>" --test "<new test cmd>" --link node_modules` must print DETECTED.
3. **Show the gap was real.** Same mutation with the OLD suite's command: SURVIVED is the finding.
4. **Wire it in.** Add the file to the standard test command. Make the deploy script run that command and refuse on failure, BEFORE building. Prove the gate in a throwaway repo whose test fails: the build must never start.
5. **CI (scoped-secrets pattern).** Each secret is exposed only to the step that uses it; deploy tools pinned to an exact version; a pre-publication step runs tests and guards (and loads the built code under the real runtime, which caught a break vitest missed).
6. A test the new limiter or check breaks (a bulk check that is not one client) is adjusted to reset the state, never by weakening the protection; say so in the test.

## Outputs

Per protection: DETECTED with the new test, SURVIVED with the old suite (or "already guarded"). The test command and the deploy gate, with the throwaway-repo proof.

## Failure handling

- `--find` occurs 0 or more than once: refuse; pick a longer, unique snippet.
- Mutation leaves a worktree behind: `git worktree prune`; the script removes it in a `finally`.
- Pre-existing failures in another suite: run it on the pre-change commit; report them as pre-existing only if they fail the same way there.

## Verification

`bash <base>/../../tests/run_tests.sh`

The mutation cases: a guarded test detects a removed ownership check, a weak test lets it survive, absent or ambiguous patterns are refused, and the real tree is untouched.

## Rules

1. Never report a control as holding without a DETECTED line for it.
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
