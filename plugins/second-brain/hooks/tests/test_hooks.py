#!/usr/bin/env python3
"""Tests for the second-brain session hooks. Run: python3 hooks/tests/test_hooks.py

Every case runs the real hook scripts as subprocesses against a throwaway vault and a
throwaway state folder, with the JSON Claude Code would send. Unhappy paths first.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HOOKS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TODAY = time.strftime("%Y-%m-%d")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sb-hooks-")
        self.vault = os.path.join(self.tmp, "vault")
        self.state = os.path.join(self.tmp, "state")
        self.work = os.path.join(self.tmp, "code", "alpha-app")
        os.makedirs(self.work)
        write(os.path.join(self.vault, "Rules-of-Engagement.md"), "# Rules\n\n1. Verify before done.\n")
        write(os.path.join(self.vault, "Daily", "2000-01-01.md"), "# old\n\n## Log\n\n### Old entry (Code)\nold\n")
        write(os.path.join(self.vault, "Daily", TODAY + ".md"),
              "---\ntype: daily\n---\n# %s\n\n## Log\n\n### First thing (Code)\nDid one.\n\n"
              "### Second thing (Code)\nDid two. MARKER-DAILY\n" % TODAY)
        write(os.path.join(self.vault, "Tasks", "todo.md"),
              "# todo\n\n## Active\n\n- Ship the alpha MARKER-TODO\n- Write the guide\n\n## Backlog\n\n- Later thing\n")
        write(os.path.join(self.vault, "Tasks", "lessons.md"),
              "# lessons\n\n## 2026-01-01\n\n### Rule: old lesson\nbody\n\n## 2026-02-02\n\n### Rule: MARKER-LESSON\nbody\n")
        write(os.path.join(self.vault, "Projects", "_template.md"), "---\nstatus: template\n---\n")
        self.hub = os.path.join(self.vault, "Projects", "Alpha", "Alpha.md")
        write(self.hub, "---\ntype: project\nstatus: active\nlast_touched: 2026-02-02\n"
                        "next_step: MARKER-NEXT finish the alpha\nworkspace:\n  - %s\n---\n# Alpha\n\n"
                        "## Rules\n\n- MARKER-RULE never push without asking\n\n## Log\n\n- **2026-02-02**: started\n"
                        % self.work)
        write(os.path.join(self.vault, "Projects", "Beta", "Beta.md"),
              "---\nstatus: active\nlast_touched: 2026-01-01\nnext_step: beta next\n---\n# Beta\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, **extra):
        e = {k: v for k, v in os.environ.items() if not k.startswith(("SECOND_BRAIN", "SESSION_MANIFEST"))}
        e.update(SECOND_BRAIN_VAULT=self.vault, SECOND_BRAIN_STATE_DIR=self.state)
        e.update({k: v for k, v in extra.items() if v is not None})
        for k, v in extra.items():
            if v is None:
                e.pop(k, None)
        return e

    def run_hook(self, script, payload, *args, raw=None, **env):
        p = subprocess.run([sys.executable, os.path.join(HOOKS, script), *args],
                           input=raw if raw is not None else json.dumps(payload),
                           capture_output=True, text=True, env=self.env(**env), timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr.strip(), "", p.stderr)
        return json.loads(p.stdout) if p.stdout.strip() else {}

    def start(self, sid="s1", source="startup", cwd=None, transcript=None, **env):
        payload = {"session_id": sid, "source": source, "cwd": cwd or self.work, "hook_event_name": "SessionStart"}
        if transcript:
            payload["transcript_path"] = transcript
        return self.run_hook("sb_startup.py", payload, **env)

    def grow(self, transcript, text="turn\n"):
        with open(transcript, "a", encoding="utf-8") as fh:
            fh.write(text)
        return transcript

    def ctx(self, out):
        return (out.get("hookSpecificOutput") or {}).get("additionalContext", "")

    def manifest(self, sid="s1"):
        path = os.path.join(self.state, "%s.sb-manifest.jsonl" % sid)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh]


class UnhappyPaths(Base):
    def test_no_vault_variable_says_so_in_one_line(self):
        out = self.start(SECOND_BRAIN_VAULT=None)
        self.assertIn("SECOND_BRAIN_VAULT is not set", out["systemMessage"])
        self.assertIn("SECOND_BRAIN_VAULT is not set", self.ctx(out))

    def test_vault_path_that_is_not_a_folder(self):
        out = self.start(SECOND_BRAIN_VAULT=os.path.join(self.tmp, "nope"))
        self.assertIn("not a folder", out["systemMessage"])

    def test_malformed_stdin_never_crashes(self):
        for script, args in (("sb_startup.py", ()), ("sb_drift.py", ("prompt",)), ("sb_drift.py", ("tool",)),
                             ("sb_lifecycle.py", ("stop",)), ("sb_lifecycle.py", ("end",))):
            self.run_hook(script, None, *args, raw="{not json")

    def test_empty_vault_reports_missing_sources(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        out = self.start(SECOND_BRAIN_VAULT=empty)
        self.assertIn("missing Rules-of-Engagement.md, Tasks/todo.md, Tasks/lessons.md", out["systemMessage"])

    def test_hooks_off_is_silent(self):
        self.assertEqual(self.start(SECOND_BRAIN_HOOKS="off"), {})
        self.assertEqual(self.manifest(), [])

    def test_unowned_folder_gets_the_board_not_a_guess(self):
        elsewhere = os.path.join(self.tmp, "code", "gamma")
        os.makedirs(elsewhere)
        c = self.ctx(self.start(cwd=elsewhere))
        self.assertIn("none resolved from the working folder", c)
        self.assertNotIn("MARKER-RULE", c)

    def test_two_hubs_claiming_one_folder_resolve_to_none(self):
        write(os.path.join(self.vault, "Projects", "Twin", "Twin.md"),
              "---\nstatus: active\nworkspace: %s\n---\n# Twin\n" % self.work)
        self.assertIn("none resolved", self.ctx(self.start()))


class Startup(Base):
    def test_delivers_every_source_as_content(self):
        out = self.start()
        c = self.ctx(out)
        for marker in ("Verify before done", "MARKER-DAILY", "MARKER-TODO", "MARKER-LESSON",
                       "MARKER-NEXT", "MARKER-RULE"):
            self.assertIn(marker, c)
        self.assertNotIn("Old entry", c)          # the newest daily only
        self.assertNotIn("Later thing", c)        # Active only, not Backlog
        self.assertIn("delivered 5 source(s)", out["systemMessage"])

    def test_manifest_records_each_source_with_its_own_bytes(self):
        self.start()
        rows = [r for r in self.manifest() if r["rec"] == "delivered"]
        self.assertEqual({r["kind"] for r in rows}, {"rules", "daily", "todo", "lessons", "project"})
        self.assertEqual(len({r["bytes"] for r in rows}), len(rows), "every source must carry its own size")
        self.assertEqual(len({r["sha"] for r in rows}), len(rows))

    def test_budget_is_enforced(self):
        write(os.path.join(self.vault, "Rules-of-Engagement.md"), "rule line\n" * 5000)
        c = self.ctx(self.start(SECOND_BRAIN_STARTUP_CHARS="4000"))
        self.assertIn("more characters not shown", c)
        self.assertLess(len(c), 6000)

    def test_hub_named_after_the_folder_resolves_without_a_workspace_line(self):
        folder = os.path.join(self.tmp, "code", "Beta")
        os.makedirs(folder)
        self.assertIn("PROJECT: Beta", self.ctx(self.start(cwd=folder)))

    def test_compact_redelivers_hub_and_ledger_only(self):
        write(os.path.join(self.state, "s1.ledger.json"), json.dumps({
            "request": "build alpha", "requirements": [{"text": "MARKER-REQ open", "done": False},
                                                       {"text": "closed one", "done": True}],
            "decisions": [{"text": "use sqlite", "why": "small"}], "done_when": []}))
        c = self.ctx(self.start(source="compact"))
        self.assertIn("MARKER-RULE", c)
        self.assertIn("MARKER-REQ open", c)
        self.assertNotIn("closed one", c)
        self.assertNotIn("MARKER-TODO", c)


class Dedupe(Base):
    def _race(self, **env):
        outs = []

        def go():
            outs.append(self.start(**env))
        threads = [threading.Thread(target=go) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        return outs

    def test_two_copies_of_the_plugin_deliver_once(self):
        outs = self._race()
        self.assertEqual(sum(1 for o in outs if self.ctx(o)), 1)
        rows = self.manifest()
        self.assertEqual(sum(1 for r in rows if r["rec"] == "duplicate_suppressed"), 1)
        self.assertEqual(sum(1 for r in rows if r["rec"] == "delivered" and r["kind"] == "rules"), 1)

    def test_known_bad_without_dedupe_both_deliver(self):
        """The detector above must be able to fail: with dedupe off it sees two deliveries."""
        outs = self._race(SECOND_BRAIN_DEDUPE_OFF="1")
        self.assertEqual(sum(1 for o in outs if self.ctx(o)), 2)


class Resume(Base):
    def test_two_resumes_in_a_row_both_deliver(self):
        tr = self.grow(os.path.join(self.tmp, "t.jsonl"))
        self.start(transcript=tr)
        self.assertIn("MARKER-RULE", self.ctx(self.start(source="resume", transcript=self.grow(tr))))
        self.assertIn("MARKER-RULE", self.ctx(self.start(source="resume", transcript=self.grow(tr))))

    def test_resume_says_the_hub_changed(self):
        self.start()
        Drift.bump(self, self.hub, "- **2026-03-03**: MARKER-NEWLOG\n")
        c = self.ctx(self.start(source="resume"))
        self.assertIn("CHANGED since this session loaded it", c)
        self.assertIn("MARKER-NEWLOG", c)

    def test_resume_names_a_changed_file_once(self):
        self.start()
        f = os.path.join(self.work, "a.py")
        write(f, "x\n")
        Drift.tool(self, "Read", f)
        Drift.bump(self, f, "y\n")
        self.assertIn(f, self.ctx(self.start(source="resume")))
        self.assertEqual(Drift.prompt(self), {})

    def test_hub_log_shows_the_most_recent_by_date(self):
        with open(self.hub, "a", encoding="utf-8") as fh:
            fh.write("- **2025-01-01**: MARKER-ANCIENT\n- **2026-09-09**: a\n- **2026-09-10**: b\n- **2026-09-11**: c\n")
        self.assertNotIn("MARKER-ANCIENT", self.ctx(self.start()))

    def test_a_resumed_session_counts_as_one_unwrapped_session(self):
        f = os.path.join(self.work, "a.py")
        write(f, "")
        Drift.tool(self, "Write", f, sid="old")
        tr = os.path.join(self.tmp, "old.jsonl")
        for _ in range(3):
            self.run_hook("sb_lifecycle.py", {"session_id": "old", "transcript_path": self.grow(tr)}, "end")
        self.assertIn("1 recent session(s)", self.ctx(self.start(sid="new")))


class Drift(Base):
    def prompt(self, text="next", sid="s1"):
        return self.run_hook("sb_drift.py", {"session_id": sid, "prompt": text}, "prompt")

    def tool(self, name, path, sid="s1", tid=None, **extra_input):
        inp = dict(file_path=path, **extra_input)
        return self.run_hook("sb_drift.py", {"session_id": sid, "tool_name": name, "tool_input": inp,
                                             "tool_use_id": tid or "%s-%s-%f" % (name, path, time.time())}, "tool")

    def bump(self, path, text):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
        st = os.stat(path)
        os.utime(path, (st.st_atime, st.st_mtime + 5))

    def test_quiet_when_nothing_changed(self):
        self.start()
        self.assertEqual(self.prompt(), {})

    def test_changed_hub_is_named_and_redelivered_once(self):
        self.start()
        self.bump(self.hub, "- **2026-03-03**: MARKER-NEWLOG from another session\n")
        out = self.prompt("first")
        self.assertIn("DRIFT", self.ctx(out))
        self.assertIn("MARKER-NEWLOG", self.ctx(out))
        self.assertEqual(self.prompt("second"), {})

    def test_own_edit_is_not_drift_but_a_parallel_edit_is(self):
        self.start()
        f = os.path.join(self.work, "app.py")
        write(f, "x = 1\n")
        self.tool("Write", f)
        self.assertEqual(self.prompt("after my edit"), {})
        self.bump(f, "y = 2\n")
        self.assertIn(f, self.ctx(self.prompt("after theirs")))

    def test_first_edit_under_a_workspace_delivers_its_hub_once(self):
        elsewhere = os.path.join(self.tmp, "code", "gamma")
        os.makedirs(elsewhere)
        self.start(cwd=elsewhere)
        f = os.path.join(self.work, "a.py")
        write(f, "")
        out = self.tool("Edit", f)
        self.assertIn("MARKER-RULE", self.ctx(out))
        self.assertEqual(self.tool("Edit", f), {})

    def test_a_read_never_delivers_a_hub(self):
        f = os.path.join(self.work, "a.py")
        write(f, "")
        self.assertEqual(self.tool("Read", f), {})

    def test_prompt_check_is_fast(self):
        self.start()
        for i in range(40):
            f = os.path.join(self.work, "f%d.py" % i)
            write(f, "")
            self.tool("Read", f)
        t = time.time()
        self.prompt()
        self.assertLess(time.time() - t, 1.0)  # includes interpreter start


class Lifecycle(Base):
    def stop(self, sid="s1"):
        return self.run_hook("sb_lifecycle.py", {"session_id": sid}, "stop")

    def test_no_reminder_for_a_session_that_wrote_nothing(self):
        self.start()
        self.assertEqual(self.stop(), {})

    def test_reminds_once_then_not_after_a_wrap(self):
        self.start()
        f = os.path.join(self.work, "a.py")
        write(f, "")
        Drift.tool(self, "Write", f)
        self.assertIn("wrap session", self.stop()["systemMessage"])
        self.assertEqual(self.stop(), {})

    def test_daily_edit_counts_as_wrapped(self):
        f = os.path.join(self.work, "a.py")
        write(f, "")
        Drift.tool(self, "Write", f)
        Drift.tool(self, "Edit", os.path.join(self.vault, "Daily", TODAY + ".md"))
        self.assertEqual(self.stop(), {})

    def test_shell_append_to_daily_counts_as_wrapped(self):
        f = os.path.join(self.work, "a.py")
        write(f, "")
        Drift.tool(self, "Write", f)
        self.run_hook("sb_drift.py", {"session_id": "s1", "tool_name": "Bash",
                                      "tool_input": {"command": "cat >> \"$V/Daily/x.md\" <<EOF"}}, "tool")
        self.assertEqual(self.stop(), {})

    def test_unwrapped_sessions_are_counted_at_the_next_start(self):
        f = os.path.join(self.work, "a.py")
        write(f, "")
        Drift.tool(self, "Write", f, sid="old")
        self.run_hook("sb_lifecycle.py", {"session_id": "old", "cwd": self.work}, "end")
        self.assertIn("1 recent session(s) wrote files and ended without a wrap", self.ctx(self.start(sid="new")))


if __name__ == "__main__":
    unittest.main(verbosity=1)
