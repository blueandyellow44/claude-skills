---
description: Run the secure-launch suite on a repo and write one PASS/FAIL/UNKNOWN findings ledger
argument-hint: "[repo path] [--url https://host/] [--out DIR]"
---

Run the `secure-launch` skill on: $ARGUMENTS (default: the current working directory).

Read-only on the repo. If the repo must not be written to, pass `--out` to a folder outside it. Report FAILs by severity with evidence paths, then every UNKNOWN with its reason, then what the suite cannot see. Check each FAIL by hand against the code before reporting it.
