#!/usr/bin/env bash
# find_embedders.sh HOST DIR [DIR ...]
#
# Before tightening frame-ancestors: find every page in your own repos that
# puts HOST inside an <iframe>, so the policy keeps them working. On
# 2026-10-07 a portfolio site's demos page framed a walking-tour app, which
# deploys the same _headers file as a production map app. Skips node_modules, .git, build output and
# .backups. Prints file:line only.
set -uo pipefail
host="${1:?usage: find_embedders.sh HOST DIR [DIR ...]}"; shift
[ $# -ge 1 ] || { echo "usage: find_embedders.sh HOST DIR [DIR ...]"; exit 2; }
esc=$(printf '%s' "$host" | sed 's/\./\\./g')
found=0
for d in "$@"; do
  [ -d "$d" ] || continue
  while IFS= read -r line; do echo "$line"; found=1; done < <(
    /usr/bin/grep -rInE --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next \
      --exclude-dir=out --exclude-dir=dist --exclude-dir=.backups --exclude-dir=.open-next \
      "<iframe[^>]*${esc}" "$d" 2>/dev/null | cut -c1-200)
done
[ $found -eq 0 ] && echo "no page frames $host in the given folders"
exit 0
