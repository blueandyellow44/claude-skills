#!/bin/bash
# Build and deploy the working tree to a PREVIEW branch of the wallywalks-app Pages
# project (test.wallywalks.app), then check what is served and put wrangler.toml
# back byte for byte.
#
# Dry run by default: prints every step and changes nothing. Add --go to execute.
# Production (main, wallywalks.app) is REFUSED. It is a separate step on the owner's word.
#
# Exit codes: 0 verified; 2 bad argument; 3 refused branch; 4 preflight refused;
#   5 wrangler.toml NOT restored; 6 a served-build check failed; 7 build identity
#   could not be established; 8 production's fingerprint changed during the run.
#
# What a pass means: the preview serves the same asset set, the same two sprites,
# an /api/me, and no-cache sprites; wrangler.toml is byte-identical to before the
# run; production's homepage asset set did not change BETWEEN the start and end
# of this run. It does not show production is "untouched" in any wider sense.
#
# Tests source this file with CW_SOURCE_ONLY=1 and replace fetch()/fetch_status()/
# fetch_headers() with inert mocks; nothing is deployed and no network is used.

# The map repo: CW_PREVIEW_REPO, else CITY_WALKS_REPO. main() refuses to run without one.
REPO="${CW_PREVIEW_REPO:-${CITY_WALKS_REPO:-}}"
PROD_HOST="https://wallywalks.app"
SPRITES=(ferry-building city-hall)

fetch()         { curl -s --max-time 30 "$1"; }
fetch_status()  { curl -s -o /dev/null --max-time 30 -w '%{http_code}' "$1"; }
fetch_headers() { curl -sI --max-time 30 "$1"; }

valid_branch() {   # 0 ok, 3 refused
  case "$1" in
    main|master|production|prod|wallywalks-app)
      echo "REFUSED: '$1' is production. This script deploys previews only." >&2; return 3;;
  esac
  if [[ "$1" =~ ^(test|phone-test-[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?)$ ]]; then return 0; fi
  echo "REFUSED: '$1' is not a preview branch name (test, or phone-test-<lowercase letters, digits, hyphens>)." >&2; return 3
}

# wrangler.toml must equal HEAD: not merely "no unstaged change". A staged edit
# passes `git diff --quiet` and would then be deployed over and lost.
config_is_head() { git -C "$REPO" diff --quiet HEAD -- wrangler.toml; }

save_config()    { SAVED_CONFIG="$(mktemp)"; cp -p "$REPO/wrangler.toml" "$SAVED_CONFIG"; }
restore_config() {   # put the exact pre-run bytes back and prove it; 0 restored, 5 not
  [ -n "${SAVED_CONFIG:-}" ] && [ -f "$SAVED_CONFIG" ] || { echo "FAIL: no saved copy of wrangler.toml to restore from" >&2; return 5; }
  cp -p "$SAVED_CONFIG" "$REPO/wrangler.toml" 2>/dev/null
  if cmp -s "$SAVED_CONFIG" "$REPO/wrangler.toml"; then echo "wrangler.toml: byte-identical to before the run"; return 0; fi
  echo "FAIL: wrangler.toml is NOT restored. The pre-run copy is kept at $SAVED_CONFIG" >&2; return 5
}

assets_of() { grep -o '/_next/static/[A-Za-z0-9_./-]*\.\(js\|css\)' | sort -u; }   # stdin: HTML

# Build identity from what a static export really contains: the hashed chunk and
# css names its homepage loads. (The export has no _buildManifest reference.)
identity_check() {   # $1 host. 0 match, 6 mismatch, 7 cannot establish
  local l s
  l="$( [ -f "$REPO/out/index.html" ] && assets_of < "$REPO/out/index.html" )"
  [ -n "$l" ] || { echo "BUILD IDENTITY: UNKNOWN (out/index.html names no /_next/static assets; is there a build?)"; return 7; }
  s="$(fetch "$1/" | assets_of)"
  [ -n "$s" ] || { echo "BUILD IDENTITY: UNKNOWN (the served page names no /_next/static assets, or did not load)"; return 7; }
  if [ "$l" = "$s" ]; then echo "BUILD IDENTITY: match ($(echo "$l" | wc -l | tr -d ' ') hashed assets)"; return 0; fi
  echo "BUILD IDENTITY: MISMATCH. Local-only: $(comm -23 <(echo "$l") <(echo "$s") | tr '\n' ' ') Served-only: $(comm -13 <(echo "$l") <(echo "$s") | tr '\n' ' ')"
  return 6
}

served_checks() {   # $1 host. Every line affects the result. 0 all pass, 6 any fail
  local rc=0 f L S code cc
  for f in "${SPRITES[@]}"; do
    if [ ! -f "$REPO/out/images/sprites/sf/$f.png" ]; then echo "sprite $f: MISSING from the local build"; rc=6; continue; fi
    L="$(shasum -a 256 "$REPO/out/images/sprites/sf/$f.png" | cut -c1-16)"
    S="$(fetch "$1/images/sprites/sf/$f.png" | shasum -a 256 | cut -c1-16)"
    if [ "$L" = "$S" ]; then echo "sprite $f: match"; else echo "sprite $f: MISMATCH (local $L, served $S)"; rc=6; fi
  done
  code="$(fetch_status "$1/api/me")"
  if [ "$code" = "200" ]; then echo "/api/me: 200"; else echo "/api/me: $code (expected 200; 404 is the build before sign-in)"; rc=6; fi
  cc="$(fetch_headers "$1/images/sprites/sf/${SPRITES[0]}.png" | tr -d '\r' | grep -i '^cache-control:' || true)"
  case "$cc" in *no-cache*) echo "sprite cache-control: no-cache";; *) echo "sprite cache-control: '${cc:-absent}' (expected no-cache; phones will keep stale pieces)"; rc=6;; esac
  return $rc
}

prod_fingerprint() { fetch "$PROD_HOST/" | assets_of | shasum -a 256 | cut -c1-16; }

main() {
  set -uo pipefail
  local BRANCH="test" GO=0 a HOST rc=0 r PROD_BEFORE PROD_AFTER
  for a in "$@"; do case "$a" in --go) GO=1;; --branch=*) BRANCH="${a#--branch=}";; *) echo "unknown argument: $a" >&2; return 2;; esac; done
  valid_branch "$BRANCH" || return $?
  [ -n "$REPO" ] || { echo "REFUSED: set CITY_WALKS_REPO (or CW_PREVIEW_REPO) to the map repo." >&2; return 4; }
  cd "$REPO" || return 4
  HOST="https://test.wallywalks.app"; [ "$BRANCH" = "test" ] || HOST="https://$BRANCH.wallywalks-app.pages.dev"
  run() { echo "+ $*"; if [ "$GO" = 1 ]; then "$@"; fi; }

  echo "== preflight"
  config_is_head || { echo "REFUSED: wrangler.toml differs from HEAD (staged or unstaged). Restore it first: git restore --staged --worktree wrangler.toml" >&2; return 4; }
  grep -q '^name = "wallywalks-app"' wrangler.wallywalks-app.toml || { echo "REFUSED: wrangler.wallywalks-app.toml does not name the wallywalks-app project." >&2; return 4; }
  echo "ROUTE_API_VERSION: $(grep -o 'ROUTE_API_VERSION = "[^"]*"' lib/customWalks.ts)"
  echo "worker route cache key: $(grep -o 'route-foot[^:]*' 'functions/api/[[route]].ts' | head -1)"
  echo "(if the route source or step shape changed since the last deploy, BOTH must change first)"
  if [ "$GO" != 1 ]; then
    echo "== would: npm run build; copy wrangler.wallywalks-app.toml over wrangler.toml; npx wrangler pages deploy out --project-name wallywalks-app --branch $BRANCH; restore wrangler.toml byte for byte; verify $HOST"
    echo "(dry run: nothing was built, deployed or changed. Re-run with --go on the owner's word.)"
    return 0
  fi
  PROD_BEFORE="$(prod_fingerprint)"
  save_config; trap 'restore_config >/dev/null 2>&1' EXIT
  echo "== build"; run npm run build || return 4
  echo "== swap config, deploy branch '$BRANCH'"
  run cp wrangler.wallywalks-app.toml wrangler.toml
  run npx wrangler pages deploy out --project-name wallywalks-app --branch "$BRANCH" || rc=6
  echo "== restore"; restore_config || return 5
  trap - EXIT
  echo "== verify what is served at $HOST"
  identity_check "$HOST"; r=$?; [ $r -ne 0 ] && rc=$r
  served_checks "$HOST" || rc=6
  PROD_AFTER="$(prod_fingerprint)"
  if [ "$PROD_BEFORE" = "$PROD_AFTER" ]; then echo "production homepage asset set: unchanged across this run ($PROD_AFTER)"
  else echo "production homepage asset set CHANGED during this run ($PROD_BEFORE -> $PROD_AFTER)"; rc=8; fi
  [ $rc -eq 0 ] && echo "RESULT: verified" || echo "RESULT: NOT verified (exit $rc). A mismatch right after a deploy can be propagation: re-run the checks once after a minute before reporting."
  return $rc
}

if [ "${CW_SOURCE_ONLY:-0}" != 1 ]; then main "$@"; exit $?; fi
