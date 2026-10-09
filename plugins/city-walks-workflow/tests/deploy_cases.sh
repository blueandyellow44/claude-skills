#!/bin/bash
# Failure-path tests for preview_deploy.sh. Fixture repo in a temp dir, transports mocked,
# never --go: nothing is built, deployed, fetched or swapped in the real repo.
SCRIPT="$1"; LEGACY="${2:-}"
T="$(mktemp -d)"; F="$T/repo"; mkdir -p "$F/out/images/sprites/sf" "$F/lib" "$F/functions/api"
( cd "$F" && git init -q && printf 'name = "placeholder"\n' > wrangler.toml && printf 'name = "wallywalks-app"\n' > wrangler.wallywalks-app.toml \
  && echo 'const ROUTE_API_VERSION = "foot2";' > lib/customWalks.ts && echo 'route-foot-v2:' > 'functions/api/[[route]].ts' \
  && git add -A && git -c user.email=t@t -c user.name=t commit -qm init )
HTML='<script src="/_next/static/chunks/main-app-aaa.js"></script><link href="/_next/static/css/bbb.css">'
echo "$HTML" > "$F/out/index.html"; echo ferry > "$F/out/images/sprites/sf/ferry-building.png"; echo hall > "$F/out/images/sprites/sf/city-hall.png"
bad=0; case_() { if [ "$2" = "$3" ]; then echo "ok   $1 (exit $2)"; else echo "FAIL $1: exit $2, want $3"; bad=$((bad+1)); fi; }

if [ "$LEGACY" = "--legacy" ]; then
  # the audited defect: a STAGED change to wrangler.toml passes the old preflight as "identical to HEAD"
  ( cd "$F" && printf 'name = "staged-edit"\n' > wrangler.toml && git add wrangler.toml )
  out="$(cd "$F" && git diff --quiet -- wrangler.toml && echo 'OLD preflight: passes'; git -C "$F" diff --quiet HEAD -- wrangler.toml || echo 'but wrangler.toml differs from HEAD')"
  echo "LEGACY staged wrangler.toml -> $out" | tr '\n' ' '; echo
  grep -c "_buildManifest" "${CITY_WALKS_REPO:?set CITY_WALKS_REPO}/out/index.html" | sed 's/^/LEGACY build-id regex (_buildManifest) matches in the real exported homepage: /'
  grep -n 'RC:-0\|exit "\${RC' "$SCRIPT" | head -2 | sed 's/^/LEGACY only the build-id line sets the exit code: /'
  exit 0
fi

export CW_SOURCE_ONLY=1 CW_PREVIEW_REPO="$F"; source "$SCRIPT"
SERVED_HTML="$HTML"; SERVED_FERRY=ferry; SERVED_HALL=hall; ME=200; CC="cache-control: no-cache"
fetch() { case "$1" in */images/sprites/sf/ferry-building.png) echo "$SERVED_FERRY";; */images/sprites/sf/city-hall.png) echo "$SERVED_HALL";; *) echo "$SERVED_HTML";; esac; }
fetch_status() { echo "$ME"; }
fetch_headers() { printf 'HTTP/2 200\r\n%s\r\n' "$CC"; }

for b in main master production prod wallywalks-app 'test; rm -rf x' 'phone-test-' 'phone-test-UPPER' '../main' 'test main' ''; do valid_branch "$b" 2>/dev/null; case_ "branch refused: '$b'" $? 3; done
for b in test phone-test-20261004 phone-test-a; do valid_branch "$b"; case_ "branch accepted: '$b'" $? 0; done

config_is_head; case_ "clean wrangler.toml equals HEAD" $? 0
( cd "$F" && printf 'name = "staged-edit"\n' > wrangler.toml && git add wrangler.toml )
config_is_head; case_ "STAGED wrangler.toml is not HEAD -> refused" $? 1
main > /dev/null 2>&1; case_ "dry run with staged wrangler.toml -> preflight refuses" $? 4
( cd "$F" && git reset -q --hard )

save_config; printf 'name = "wallywalks-app"\n' > "$F/wrangler.toml"; restore_config > /dev/null; case_ "restore puts the pre-run bytes back" $? 0
cmp -s "$SAVED_CONFIG" "$F/wrangler.toml"; case_ "...and they are byte-identical" $? 0
save_config; printf 'swapped\n' > "$F/wrangler.toml"; chmod 444 "$F/wrangler.toml"; chmod 555 "$F"; restore_config > /dev/null 2>&1; r=$?; chmod 755 "$F"; chmod 644 "$F/wrangler.toml"; case_ "restore that cannot write -> exposed" $r 5
( cd "$F" && git checkout -q -- wrangler.toml )
SAVED_CONFIG=""; restore_config > /dev/null 2>&1; case_ "restore with no saved copy -> exposed" $? 5

identity_check https://x > /dev/null; case_ "identity: exact matching HTML" $? 0
SERVED_HTML='<script src="/_next/static/chunks/main-app-OLD.js"></script><link href="/_next/static/css/bbb.css">'; identity_check https://x > /dev/null; case_ "identity: one asset differs" $? 6
SERVED_HTML='<html>no assets</html>'; identity_check https://x > /dev/null; case_ "identity: served page names no assets" $? 7
SERVED_HTML="$HTML"; mv "$F/out/index.html" "$F/out/index.bak"; identity_check https://x > /dev/null; case_ "identity: no local build" $? 7
echo '<html>bare</html>' > "$F/out/index.html"; identity_check https://x > /dev/null; case_ "identity: local page names no assets" $? 7
mv "$F/out/index.bak" "$F/out/index.html"
SERVED_HTML="$HTML<script src=\"/_next/static/chunks/extra-ccc.js\"></script>"; identity_check https://x > /dev/null; case_ "identity: served has an extra asset" $? 6
SERVED_HTML="$HTML"

served_checks https://x > /dev/null; case_ "served checks: all good" $? 0
SERVED_FERRY=other; served_checks https://x > /dev/null; case_ "served checks: sprite mismatch fails the run" $? 6; SERVED_FERRY=ferry
ME=404; served_checks https://x > /dev/null; case_ "served checks: /api/me 404 fails the run" $? 6; ME=200
CC="cache-control: max-age=14400"; served_checks https://x > /dev/null; case_ "served checks: cached sprites fail the run" $? 6
CC=""; served_checks https://x > /dev/null; case_ "served checks: no cache-control header fails the run" $? 6; CC="cache-control: no-cache"
main --branch=main > /dev/null 2>&1; case_ "main() refuses production" $? 3
main --bogus > /dev/null 2>&1; case_ "main() rejects an unknown argument" $? 2
main > /dev/null 2>&1; case_ "main() dry run on a clean fixture" $? 0
( cd "$F" && git diff --quiet HEAD ); case_ "dry run left every tracked file in the fixture unchanged" $? 0
rm -rf "$T"; echo; echo "cases wrong: $bad"; exit $bad
