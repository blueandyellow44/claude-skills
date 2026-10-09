#!/usr/bin/env bash
# scan_secrets.sh REPO [DIR ...]
#
# Secret scan that proves its detector first and never prints a value.
#  1. gitleaks must exist (install with `brew install gitleaks` if missing).
#  2. A planted fake Google key and Stripe key in a temp dir must be FOUND,
#     or the scan is refused: a detector is untrusted until seen to fail.
#  3. Scans REPO's whole git history, then each DIR as plain files (build
#     output, untracked folders), every report redacted to nothing.
#  4. Prints counts per rule and file only. Never the match, never the secret.
# Exit: 0 clean, 1 findings, 2 the detector could not be proven or run.
set -uo pipefail
repo="${1:?usage: scan_secrets.sh REPO [DIR ...]}"; shift || true
command -v gitleaks >/dev/null || { echo "gitleaks not installed (brew install gitleaks)"; exit 2; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
# Never let the scanned repo configure its own scan: the suite's config, an empty
# ignore folder, and inline gitleaks:allow comments ignored (Phase 5 audit).
mkdir -p "$work/noignore"
GL_FLAGS=(-c "$(cd "$(dirname "$0")" && pwd)/gitleaks-suite.toml" -i "$work/noignore" --ignore-gitleaks-allow)

mkdir -p "$work/canary"
python3 - "$work/canary/fixture.js" <<'PY'
import random, string, sys
r = random.Random(7)
pick = lambda alphabet, n: "".join(r.choice(alphabet) for _ in range(n))
key = "AIza" + pick(string.ascii_letters + string.digits + "-_", 35)
stripe = "sk_live_" + pick(string.ascii_letters + string.digits, 99)
open(sys.argv[1], "w").write(f'const a = "{key}";\nconst b = "{stripe}";\n')
PY
gitleaks dir "$work/canary" "${GL_FLAGS[@]}" --redact=100 --no-banner -f json -r "$work/canary.json" >/dev/null 2>&1
planted=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$work/canary.json" 2>/dev/null || echo 0)
if [ "$planted" -lt 2 ]; then echo "DETECTOR NOT PROVEN: found $planted of 2 planted keys; scan refused"; exit 2; fi
echo "detector proven: found $planted of 2 planted fake keys"

summarize() { # label report
  python3 - "$1" "$2" <<'PY'
import json, sys, collections
label, path = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(path))
except Exception:
    print(f"{label}: SCAN FAILED (no report)"); sys.exit(3)
print(f"{label}: {len(d)} finding(s)")
for (rule, f), n in collections.Counter((x["RuleID"], x["File"]) for x in d).most_common(40):
    print(f"  {rule}  {f}  x{n}")
sys.exit(1 if d else 0)
PY
}

status=0
# gitleaks always honors a .gitleaksignore found in the scanned source, whatever
# -i says. A repo carrying one is scanned through a throwaway clone without it
# (the real repo is never touched).
scan_src="$repo"
if git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 && [ -e "$repo/.gitleaksignore" ]; then
  git clone -q --no-hardlinks "$repo" "$work/clone" 2>/dev/null && rm -f "$work/clone/.gitleaksignore" && scan_src="$work/clone"
fi
if git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  gitleaks git "$scan_src" "${GL_FLAGS[@]}" --redact=100 --no-banner -f json -r "$work/git.json" >/dev/null 2>&1
  summarize "git history of $repo" "$work/git.json"; rc=$?; [ $rc -eq 3 ] && exit 2; [ $rc -eq 1 ] && status=1
else
  # Not a git repo: there is no history to scan, so scan the files as they are.
  echo "no git history at $repo; scanning its files instead"
  gitleaks dir "$repo" "${GL_FLAGS[@]}" --redact=100 --no-banner -f json -r "$work/git.json" >/dev/null 2>&1
  summarize "files in $repo" "$work/git.json"; rc=$?; [ $rc -eq 3 ] && exit 2; [ $rc -eq 1 ] && status=1
fi
i=0
for d in "$@"; do
  i=$((i+1))
  [ -e "$d" ] || { echo "$d: not found, skipped"; continue; }
  gitleaks dir "$d" "${GL_FLAGS[@]}" --redact=100 --no-banner -f json -r "$work/dir$i.json" >/dev/null 2>&1
  summarize "files in $d" "$work/dir$i.json"; rc=$?; [ $rc -eq 3 ] && exit 2; [ $rc -eq 1 ] && status=1
done
[ $status -eq 1 ] && echo "Classify each hit before calling it a leak: read the surrounding structure with the value masked (hash manifests and lockfiles are common false positives)."
exit $status
