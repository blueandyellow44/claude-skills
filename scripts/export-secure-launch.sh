#!/usr/bin/env bash
# Export the Secure Launch suite from its durable source into plugins/.
# Edit the source, never these copies; re-run this to refresh them.
# Only git-tracked files inside each plugin folder leave the source, so
# STATE.md, change-tracker.md, validation/ and the source README stay private.
set -euo pipefail
src="${SECURE_LAUNCH_SRC:-$HOME/.claude/local-marketplaces/secure-launch}"
dst="$(cd "$(dirname "$0")/.." && pwd)/plugins"
plugins=(secure-core secure-secrets secure-supply-chain secure-app secure-platform secure-gate)

if [ -n "$(git -C "$src" status --porcelain)" ]; then
  echo "source has uncommitted changes; commit them first" >&2
  exit 1
fi
for p in "${plugins[@]}"; do
  rm -rf "${dst:?}/$p"
  (cd "$src" && git ls-files -z -- "$p" | xargs -0 tar cf -) | tar xf - -C "$dst"
done
echo "exported secure-launch $(git -C "$src" rev-parse --short HEAD): ${plugins[*]}"
