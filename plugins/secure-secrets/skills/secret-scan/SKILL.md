---
name: secret-scan
description: "Scan a repo for leaked secrets without printing a single secret value: gitleaks proven on planted fake keys before it is trusted, git history plus build output plus untracked folders, every hit classified with the value masked, and a check that .dev.vars/.env are ignored and untracked. Use when the user says 'secret scan', 'check for leaked keys', 'did a key get committed', or as part of secure-launch. Do NOT use it for dependencies (dependency-audit), for transcripts (transcript-secret-guard), or to move or rotate a key (secret-rotation and secret-handling)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# secret-scan

The secret half of the 2026-10-07 `secret-dependency-scan`; the dependency half is now `secure-supply-chain:dependency-audit`.

## Trigger

A security audit, a pre-launch check, or the owner asking whether keys or dependencies are exposed.

## Inputs

- Repo path. Extra folders: the build output that ships (`out/`, `dist/`), untracked work folders (`.agents/`, `review-*`).

## Prerequisites

- `gitleaks` on PATH (`brew install gitleaks`; obtain it rather than writing a coverage caveat).

## Procedure

1. Ledger form: `python3 <base>/../../scripts/check_secrets.py REPO --extra-dir out --extra-dir .agents` (PASS/FAIL/UNKNOWN per scope). Raw form: `bash <base>/../../scripts/scan_secrets.sh REPO out .agents`. It refuses to scan until it has found two planted fake keys (exit 2 = the detector is not proven; report "not run").
2. For each hit, read the surrounding STRUCTURE with the value masked (`sed` the 8 to 40 characters to `<R>`). On 2026-10-07 all 11 hits in `.agents/` were filename-to-hash manifests. Classify: real credential, test fixture, hash or ID.
3. Check the secrets file is ignored: `git check-ignore -v .dev.vars` (or `.env`), and `git ls-files | grep -i 'env\|vars'` is empty.
4. A hit that is a test fixture or a hash, confirmed by reading the structure, goes into the repo's `.gitleaksignore` by fingerprint (on the owner's word, it is a repo change) or into `security/accepted.json` with the reason. Never weaken the scan to make it pass.

## Outputs

Counts per rule and file (never values), the classification of each hit, and the tracked/ignored checks for secrets files.

## Failure handling

- Detector not proven: say so; never report clean.
- A real credential found: do not print or test it; name the file and which key it is (by its last four characters only if the dashboard shows that), and hand the owner the rotation as a todo (`secret-rotation` skill, which uses `secret-handling` for the no-display steps).

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a committed fake key, a committed `.dev.vars`, an unignored `.env` all FAIL, and the value never appears in the output; a missing gitleaks is UNKNOWN (exit 3), never PASS. Known-good: the clean repo PASSes all three.

## Rules

1. Never print, echo, or paste a secret value, even redacted-looking.
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
