#!/usr/bin/env bash
# secure-app tests: ASVS-lite, fetch, spend, mutation, SSRF trap. Known-bad first.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/test_app.py"
