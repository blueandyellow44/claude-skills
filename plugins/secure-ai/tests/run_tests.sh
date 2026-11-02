#!/usr/bin/env bash
# secure-ai tests: static checks and the red-team probe against local mock servers. Known-bad first.
# Prints ONE summary line last: run_all.sh judges each plugin by its final line.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
p=0; f=0
for t in test_ai.py test_redteam.py; do
  out=$(python3 "$here/$t" 2>&1); echo "$out" | sed '$d'
  line=$(echo "$out" | tail -1)
  set -- $line
  case "$line" in *" passed, "*" failed") p=$((p + $1)); f=$((f + $3));; *) f=$((f + 1)); echo "FAIL $t printed no summary: $line";; esac
done
echo "$p passed, $f failed"
[ $f -eq 0 ]
