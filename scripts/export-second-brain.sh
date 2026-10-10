#!/usr/bin/env bash
# Export the second-brain plugin from its private source into
# plugins/second-brain, then apply the public scrub.
# Edit the source, never this copy; re-run this to refresh it.
#
#   export-second-brain.sh            assemble, scrub, write plugins/second-brain
#   export-second-brain.sh --raw DIR  assemble only, into DIR (the input to
#                                     `scrub.py make` when the scrub is re-derived)
#
# Two read-only sources: the built plugin, and a handful of operator scripts the
# skills call, which live in the vault and ship under operator/.
# Left behind: the sessions-index skill (it indexes transcripts that only a
# separate, unpublished capture plugin produces), launchd plists, install notes
# for those plists, run logs, a packaged .skill archive, the template-drift
# check (it compares against the private vault), change-tracker.md, backups.
# The scrub (scripts/second-brain-public/scrub.py, patches.json) fails loudly,
# writing nothing, if either source changed under it.
set -euo pipefail
src="${SECOND_BRAIN_SRC:-$HOME/.claude/local-marketplaces/second-brain/second-brain}"
ops="${SECOND_BRAIN_OPERATOR_SRC:-${SECOND_BRAIN_VAULT:-$HOME/vault}/Resources/operator}"
root="$(cd "$(dirname "$0")/.." && pwd)"
dst="$root/plugins/second-brain"
operator_files="vault-vitals.py normalize-wikilinks.py tie-orphans.py todo-mover.py
relocate-misfiled-backups.py capability-candidates.py test_todo_mover.py test_capability_candidates.py"

[ -f "$src/.claude-plugin/plugin.json" ] || { echo "no plugin at $src" >&2; exit 1; }
for f in $operator_files; do
  [ -f "$ops/$f" ] || { echo "no operator script at $ops/$f (set SECOND_BRAIN_OPERATOR_SRC)" >&2; exit 1; }
done

assemble() {
  mkdir -p "$1/operator"
  (cd "$src" && tar cf - \
    --exclude='./skills/sessions-index' --exclude='./skills/morning-agenda/README.md' \
    --exclude='./skills/vault-doctor/INSTALL.md' \
    --exclude='./skills/vault-setup/references/check_template_drift.py' \
    --exclude='change-tracker.md' --exclude='*.plist' --exclude='*.skill' --exclude='*.log' \
    --exclude='.backups' --exclude='*.bak*' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.DS_Store' .) | tar xf - -C "$1"
  for f in $operator_files; do cp "$ops/$f" "$1/operator/$f"; done
  find "$1" -type f -exec chmod 644 {} +
  find "$1" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod 755 {} +
}

if [ "${1:-}" = "--raw" ]; then
  [ -n "${2:-}" ] && [ ! -e "$2" ] || { echo "--raw needs a directory that does not exist yet" >&2; exit 1; }
  assemble "$2"
  echo "raw export written to $2"
  exit 0
fi

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
assemble "$tmp/out"

PYTHONDONTWRITEBYTECODE=1 python3 "$root/scripts/second-brain-public/scrub.py" apply "$tmp/out"

rm -rf "${dst:?}"
mkdir -p "$dst"
(cd "$tmp/out" && tar cf - .) | tar xf - -C "$dst"
echo "exported second-brain $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$dst/.claude-plugin/plugin.json") to $dst"
