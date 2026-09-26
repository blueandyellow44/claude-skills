#!/usr/bin/env python3
"""Tests for check_draft.py. Run: python3 test_check_draft.py (stdlib only, exits non-zero on failure)."""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_draft as cd  # noqa: E402

# A draft built to trip the sheet: stock phrases, an abstraction leak, a negation reveal pair,
# three verdict landings in a row, prestige words used past the cap, and a summing-up close.
BAD = """---
title: fixture
---
# The real problem

At the end of the day, most teams do not have a tooling problem. It is essentially a habit problem, and the weight of it shows up every Monday. This is not a plan. It is a wish.

The weight of the old process is quiet. People work around it rather than through it. That is the whole of it.

We tried a new board and a new meeting and a new owner for the weekly numbers. Nobody changed how they worked. The weight stayed.

It is worth noting that the fix was never software, only attention. And that is the real lesson.
"""

PLAIN = """# Monday

Ana opens the sheet at eight. She fills the three columns she owns and leaves the fourth blank, because the vendor has not sent the invoice.

By ten the invoice arrives. She pastes the total, checks it against the purchase order, and sends the sheet to Dev with one line: two dollars off, my rounding.

Dev fixes the rounding and forwards it to finance before lunch.
"""


def check(cond, msg, failures):
    if not cond:
        failures.append(msg)


def main():
    failures = []

    bad = cd.build_sheet(BAD)
    check(any(t == "at the end of the day" for t, _ in bad["stock_phrases"]), "stock phrase missed", failures)
    check(any(t == "essentially" for t, _ in bad["abstraction"]), "abstraction leak missed", failures)
    check(bad["negation_reveals"]["pairs"] >= 1, "negate-then-reveal pair missed", failures)
    check(any(t == "weight" and c >= 3 for t, c in bad["diction"]), "diction frequency missed", failures)
    check(bad["closing"], "closing suspicion missed", failures)
    check(bad["verdict_landings"]["landings"] >= 3, "verdict landings under-counted", failures)
    check("title" not in json.dumps(bad["stock_phrases"]), "front matter leaked into the body", failures)

    plain = cd.build_sheet(PLAIN)
    check(not plain["stock_phrases"], f"false stock phrase: {plain['stock_phrases']}", failures)
    check(not plain["abstraction"], f"false abstraction: {plain['abstraction']}", failures)
    check(plain["negation_reveals"]["total"] == 0, "false negation reveal", failures)
    check(not plain["closing"], f"false closing flag: {plain['closing']}", failures)

    empty = cd.build_sheet("")
    check(empty["words"] == 0 and empty["verdict_landings"]["paragraphs"] == 0,
          "empty draft not handled", failures)

    script = os.path.join(HERE, "check_draft.py")
    with tempfile.TemporaryDirectory() as tmp:
        missing = subprocess.run([sys.executable, script, "--draft", os.path.join(tmp, "nope.md")],
                                 capture_output=True, text=True)
        check(missing.returncode == 2, f"unreadable draft should exit 2, got {missing.returncode}", failures)

        path, out = os.path.join(tmp, "bad.md"), os.path.join(tmp, "sheet.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(BAD)
        ok = subprocess.run([sys.executable, script, "--draft", path, "--json", out,
                             "--diction", os.path.join(tmp, "absent.txt")], capture_output=True, text=True)
        check(ok.returncode == 0, f"readable draft should exit 0, got {ok.returncode}: {ok.stderr}", failures)
        check("could not read" in ok.stdout, "unreadable --diction list not reported", failures)
        check(os.path.exists(out) and json.load(open(out))["words"] > 0, "JSON sheet not written", failures)

    for f in failures:
        print("FAIL:", f)
    print(f"{'FAILED' if failures else 'passed'}: {len(failures)} failure(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
