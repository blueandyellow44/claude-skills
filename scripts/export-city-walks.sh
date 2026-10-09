#!/usr/bin/env bash
# Export the city-walks-workflow plugin from its private source into
# plugins/city-walks-workflow, then apply the public scrub.
# Edit the source, never this copy; re-run this to refresh it.
#
# Left behind: the wally-voice skill (private), change-tracker.md, .backups/,
# tests/results/, *.bak* reference snapshots, __pycache__, *.pyc, .DS_Store.
# Added: the new-city skill from the City Walks Template repo.
# The scrub (scripts/city-walks-public/scrub.py, patches.json) fails loudly,
# writing nothing, if the source changed under it.
set -euo pipefail
src="${CITY_WALKS_SRC:-$HOME/.claude/local-marketplaces/city-walks/city-walks-workflow}"
newcity="${CITY_WALKS_NEW_CITY_SRC:-$HOME/City Walks/.claude/skills/new-city}"
root="$(cd "$(dirname "$0")/.." && pwd)"
dst="$root/plugins/city-walks-workflow"

[ -f "$src/.claude-plugin/plugin.json" ] || { echo "no plugin at $src" >&2; exit 1; }
[ -f "$newcity/SKILL.md" ] || { echo "no new-city skill at $newcity" >&2; exit 1; }

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/out"
(cd "$src" && tar cf - \
  --exclude='./skills/wally-voice' --exclude='./change-tracker.md' --exclude='./.backups' \
  --exclude='./tests/results' --exclude='*.bak*' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.DS_Store' --exclude='*.log' .) | tar xf - -C "$tmp/out"
mkdir -p "$tmp/out/skills/new-city"
(cd "$newcity" && tar cf - --exclude='.DS_Store' .) | tar xf - -C "$tmp/out/skills/new-city"

python3 "$root/scripts/city-walks-public/scrub.py" apply "$tmp/out"

rm -rf "${dst:?}"
mkdir -p "$dst"
(cd "$tmp/out" && tar cf - .) | tar xf - -C "$dst"
echo "exported city-walks-workflow $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$dst/.claude-plugin/plugin.json") to $dst"
