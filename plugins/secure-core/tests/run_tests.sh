#!/usr/bin/env bash
# secure-core tests: ledger contract, UNKNOWN handling, inventory on fixtures.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/test_core.py"
