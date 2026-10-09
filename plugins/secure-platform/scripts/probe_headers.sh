#!/usr/bin/env bash
# probe_headers.sh URL [URL ...]
#
# Read-only: one HEAD request per URL plus one plain-http request per host.
# Reports which launch headers are present and whether http redirects to https.
# Never sends a body, a cookie or a credential.
# Exit: 0 all present, 1 something missing, 2 a URL did not answer.
set -uo pipefail
[ $# -ge 1 ] || { echo "usage: probe_headers.sh URL [URL ...]"; exit 2; }
status=0
for url in "$@"; do
  h=$(curl -sS -I --max-time 15 "$url" 2>&1) || { echo "== $url: NO ANSWER"; status=2; continue; }
  echo "== $url"
  check() { # name regex
    if printf '%s' "$h" | grep -qiE "$2"; then echo "  ok      $1"; else echo "  MISSING $1"; [ $status -eq 0 ] && status=1; fi
  }
  check "framing control (CSP frame-ancestors or X-Frame-Options)" "^(content-security-policy:.*frame-ancestors|x-frame-options:)"
  check "HSTS (strict-transport-security)" "^strict-transport-security:"
  check "nosniff (x-content-type-options)" "^x-content-type-options:[[:space:]]*nosniff"
  check "referrer-policy" "^referrer-policy:"
  host=$(printf '%s' "$url" | sed -E 's#^https?://([^/]+).*#\1#')
  loc=$(curl -sS -o /dev/null -w "%{http_code} %{redirect_url}" --max-time 15 "http://$host/" 2>/dev/null || echo "000")
  case "$loc" in
    30[178]\ https://*) echo "  ok      http redirects to https ($loc)";;
    *) echo "  MISSING http -> https redirect (got: $loc)"; [ $status -eq 0 ] && status=1;;
  esac
  case "$host" in
    *.app|*.dev|*.page) echo "  note    .${host##*.} is on the browser HSTS preload list: plain http is never loaded there";;
  esac
done
exit $status
