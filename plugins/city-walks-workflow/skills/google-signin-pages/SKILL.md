---
name: google-signin-pages
description: "Repeatable checklist for Google sign-in on a Cloudflare Pages app, as set up for wallywalks.app on 2026-10-03: Google Cloud project and consent screen, OAuth web client with origins and redirect URIs per host, Pages secrets for production and preview, the Hono callback routes, local dev on localhost, custom-domain preview, brand verification, and the verification that a stranger cannot read or change another account's data. Use when the owner says 'add Google sign-in', 'set up login', 'sign-in is broken on test', 'redirect_uri_mismatch', 'consent screen shows the wrong name', or a new host or app needs the same setup."
allowed-tools:
  - Bash
  - Read
---

# google-signin-pages

## Goal

Sign-in that works on production, on the preview host and locally, with the consent screen showing the product's name, and data private to each account.

## Source

Built once for wallywalks.app on 2026-10-03 (`.agents/continuation-20261003/LOG.md`, 21:15 onward; routes in the API worker's catch-all route file under `functions/api/`). Steps marked (console) were done in the owner's logged-in Chrome and were not captured as commands; confirm each against the console as you go and correct this file when one differs.

## Checklist

### Google Cloud (console)

1. **Its own project.** One Google Cloud project per product, named for it (`wallywalks-app`). Verify whose product it is before reusing a project: never reuse another product's project. Read the project id back after creating it; a stray empty project was created by mistake once.
2. **Consent screen.** App name as users know it ("Wally Walks"), support email, logo (120 px: `public/images/brand/google-signin-logo-120.png`), home page and privacy policy URLs on the production domain.
3. **Scopes.** `openid`, `email`, `profile` only. Nothing sensitive, so no security review.
4. **Publish: "In production".** Left in "Testing", only hand-added test users can sign in, and testers must not need to be added by hand.
5. **OAuth client, type Web.** Authorized JavaScript origins and redirect URIs for EVERY host that will sign in:
   - production: `https://<domain>` and `https://<domain>/api/auth/callback/google`
   - preview: `https://test.<domain>` and its callback
   - local: the 2026-10-03 session's record says it signed in on an ad hoc server at `http://localhost:3881`. That is NOT the repo's runtime (`npm run demo` is fixed to `http://127.0.0.1:3777`), and the origins registered in the Google console were not re-read when this file was written: open the client in the console and read the list before relying on either. Google treats `localhost` and `127.0.0.1` as different origins.
6. **Brand verification.** Until it passes, the consent screen shows the bare domain and no logo. Needs the live privacy page and domain ownership proof in Search Console (a DNS TXT record). Submitting it is the owner's word.

### Cloudflare Pages

7. **Client id** is public: `GOOGLE_CLIENT_ID` under `[vars]` in the deploy config (`wrangler.wallywalks-app.toml`).
8. **Secrets**, in BOTH environments (production and preview): `GOOGLE_CLIENT_SECRET`, `BETTER_AUTH_SECRET` (signs the session cookie). `npx wrangler pages secret put <NAME> --project-name <project>` for production; the preview environment is set separately. Locally they live in `.dev.vars` (gitignored, mode 0600). Secrets move clipboard to CLI, never through chat or a screenshot.
9. **Preview host on a custom domain.** Add `test.<domain>` from the Pages DASHBOARD (the API path skips the DNS record) and point a CNAME at `test.<project>.pages.dev`. A `*.pages.dev` preview host is a different origin and needs its own entry in step 5.

### Code (Hono worker)

10. `GET /api/auth/google?return=/path` sets a short-lived return cookie and redirects to the callback route; `@hono/oauth-providers` `googleAuth` runs on `/api/auth/callback/google` with state checked; the callback sets an HMAC-signed, httpOnly, SameSite=Lax session cookie; `GET /api/me` returns the user or null with `cache-control: no-store`; `POST /api/auth/signout` clears it.
11. **The account comes from the session only**, never from the request (`space = g:<sub>`). Signed out, as read in the route file on 2026-10-04: `GET /walks` and `GET /notes` return empty; the mutation and generation routes that check the session answer 401 (`POST`/`PUT`/`DELETE /walks...`, `PUT /notes`, `POST /routes/suggest`, `POST /routes/enroute`, `POST /walks/:id/text` and the per-walk photo and sketch routes). `POST /auth/signout` and the lookup routes (`/geocode`, `/place`, `/reverse`, `/route`) do not require a session. Re-read the file for the current list; do not assume "every write".
12. **Return paths must stay on the site.** `safeReturn` rejects anything that does not start with a single `/`, any backslash or control character, and anything that resolves to another origin. Until 2026-10-04 it accepted `/\\example.invalid`, which browsers send to another site (an open redirect after sign-in); fixed in the working tree that day on the owner's word. `tests/return_path_case.py` in this plugin runs the real function from the file. It checks the working tree only: whether a given deploy carries the fix is a separate, live check.
13. A privacy page at `/privacy` that says what is stored (name, email, picture, the walks).

### Verify (unhappy paths first)

14. Signed out: `curl` each session-checked route listed in step 11, expect 401; lists empty. Report the routes actually tried.
15. A forged or tampered cookie: 401.
16. Two accounts: the second cannot read, edit or delete the first's walk (delete answers 404).
17. The full flow in the user's own Chrome on local, then on the preview host: consent shows only name, picture and email; return lands on the page it left.
18. `redirect_uri_mismatch` means step 5 lacks that exact host and path. A 503 "Sign-in is not configured" means a secret is missing in that environment.
19. Delete every test walk and account artifact created.

## Rules

1. Reading the routes in the API route file (the auth block) is obligatory before changing or porting them.
2. Creating the Google project, publishing the consent screen, submitting brand verification and adding DNS records are the owner's actions or need the owner's word; do the rest.
3. Never print a secret. If one lands in a transcript, add a todo to rotate it the same turn.
4. When the owner rules out something this skill does, or a console step differs from this file, correct the file in the same turn.

## Output

The checklist with each line marked done, not done, or the owner's action, and the verification results with what was measured.
