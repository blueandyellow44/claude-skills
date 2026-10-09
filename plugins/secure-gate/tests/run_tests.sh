#!/usr/bin/env bash
# secure-gate tests: gate decisions, vendoring, pre-push, deploy gate, CI template.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/test_gate.py"
