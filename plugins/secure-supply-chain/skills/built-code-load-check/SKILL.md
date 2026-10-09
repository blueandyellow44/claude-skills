---
name: built-code-load-check
description: "Before trusting a dependency bump, prove the BUILT output resolves and loads under plain Node, not the test runner: every bare import and require in dist/ resolved with Node's own resolver (nothing executed), then each declared side-effect-free module imported in a child Node with an empty environment. Catches exports-map breaks like @extractus 8.1.0, which passed every vitest test and broke under Node. Use when the user says 'is this upgrade safe', 'bump X', 'it passes tests but', after npm audit fix, or in a deploy gate for Node services. Do NOT use it on a Cloudflare Worker bundle as proof of runtime health (workerd is not Node) or to run a service's main."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# built-code-load-check

## Trigger

A dependency changes in a Node service (a feed-ingestion service, any server or CLI), or a deploy gate needs a runtime check the test runner cannot give.

## Inputs

- Repo path; built folders (default dist, build, out, lib); optional `--entry` modules, or `security/load-check.json` `{"entries": ["dist/lib/ingest.js"]}`.

## Prerequisites

- `node` (the version production runs). The build already run: this check never builds.

## Procedure

1. Build the code the way production does.
2. `python3 <base>/../../scripts/load_built.py REPO`. `built.resolve` resolves every bare import from the file that makes it, with ESM and CommonJS rules as Node applies them.
3. Name the modules that are safe to import (no server start, no job run) in `security/load-check.json`, and re-run: `built.import.*` imports each in a child Node with no environment variables, 20 s limit.
4. On a FAIL after a bump: pin back to the last version that resolves and record why in the project's notes; the upgrade becomes the owner's decision with the error quoted.
5. In CI, run this after the build and before publish (the news-scoring app's publish gate does).

## Outputs

`built.resolve` with the failing file, specifier and Node error code; `built.import.<entry>` per declared module.

## Failure handling

- No build output: UNKNOWN; build first.
- An entry that hangs: it runs something at import; take it off the list.
- A Worker bundle: bundled output has no bare imports, so it passes trivially; say that this proves nothing about workerd.

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: a built file importing a subpath the package's exports map hides FAILs with ERR_PACKAGE_PATH_NOT_EXPORTED; a module that throws at import FAILs; no build output is UNKNOWN (exit 3). Known-good: the same package's exported entry resolves and imports.

## Rules

1. Node, never the test runner, is the judge here.
2. Never import a main that starts a server, a job or a network call.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
