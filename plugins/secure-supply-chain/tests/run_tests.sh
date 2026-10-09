#!/usr/bin/env bash
# secure-supply-chain tests: audit triage, pinning, built-code load. Network-free.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/test_supply.py"
