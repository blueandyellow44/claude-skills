#!/usr/bin/env bash
# secure-secrets tests: scan, shape check, staged guard, capture scanner. Known-bad first.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/test_secrets.py"
