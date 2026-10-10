#!/usr/bin/env python3
# vendored by the vault-setup skill, 2026-08-18. Generic — builds its own
# temp vaults, no changes needed for a fresh vault.
"""test_vault_audit.py — seeded known-bad proofs for every vault-audit.py check.

A detector is untrusted until observed to FAIL on a known-bad state. Each test
seeds the exact defect its check exists for, asserts the check fires, then
asserts a clean seed stays quiet. Run: python3 test_vault_audit.py
"""

import importlib.util
import json
import os
import shutil
import sys
import time
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vault_audit", os.path.join(HERE, "vault-audit.py"))
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)


def seed_vault(tmp):
    """Minimal CLEAN vault: every check should stay quiet on this."""
    os.makedirs(os.path.join(tmp, "Projects", "Demo"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "Tasks"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "_inbox", "_processed"), exist_ok=True)
    w(tmp, "CLAUDE.md", "# root\nDemo project listed here.\n")
    w(tmp, "Rules-of-Engagement.md", "# roe\n")
    w(tmp, "Projects/CLAUDE.md", "# projects routing\n")
    w(tmp, "Projects/Projects.md", "| [[Demo]] |\n")
    w(tmp, "Tasks/CLAUDE.md", "# tasks routing\n")
    w(tmp, "_inbox/CLAUDE.md", "# inbox routing\n")
    w(tmp, "Projects/Demo/Demo.md",
      "---\nstatus: active\nlast_touched: 2026-08-18\nnext_step: |-\n  none\n---\n# Demo\n")
    w(tmp, "Tasks/todo.md", "# todo\n\n## Active\n\n- [ ] one open thing\n\n## Backlog\n")
    w(tmp, "Tasks/lessons.md", "# lessons\n\n## 2026-08-18\n\n### [T] Rule: x\n\nbody\n")
    # The Obsidian layer. A clean vault is one a PERSON can open, so the
    # baseline carries a full .obsidian/ — otherwise obsidian_layer would fire
    # on the clean seed and the "stays quiet" half of every run is a lie.
    w(tmp, ".obsidian/core-plugins.json", '{"graph": true, "bases": true}\n')
    w(tmp, ".obsidian/app.json", '{"newLinkFormat": "shortest"}\n')
    w(tmp, ".obsidian/appearance.json", '{"enabledCssSnippets": ["vault-home"]}\n')
    w(tmp, ".obsidian/graph.json", '{"showOrphans": false}\n')
    w(tmp, ".obsidian/daily-notes.json", '{"folder": "Daily"}\n')
    w(tmp, ".obsidian/templates.json", '{"folder": "Resources/templates"}\n')
    w(tmp, ".obsidian/workspace.json", '{"lastOpenFiles": ["Home.md"]}\n')
    w(tmp, ".obsidian/snippets/vault-home.css", "/* x */\n")
    w(tmp, "Home.md", "---\ncssclasses:\n  - home\n---\n# Home\n")
    return tmp


def w(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def hits(findings, check, needle=""):
    return [f for f in findings if f["check"] == check and needle in (f["path"] + f["message"])]


def check_name_for(case):
    """Map a case name like `hub_yaml_broken` to its check, `hub_yaml`.

    Resolved against the real CHECKS registry rather than by stripping a
    hardcoded list of name suffixes. The suffix-stripping this replaced
    silently resolved any unrecognised case name to a check that does not
    exist, so `hits()` matched nothing and the case reported "did NOT fire"
    while the finding it wanted was sitting in the results. A test harness
    that fails closed on a naming convention is a harness that quietly
    stops testing whatever it cannot parse.
    """
    matches = [c for c in va.CHECKS if case == c or case.startswith(c + "_")]
    if not matches:
        raise AssertionError(
            f"case '{case}' does not name a registered check; "
            f"prefix it with one of: {sorted(va.CHECKS)}")
    return max(matches, key=len)


def run_all(tmp_factory):
    import tempfile
    results = {}
    checks = [
        ("root_files",
         lambda v: w(v, "stray-notes.md", "x"),
         lambda v: va.check_root_files(v), "stray-notes.md"),
        ("routing",
         lambda v: os.makedirs(os.path.join(v, "NewArea"), exist_ok=True),
         lambda v: va.check_routing(v), "NewArea/"),
        ("obsidian_layer_absent",
         lambda v: shutil.rmtree(os.path.join(v, ".obsidian")),
         lambda v: va.check_obsidian_layer(v), ".obsidian/"),
        ("obsidian_layer_no_core_plugins",
         lambda v: os.remove(os.path.join(v, ".obsidian", "core-plugins.json")),
         lambda v: va.check_obsidian_layer(v), "core-plugins.json"),
        ("obsidian_layer_partial",
         lambda v: os.remove(os.path.join(v, ".obsidian", "daily-notes.json")),
         lambda v: va.check_obsidian_layer(v), "daily-notes.json"),
        ("obsidian_layer_dangling_snippet",
         lambda v: os.remove(os.path.join(v, ".obsidian", "snippets", "vault-home.css")),
         lambda v: va.check_obsidian_layer(v), "vault-home.css"),
        ("obsidian_layer_dangling_home",
         lambda v: os.remove(os.path.join(v, "Home.md")),
         lambda v: va.check_obsidian_layer(v), "Home.md"),
        ("canon_flow",
         # One baseline row exactly one window back, tiny; the live file is
         # huge. The check appends today's row itself, so the pair it compares
         # is (baseline, today). Dates are computed relative to today rather
         # than hardcoded: growth is normalized per CANON_FLOW_WINDOW_DAYS, so
         # a fixed past date would divide the delta by an ever-growing span and
         # this case would silently stop firing as real time passed.
         lambda v: (w(v, "Resources/operator/canon-size-history.jsonl",
                      json.dumps({
                          "date": (date.today() - timedelta(
                              days=va.CANON_FLOW_WINDOW_DAYS)).isoformat(),
                          "sizes": {"Rules-of-Engagement.md": 1_000}}) + "\n"),
                    w(v, "Rules-of-Engagement.md", "x" * 60_000)),
         lambda v: va.check_canon_flow(v), "the admission gate is leaking"),
        ("canon_rule_count",
         lambda v: w(v, "Rules-of-Engagement.md",
                     "# roe\n" + "".join(f"- **Rule {i}.** body\n" for i in range(160))),
         lambda v: va.check_canon_rule_count(v), "discrete rules"),
        ("roe_sunset",
         lambda v: w(v, "Rules-of-Engagement.md",
                     "# roe\n- **An ancient rule (2020-01-01).** body\n"),
         lambda v: va.check_roe_sunset(v), "older than"),
        ("rule_rent",
         lambda v: w(v, "Resources/operator/rule-recurrences.jsonl",
                     json.dumps({"date": "2026-08-01", "rule": "Ground the clock"}) + "\n"
                     + json.dumps({"date": "2026-08-02", "rule": "Ground the clock"}) + "\n"),
         lambda v: va.check_rule_rent(v), "recurred 2x"),
        ("hub_triangle_no_hub",
         lambda v: os.makedirs(os.path.join(v, "Projects", "Ghost"), exist_ok=True),
         lambda v: va.check_hub_triangle(v), "Projects/Ghost/"),
        ("hub_triangle_off_board",
         lambda v: w(v, "Projects/Loner/Loner.md",
                     "---\nstatus: active\nlast_touched: 2026-08-18\nnext_step: n\n---\n"),
         lambda v: va.check_hub_triangle(v), "Projects/Loner/"),
        ("hub_yaml_broken",
         lambda v: w(v, "Projects/Demo/Demo.md",
                     "---\nstatus: active\nnext_step: multi\n  line breaks: yaml\n---\n# Demo\n"),
         lambda v: va.check_hub_yaml(v), "Projects/Demo/Demo.md"),
        ("hub_yaml_missing_field",
         lambda v: w(v, "Projects/Demo/Demo.md", "---\nstatus: active\n---\n# Demo\n"),
         lambda v: va.check_hub_yaml(v), "next_step"),
        ("hub_log_lag",  # Log entry newer than last_touched, both heading shapes
         lambda v: w(v, "Projects/Demo/Demo.md",
                     "---\nstatus: active\nlast_touched: 2026-08-18\nnext_step: |-\n  none\n---\n"
                     "# Demo\n\n## Log\n\n- **2026-08-10 (old)**: x\n### 2026-09-01 (hand wrap)\nbody\n"),
         lambda v: va.check_hub_log_lag(v), "2026-09-01"),
        ("canon_budgets",
         lambda v: w(v, "Rules-of-Engagement.md", "x" * 16_000),
         lambda v: va.check_canon_budgets(v), "Rules-of-Engagement.md"),
        ("misfiled_backups",
         lambda v: w(v, "Tasks/.backups/todo-20260801.md", "x"),
         lambda v: va.check_misfiled_backups(v), "Tasks/.backups"),
        ("inbox_aging",
         lambda v: (w(v, "_inbox/old-alert.md", "x"),
                    os.utime(os.path.join(v, "_inbox/old-alert.md"),
                             (time.time() - 20 * 86400,) * 2)),
         lambda v: va.check_inbox_aging(v), "old-alert.md"),
        ("todo_hygiene",
         lambda v: w(v, "Tasks/todo.md",
                     "# todo\n\n## Active\n\n- [x] finished thing\n- ~~struck thing~~\n\n## Backlog\n"),
         lambda v: va.check_todo_hygiene(v), "2 completed"),
        ("size_claims",
         lambda v: (w(v, "Tasks/lessons.md", "x" * 1_000_000),
                    w(v, "CLAUDE.md", "lessons is ~110k tokens here\n")),
         lambda v: va.check_size_claims(v), "~110k tokens"),
        ("vitals_trend",
         lambda v: w(v, "Resources/operator/vault-state.json", json.dumps({
             "vitals_trend": [{"date": "2026-08-18", "orphans": 223, "dead_links": 2501,
                               "dotdot_links": 103, "frontmatter_gaps": 592},
                              {"date": "2026-08-11", "orphans": 205, "dead_links": 2352,
                               "dotdot_links": 96, "frontmatter_gaps": 574}]})),
         lambda v: va.check_vitals_trend(v), "orphans"),
    ]
    failed = []
    for name, seed_bad, run, needle in checks:
        # known-bad must fire
        with tempfile.TemporaryDirectory() as tmp:
            v = seed_vault(tmp)
            seed_bad(v)
            got = run(v)
            if not hits(got, check_name_for(name), needle):
                failed.append((name, "did NOT fire on seeded known-bad", got))
        # clean seed must stay quiet (skip vitals/size which need their seeds absent)
        with tempfile.TemporaryDirectory() as tmp:
            v = seed_vault(tmp)
            got = [f for f in run(v) if f["severity"] != "info"]
            if got:
                failed.append((name, "fired on a CLEAN vault", got))
    return failed


def run_zero_inspection_cases():
    """A check that walks a directory and inspects zero items must not read as
    clean. hub_triangle and misfiled_backups are guarded in main() via
    ZERO_INSPECTION; this drives the real main() end-to-end (subprocess,
    --json) rather than the guard lambda in isolation, so it proves the
    wiring, not just the precondition function."""
    import json
    import shutil
    import subprocess
    import sys
    import tempfile

    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        v = seed_vault(tmp)
        for n in os.listdir(os.path.join(v, "Projects")):
            p2 = os.path.join(v, "Projects", n)
            if os.path.isdir(p2):
                shutil.rmtree(p2)
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "vault-audit.py"),
             "--vault", v, "--only", "hub_triangle", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)
        infos = [f for f in data["findings"] if f["severity"] == "info"
                 and f["check"] == "hub_triangle"]
        if not infos:
            failed.append(("zero_inspection_hub_triangle",
                           "an emptied Projects/ dir read as clean instead of "
                           "'zero items inspected'", data["findings"]))

    # a clean vault WITH real projects must NOT trip the guard
    with tempfile.TemporaryDirectory() as tmp:
        v = seed_vault(tmp)
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "vault-audit.py"),
             "--vault", v, "--only", "hub_triangle", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)
        infos = [f for f in data["findings"] if f["severity"] == "info"]
        if infos:
            failed.append(("zero_inspection_false_positive",
                           "the guard fired on a vault that DOES have a project",
                           infos))
    return failed


def run_lessons_floor_cases():
    """lessons_floor: the section count of an append-only record must not fall.
    Seeds a clobber (a past with many dated sections, a present with
    few) through the injectable git, plus the clean and no-baseline cases."""
    import tempfile
    failed = []
    past = "# lessons\n" + "".join("\n## 2026-07-%02d\n\nbody\n" % d for d in range(1, 29))

    def fake_git(text):
        return lambda args: "abc1234def\n" if args[0] == "rev-list" else text

    with tempfile.TemporaryDirectory() as tmp:
        v = seed_vault(tmp)  # one dated section in the live file
        got = va.lessons_floor_findings(v, git=fake_git(past))
        if not hits(got, "lessons_floor", "sections of an append-only record are gone"):
            failed.append(("lessons_floor", "did NOT fire on a seeded section loss", got))
        same = open(os.path.join(v, "Tasks", "lessons.md"), encoding="utf-8").read()
        got = [f for f in va.lessons_floor_findings(v, git=fake_git(same)) if f["severity"] != "info"]
        if got:
            failed.append(("lessons_floor", "fired on an unchanged file", got))

        def broken(args):
            raise RuntimeError("not a git repository")
        got = va.lessons_floor_findings(v, git=broken)
        if not [f for f in got if f["severity"] == "info" and "NOT checked" in f["message"]]:
            failed.append(("lessons_floor", "no-baseline case was silent instead of info", got))
    return failed


def main():
    failed = run_all(None)
    failed += run_zero_inspection_cases()
    failed += run_lessons_floor_cases()
    if failed:
        for name, why, got in failed:
            print(f"FAIL {name}: {why}")
            for f in got[:3]:
                print(f"   {f['severity']} {f['check']} {f['path']}: {f['message'][:80]}")
        return 1
    print("PASS: every check fired on its seeded known-bad and stayed quiet on a clean vault")
    return 0


if __name__ == "__main__":
    sys.exit(main())
