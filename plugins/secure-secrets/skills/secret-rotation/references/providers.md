# Providers: where each key is minted, where it lives, how to prove it

Console paths are as of 2026-10-08 and drift; if a label differs, find the equivalent and update this file. `verify_secret.py` endpoints are free reads.

| Provider | Mint / roll | Old key | Typical homes | Prove (prints status only) |
|---|---|---|---|---|
| Cloudflare API token | dash.cloudflare.com, My Profile, API Tokens, the token's "Roll" | Roll replaces it at once | `CLOUDFLARE_API_TOKEN` GitHub Actions secret (a Pages deploy workflow), local env for wrangler in CI. `wrangler login` is OAuth, not this token | `verify_secret.py cloudflare --name CLOUDFLARE_API_TOKEN` (`/user/tokens/verify`) |
| Railway | the upstream provider's key, stored as a Railway service variable (dashboard, service, Variables). Account tokens: Account Settings, Tokens | delete in the same screen | Railway service variables (a hosted MCP server) | `railway variables --kv \| grep -c '^NAME='` (presence), then the service's own health call |
| Google Cloud API key | console.cloud.google.com, APIs and Services, Credentials, the key, "Regenerate key", or create a new key with the same API and referrer restrictions | delete the old key after traffic moves | `.dev.vars`, Pages secrets, GitHub Actions | the app's live map call; no free generic endpoint is used here |
| Google service account key | IAM, Service Accounts, the account, Keys, Add key (JSON) | delete the old key id | JSON file outside the repo, GitHub Actions secret | the tool that uses it (`gcloud auth activate-service-account` then a read) |
| Anthropic | console.anthropic.com, Settings, API Keys, Create key | disable, then delete | `.dev.vars`, Pages/Worker secrets, GitHub Actions (a scheduled scoring job), Fly secrets | `verify_secret.py anthropic` (`/v1/models`) |
| Deepgram | console.deepgram.com, the project, API Keys, Create | delete the old key | Pages/Worker secret (a live-audio feature), `.dev.vars` | `verify_secret.py deepgram` (`/v1/projects`) |
| ElevenLabs | elevenlabs.io, Developers, API Keys, Create | delete the old key | `.dev.vars` and Pages secret (audio narration) | `verify_secret.py elevenlabs` (`/v1/models`; a restricted key may 401 here, then use the app's call) |
| Stripe secret key | dashboard.stripe.com, Developers, API keys, the secret key, "Roll key" (offers an expiry for the old key) | expires at the time chosen | Pages secret `STRIPE_SECRET_KEY` | `verify_secret.py stripe` (`/v1/balance`, a read) |
| Stripe webhook secret | Developers, Webhooks, the endpoint, "Roll secret" | expires at the time chosen | Pages secret `STRIPE_WEBHOOK_SECRET` | send a test event from the dashboard; the app must answer 200 |
| GitHub PAT | github.com, Settings, Developer settings, Personal access tokens, the token, "Regenerate token" | replaced at once | GitHub Actions secrets in other repos, local tools | `verify_secret.py github` (`/user`) |
| Supabase | project, Settings, API Keys. New `sb_secret_`/`sb_publishable_` keys rotate one at a time; legacy `anon`/`service_role` JWTs rotate only with the JWT secret (signs everyone out) | revoke the old `sb_secret_` key | Fly secrets, `.env` | the service's own read (`/rest/v1/` with the key) |

Where secrets must NOT live: `wrangler.toml` `[vars]` (plaintext, committed), `fly.toml` `[env]` (committed), any `NEXT_PUBLIC_`/`VITE_` variable (shipped to the browser), `Index.html` of an Apps Script project (use PropertiesService).
