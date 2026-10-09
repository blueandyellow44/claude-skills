---
name: google-apps-script
description: "Google Apps Script adapter of secure-launch (for example, a classroom toolkit): the web app's access level in appsscript.json (anonymous while executing as the deployer is critical), explicit OAuth scopes narrowed to what the code needs, and no API keys in Index.html or .gs files (PropertiesService instead). States what it cannot see: the live deployment's settings and Script Properties. Use when the user says 'is the toolkit safe', 'apps script access', 'oauth scopes', or when secure-launch detects appsscript.json. Do NOT use it to deploy (clasp-deploy) or to patch the app (gas-single-file-patcher)."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# google-apps-script

## Trigger

A repo with `appsscript.json` or `.clasp.json`.

## Inputs

- Repo path (several manifests in one repo are each checked).

## Prerequisites

- secure-core.

## Procedure

1. `python3 <base>/../../scripts/check_gas.py REPO`.
2. `gas.webapp-access`: ANYONE may be intended for a cross-school tool; ask, and record the ruling in `security/accepted.json` if so.
3. `gas.scopes` UNKNOWN: add an explicit `oauthScopes` list, so a scope can be reviewed in a diff.
4. `gas.keys-in-code` FAIL: move the key to Script Properties, rotate it (`secret-rotation`), redeploy with the `clasp-deploy` checklist.

## Outputs

Access, scopes and key results per manifest.

## Failure handling

- The live deployment may still run an older access setting until a new deployment: check the deployment in the Apps Script editor (cannot_see).

## Verification

`bash <base>/../../tests/run_tests.sh`

Known-bad: ANYONE_ANONYMOUS with USER_DEPLOYING (critical), the full drive scope, and a key in Index.html all FAIL, with the key never printed. Known-good: DOMAIN, drive.file, PropertiesService PASS. A manifest without oauthScopes is UNKNOWN.

## Rules

1. When the owner rules that this skill should not do something, add that rule here in the same turn.
