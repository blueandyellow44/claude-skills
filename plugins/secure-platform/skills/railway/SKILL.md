---
name: railway
description: "Railway adapter of secure-launch (for example, a hosted MCP server): code never logs or returns the whole environment, the start command runs a production server, and the dashboard-only settings (service variables, public networking) are read with count-only commands, never plain `railway variables`, which printed variable prefixes into a transcript on 2026-09-04. Use when the user says 'check the Railway service', 'railway variables', or when secure-launch detects railway.json or railway.toml. Do NOT use it to change variables (secret-rotation)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# railway

## Trigger

A repo with `railway.json` or `railway.toml`.

## Inputs

- Repo path; the Railway project linked in that folder (`railway status`, read-only) for the dashboard reads.

## Prerequisites

- secure-core. The Railway CLI logged in, for the count-only reads.

## Procedure

1. `python3 <base>/../../scripts/check_railway.py REPO`.
2. Variables, count-only: `railway variables --kv | grep -c .` for the count and `railway variables --kv | cut -d= -f1` for names. Never plain `railway variables`.
3. Public networking: read it in the service's Settings, Networking (generated domain, custom domains, TCP proxy). Do not run `railway domain`: it CREATES a domain when none exists.

## Outputs

`railway.env-dump`, `railway.config`, and the names-only variable list and networking state.

## Failure handling

- CLI not linked in the folder: say so; do not `railway link` without the owner's word (it writes config).

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: logging process.env whole and a dev-server start command FAIL, and cannot_see carries the count-only command. Known-good: logging a key count only and a built-server start command PASS.

## Rules

1. Never plain `railway variables` (the staged transcript guard blocks it once installed).
2. When the owner rules that this skill should not do something, add that rule here in the same turn.
