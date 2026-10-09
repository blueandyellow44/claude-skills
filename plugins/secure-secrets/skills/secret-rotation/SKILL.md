---
name: secret-rotation
description: "Rotate a leaked or aging API key end to end without ever displaying it: per provider (Cloudflare, Railway, Google Cloud, Anthropic, Deepgram, ElevenLabs, Stripe, GitHub PAT, Supabase), where the key is minted, every place it lives (Pages or Worker secret, .dev.vars, GitHub Actions secret, Railway variable), how to store the new value from the clipboard with a parser, redeploy, prove it with one read-only call that prints only the HTTP status, and revoke the old one. Use when the user says 'rotate the key', 'this key leaked', 'replace the API key', or when secret-scan or transcript-secret-guard finds a real credential. Do NOT use it to create a brand-new integration's first key in a console (secret-handling covers the console steps), or to scan for leaks."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# secret-rotation

Every step that touches a value runs through the `secret-handling` skill's no-display rules (screenshots at 0.12 scale or smaller, redacting page reads, the console's own copy button). This skill adds the map of where each key lives and the proof that the new one works.

## Trigger

A key was exposed (transcript, commit, screenshot, chat) or is due for rotation.

## Inputs

- The provider and the variable NAME (never the value).
- The repos and deploy targets that use it: run `security-inventory` and read `secrets_read` for the name, then `grep -rn NAME .github/workflows wrangler.* fly.toml railway.*` in each repo.

## Prerequisites

- The owner's browser, logged in to the provider console (one tab, closed after).
- The owner's word for each live change: the secret put, the redeploy, the revocation of the old key.

## Procedure

1. **Map every home of the key** (provider table: `references/providers.md`). A key missed here breaks the service at revocation.
2. **Mint the new key** in the console per `references/providers.md`, copying it with the console's copy button. Do not screenshot the dialog at full size.
3. **Store it everywhere, from the clipboard:**
   - `.dev.vars` / `.env`: `pbpaste | python3 <base>/../../scripts/store_secret.py .dev.vars NAME` (prints length only; refuses a value that starts with `NAME=`).
   - Cloudflare Pages: `pbpaste | npx wrangler pages secret put NAME --project-name P`, then REDEPLOY (a Pages secret takes effect only at the next deployment, found 2026-10-06).
   - Cloudflare Worker: `pbpaste | npx wrangler secret put NAME`.
   - GitHub Actions: `pbpaste | gh secret set NAME -R owner/repo`.
   - Railway: the dashboard Variables tab (Railway redeploys on change); confirm with `railway variables --kv | grep -c '^NAME='`.
   - Fly: `pbpaste | fly secrets import` is line-based; use `fly secrets set NAME="$(pbpaste)"` (the value is in the process list for an instant, not on screen).
4. **Check the stored shape:** `python3 <base>/../../scripts/check_secret_shape.py .dev.vars`. FAIL on prefix, quotes, whitespace, placeholder or provider-prefix mismatch.
5. **Prove it works:** `python3 <base>/../../scripts/verify_secret.py PROVIDER --file .dev.vars --name NAME` (one free read; prints the status only). Then one live call through the deployed app.
6. **Revoke the old key** in the console, on the owner's word. Then the same live call again: it must still work (proves nothing used the old key).
7. Record the rotation (date, name, homes updated, last four characters only if the console shows them) in the project's notes, and close the todo.

## Outputs

The homes list with each updated, the shape check, the verify status before and after revocation, and the notes line.

## Failure handling

- verify exits 1 (401/403): the stored value is wrong. Run the shape check; re-copy; never paste the value to compare.
- verify exits 3: network or an unexpected status. Not a pass; try the app's own live call.
- A provider whose endpoint the key's scopes cannot read (a restricted ElevenLabs key): use the app's live call as the proof and say so.
- A home found after revocation: the service is down until it is updated; that home goes in `references/providers.md` for next time.

## Verification

`bash <base>/../../tests/run_tests.sh`

The shape check FAILs a `NAME=NAME=` value, a provider-prefix mismatch, an unbalanced quote, a placeholder and trailing whitespace, and PASSes a well-formed file, never printing a value; `store_secret.py` refuses a `NAME=` value and stores a good one at 0600; `verify_secret.py` exits 1 on a refused key, 0 on a good one, 3 on an unset name, and refuses to send a key to a foreign host.

## Rules

1. The value never appears on screen, in a command line you type, or in output.
2. Revocation, redeploys and secret puts are live changes: each needs the owner's word.
3. When the owner rules that this skill should not do something, add that rule here in the same turn.
