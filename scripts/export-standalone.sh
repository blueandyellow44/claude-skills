#!/usr/bin/env bash
# Export three standalone plugins from their private sources into plugins/,
# then apply the public scrub:
#   plugins/youtube-recut   the youtube-recut plugin
#   plugins/skill-toolkit   the skill-builder skill only
#   plugins/news-scoring    litmus-editorial-analyzer and ph-balance-scorer
# Edit the sources, never these copies; re-run this to refresh them.
#
# Left behind: change-tracker.md, .backups/, .history/, STATE.md, tests/results/,
# *.bak*, __pycache__, *.pyc, .DS_Store, logs, media (video, audio, subtitles),
# the recut plugin's brand presets (a channel's identity; the public copy gets a
# placeholder preset from the scrub), and every other skill in the source plugins.
# The scrub (scripts/standalone-public/scrub.py, patches.json) fails loudly,
# writing nothing, if any source file changed under it.
#
#   export-standalone.sh              export, scrub, replace the three plugin folders
#   export-standalone.sh --raw <dir>  write the unscrubbed copy to <dir> and stop
#                                     (the input for `scrub.py make`; keep it out of the repo)
set -euo pipefail
recut="${YOUTUBE_RECUT_SRC:-$HOME/.claude/local-marketplaces/second-brain/youtube-recut}"
builder="${SKILL_BUILDER_SRC:-$HOME/.claude/local-marketplaces/second-brain/skill-forge/skills/skill-builder}"
litmus="${LITMUS_ANALYZER_SRC:-$HOME/Political Ap/skills/litmus-editorial-analyzer}"
ph="${PH_SCORER_SRC:-$HOME/Political Ap/skills/ph-balance-scorer}"
ph_installed="${PH_SCORER_INSTALLED:-$HOME/.claude/skills/ph-balance-scorer}"
root="$(cd "$(dirname "$0")/.." && pwd)"
plugins=(youtube-recut skill-toolkit news-scoring)

[ -f "$recut/.claude-plugin/plugin.json" ] || { echo "no plugin at $recut" >&2; exit 1; }
for d in "$builder" "$litmus" "$ph"; do
  [ -f "$d/SKILL.md" ] || { echo "no skill at $d" >&2; exit 1; }
done
# The scorer exists in two places. They must agree, or the choice is not ours to make.
if [ -f "$ph_installed/SKILL.md" ] && ! cmp -s "$ph/SKILL.md" "$ph_installed/SKILL.md"; then
  echo "ph-balance-scorer differs between $ph and $ph_installed; set PH_SCORER_SRC to the one to publish and PH_SCORER_INSTALLED to the same path" >&2
  exit 1
fi

copy() { # copy <src> <dst> [more tar excludes], leaving junk, state and media behind
  local src="$1" dst="$2"; shift 2
  mkdir -p "$dst"
  (cd "$src" && tar cf - "$@" \
    --exclude='./change-tracker.md' --exclude='change-tracker.md' --exclude='.backups' --exclude='.history' \
    --exclude='STATE.md' --exclude='./tests/results' --exclude='*.bak*' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.DS_Store' --exclude='*.log' --exclude='*.tmp' \
    --exclude='*.mp4' --exclude='*.mov' --exclude='*.mkv' --exclude='*.wav' --exclude='*.mp3' --exclude='*.m4a' \
    --exclude='*.aiff' --exclude='*.vtt' --exclude='*.srt' --exclude='*.ass' .) | tar xf - -C "$dst"
}

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
copy "$recut" "$tmp/out/youtube-recut" --exclude='./skills/youtube-recut/assets/presets'
copy "$builder" "$tmp/out/skill-toolkit/skills/skill-builder"
copy "$litmus" "$tmp/out/news-scoring/skills/litmus-editorial-analyzer"
copy "$ph" "$tmp/out/news-scoring/skills/ph-balance-scorer"

if [ "${1:-}" = "--raw" ]; then
  [ -n "${2:-}" ] || { echo "usage: $0 --raw <dir>" >&2; exit 1; }
  raw="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$2")"
  case "$raw/" in "$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$root")"/*) echo "refusing to write the unscrubbed copy inside the repo" >&2; exit 1;; esac
  rm -rf "${raw:?}"; mkdir -p "$raw"; (cd "$tmp/out" && tar cf - .) | tar xf - -C "$raw"
  echo "raw (UNSCRUBBED, private) copy written to $raw"; exit 0
fi

python3 "$root/scripts/standalone-public/scrub.py" apply "$tmp/out"

for p in "${plugins[@]}"; do
  rm -rf "${root:?}/plugins/$p"
  mkdir -p "$root/plugins/$p"
  (cd "$tmp/out/$p" && tar cf - .) | tar xf - -C "$root/plugins/$p"
done
ver() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$root/plugins/$1/.claude-plugin/plugin.json"; }
for p in "${plugins[@]}"; do echo "exported $p $(ver "$p") to $root/plugins/$p"; done
