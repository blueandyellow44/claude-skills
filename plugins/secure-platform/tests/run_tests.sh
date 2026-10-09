#!/usr/bin/env bash
# secure-platform tests: one known-bad and one known-good fixture per adapter.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/test_platform.py"
