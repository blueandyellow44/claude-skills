#!/usr/bin/env bash
# Export the Secure Launch suite from its durable source into plugins/.
# Edit the source, never these copies; re-run this to refresh them.
# Only git-tracked files inside each plugin folder leave the source, so
# STATE.md, change-tracker.md, validation/ and the source README stay private.
set -euo pipefail
src="${SECURE_LAUNCH_SRC:-$HOME/.claude/local-marketplaces/secure-launch}"
dst="$(cd "$(dirname "$0")/.." && pwd)/plugins"
plugins=(secure-core secure-secrets secure-supply-chain secure-app secure-platform secure-gate secure-ai)

if [ -n "$(git -C "$src" status --porcelain --untracked-files=no)" ]; then
  echo "source has uncommitted changes; commit them first" >&2
  exit 1
fi
for p in "${plugins[@]}"; do
  rm -rf "${dst:?}/$p"
  (cd "$src" && git ls-files -z -- "$p" | xargs -0 tar cf -) | tar xf - -C "$dst"
done
# Public scrub: the mcp-tool-scope skill credits a named reviewer in the private source. The public copy says
# "a security review"; refuse if the sentence changed, so a new private detail is never published unscrubbed.
f="$dst/secure-app/skills/mcp-tool-scope/SKILL.md"
n=$(grep -cE "from [A-Z][a-z]+ [A-Z][a-z]+'s review of a real MCP app" "$f" || true)
if [ "$n" != "1" ]; then
  echo "mcp-tool-scope scrub: expected the reviewer sentence once, found $n; update this scrub" >&2
  exit 1
fi
perl -pi -e "s/from [A-Z][a-z]+ [A-Z][a-z]+'s review of a real MCP app/from a security review of a real MCP app/" "$f"
echo "exported secure-launch $(git -C "$src" rev-parse --short HEAD): ${plugins[*]}"
