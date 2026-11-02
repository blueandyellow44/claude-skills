"""names.py - is this env var NAME a credential? One answer for every adapter.

Phase 9 (2026-11-01) merged two copies: check_cloudflare.secret_name (whole-segment
and suffix vocabulary, public-by-design allowlists, the `browser` flag, shared with
check_nextjs) and check_fly_supabase.secret_name (word list, setting suffixes,
database URL names, value shapes). Where the copies disagreed, the merge keeps the
reading that both plugins' unit tests and the full bench accept:

- A SETTING SUFFIX cancels the name (fly rule, now everywhere): PRIVATE_KEY_PATH,
  SECRET_KEY_ID, PASSWORD_MIN_LENGTH, CLIENT_SECRET_FILE name a setting ABOUT a secret,
  not the secret. The cloudflare copy said True to these because a strong segment
  (PRIVATE_KEY, SECRET) appeared anywhere.
- A DATABASE URL name is a secret (fly rule, now everywhere): DATABASE_URL, REDIS_URL,
  PG_DSN carry a password in the value, so one in wrangler [vars] or behind a browser
  prefix is a leak. The cloudflare copy had no such rule.
- PUBLIC-BY-DESIGN names are public in every config (cloudflare rule, now everywhere):
  MAPBOX_TOKEN and *_ANON_KEY / *_SITE_KEY / *_PUBLISHABLE_KEY / *_PUBLIC_KEY, plus a
  PUBLIC or PUBLISHABLE segment anywhere. The fly copy called MAPBOX_TOKEN a secret and
  only let ANON/SITE/PUBLIC/PUBLISHABLE cancel the word right after them.
- The public allowlist is tested BEFORE the database rule and the secret vocabulary: an
  author who writes PUBLIC_ in a name has declared it public.
- Weak words are suffixes, never substrings and never middle segments (cloudflare rule):
  KEY, TOKEN, SALT, PRIVATE, API_KEY, ACCESS_KEY, AUTH_TOKEN, ACCESS_TOKEN as the last
  segment or the last pair. The fly copy counted KEY, TOKEN, PRIVATE anywhere unless a
  listed setting suffix followed (ACCESS_TOKEN_LIFETIME, KEY_VALUE, PRIVATE_NOTES were
  secrets there). The fly words PASS, PWD and APIKEY join the suffix set (DB_PASS,
  REDIS_PWD, STRIPE_APIKEY), so nothing the fly copy's tests caught is lost.
- Strong words count anywhere as a whole segment or pair (cloudflare rule, kept): SECRET,
  SECRETS, PASSWORD, PASSWD, PASSCODE, CREDENTIAL(S), DSN, PRIVATE_KEY, SERVICE_ROLE,
  CLIENT_SECRET, SIGNING_KEY, SECRET_KEY.
- `browser=True` (a name a bundler ships, prefix already stripped) treats Google's
  referrer-restricted Maps key names as public; the same name in wrangler [vars] or fly
  [env] is a server key and stays a secret (cloudflare rule, kept).
- `value` (fly rule, kept) is read only to recognize a key shape or a URL password; it is
  never returned, printed or stored. The cloudflare callers pass no value.

Never reads a value for any other purpose. KEYBOARD_LAYOUT, MAX_TOKENS and
SESSION_TOKEN_TTL_SECONDS are config, not credentials (bench decoys 2026-11-01).
"""
import re

import ledger

# Strong: a credential wherever the segment (or adjacent pair) appears.
SECRET_SEGMENTS = {"SECRET", "SECRETS", "PASSWORD", "PASSWD", "PASSCODE", "CREDENTIAL", "CREDENTIALS", "DSN",
                   "PRIVATE_KEY", "SERVICE_ROLE", "CLIENT_SECRET", "SIGNING_KEY", "SECRET_KEY"}
# Weak: a credential only as the last segment or the last pair.
SECRET_SUFFIXES = {"KEY", "TOKEN", "SALT", "API_KEY", "ACCESS_KEY", "AUTH_TOKEN", "ACCESS_TOKEN", "PRIVATE",
                   "PASS", "PWD", "APIKEY"}
# Public by design: the provider documents the browser as the value's home and
# restricts it by domain or scope server-side. A publishable/site/anon key or a
# PUBLIC_ segment is meant to ship; Mapbox's public token (pk., URL-restricted)
# is named NEXT_PUBLIC_MAPBOX_TOKEN in Mapbox's own Next.js guide.
PUBLIC_SUFFIXES = {"SITE_KEY", "ANON_KEY", "PUBLISHABLE_KEY", "PUBLIC_KEY"}
PUBLIC_SEGMENTS = {"PUBLIC", "PUBLISHABLE"}
PUBLIC_NAMES = {"MAPBOX_TOKEN", "MAPBOX_ACCESS_TOKEN"}
# Public only under a browser prefix (NEXT_PUBLIC_, VITE_): Google documents browser Maps keys as public and
# referrer-restricted, while the same name in wrangler [vars] or fly [env] is a server key and stays a secret
# (Phase 8, 2026-11-01).
BROWSER_PUBLIC_NAMES = {"GOOGLE_MAPS_API_KEY", "GOOGLE_MAPS_KEY", "MAPS_API_KEY", "MAPS_KEY"}
# A name ending in one of these holds a setting ABOUT a secret, not the secret.
SETTING_SUFFIX = {"ISSUER", "URL", "URI", "ENDPOINT", "HOST", "ID", "NAME", "PREFIX", "SUFFIX", "TTL", "SECONDS", "MS", "MINUTES", "HOURS", "DAYS",
                  "LENGTH", "LEN", "SIZE", "COUNT", "LIMIT", "MAX", "MIN", "HEADER", "AUDIENCE", "AUD", "ALGORITHM", "ALG", "PATH", "FILE", "DIR",
                  "EXPIRY", "EXPIRES", "EXPIRATION", "ENABLED", "REQUIRED", "TYPE", "MODE", "VERSION", "PROPERTY", "LAYOUT", "FORMAT", "SCHEME",
                  "REGION", "BUCKET", "TABLE", "ROTATION", "POLICY", "HINT", "LABEL", "FIELD", "PARAM", "COOKIE", "STORE", "PROVIDER", "KID"}
# A connection string carries its password: DATABASE_URL, REDIS_URL, PG_DSN, MONGODB_URI.
DB_URL = re.compile(r"(?:^|_)(?:DATABASE|DB|POSTGRES|POSTGRESQL|PG|MYSQL|MONGO|MONGODB|REDIS|AMQP|RABBITMQ|KAFKA|NEON|CONNECTION)_?(?:URL|URI|DSN|STRING)$")
URL_PASSWORD = re.compile(r"://[^/\s:@'\"]+:[^@\s/'\"]+@")


def secret_name(name, value=None, browser=False):
    """True when an env/var NAME is shaped like a credential (see the module docstring for the rules).
    `value`, when given, is read only to recognize a key shape or a URL password and is never returned.
    `browser=True` judges a name a bundler ships to the browser (the prefix already stripped)."""
    if value and (any(p.search(value) for p in ledger.SECRET_SHAPES) or URL_PASSWORD.search(value)):
        return True
    n = name.upper().strip()
    segs = [s for s in n.split("_") if s]
    if not segs:
        return False
    if browser and n in BROWSER_PUBLIC_NAMES:
        return False
    if n in PUBLIC_NAMES or set(segs) & PUBLIC_SEGMENTS or any(n == s or n.endswith("_" + s) for s in PUBLIC_SUFFIXES):
        return False
    if DB_URL.search(n):
        return True
    if segs[-1] in SETTING_SUFFIX:
        return False
    pairs = {"_".join(segs[i:i + 2]) for i in range(len(segs) - 1)}
    if set(segs) & SECRET_SEGMENTS or pairs & SECRET_SEGMENTS:
        return True
    return segs[-1] in SECRET_SUFFIXES or "_".join(segs[-2:]) in SECRET_SUFFIXES
