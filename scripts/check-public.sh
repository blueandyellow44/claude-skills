#!/usr/bin/env bash
# Fail if anything about to be published carries personal paths, vault links,
# private project names, or key-shaped strings. Run before every push.
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail=0
files=$( { git ls-files; git ls-files --others --exclude-standard; } | grep -v '^scripts/check-public.sh$' | sort -u)
pattern='/Users/|Second Brain|~/vault|Tasks/lessons|maxs-coach|litmustimes|wallywalks\.com|sheahan\.ai|Intent Solutions|Jeremy|Bethel|\(Max, 20'
hits=$(printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 grep -nIE "$pattern" 2>/dev/null)
# Obsidian wikilinks render literally on GitHub; only prose files can carry them.
wl=$(printf '%s\n' "$files" | grep -E '\.md$' | tr '\n' '\0' | xargs -0 grep -nE '\[\[[A-Za-z][^]]*\]\]' 2>/dev/null)
hits=$(printf '%s\n%s' "$hits" "$wl" | sed '/^$/d')
if [ -n "$hits" ]; then echo "PRIVATE REFERENCES:"; echo "$hits"; fail=1; fi
junk=$(printf '%s\n' "$files" | grep -E '__pycache__|\.pyc$|\.DS_Store|change-tracker\.md|STATE\.md|/validation/|\.backups/')
if [ -n "$junk" ]; then echo "FILES THAT SHOULD NOT SHIP:"; echo "$junk"; fail=1; fi
if command -v gitleaks >/dev/null; then
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT; printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 tar cf - | tar xf - -C "$tmp"
  gitleaks dir "$tmp" --redact=100 --no-banner -c "$root/scripts/gitleaks-public.toml" >/dev/null 2>&1 || { echo "GITLEAKS FOUND KEY-SHAPED STRINGS (re-run: gitleaks dir <copy> --redact=100 -v)"; fail=1; }
else
  echo "gitleaks not installed: key scan NOT RUN"; fail=1
fi
[ $fail -eq 0 ] && echo "PUBLIC CHECK PASSED ($(printf '%s\n' "$files" | wc -l | tr -d ' ') files)"
exit $fail
