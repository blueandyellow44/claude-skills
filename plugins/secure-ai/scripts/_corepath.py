"""_corepath.py - put secure-core/lib on sys.path.

Identical in every secure-launch plugin (tests/run_all.sh fails if they drift).
Resolves the marketplace layout (<marketplace>/secure-core/lib) and the
installed-cache layout (<cache>/secure-launch/secure-core/<version>/lib).
A missing secure-core exits non-zero, which the orchestrator records as UNKNOWN.
"""
import glob
import os
import sys

_plugin = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_candidates = [os.path.join(_plugin, "..", "secure-core", "lib")]
_candidates += sorted(glob.glob(os.path.join(_plugin, "..", "..", "secure-core", "*", "lib")), reverse=True)
for _c in _candidates:
    if os.path.exists(os.path.join(_c, "ledger.py")):
        sys.path.insert(0, os.path.abspath(_c))
        break
else:
    sys.exit("secure-core/lib not found next to %s: the secure-core plugin is required" % _plugin)
