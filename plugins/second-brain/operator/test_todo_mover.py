#!/usr/bin/env python3
"""test_todo_mover.py — seeded known-bad/known-good proofs for todo-mover.py.

A detector (or mover) is untrusted until observed to fail on a
known-bad state and stay quiet on a known-good one. The load-bearing case here
is NOT "does it move a [x] block" (cheap to get right) — it's "does it refuse
to move an open [ ] block whose prose happens to contain the word CLOSED,
RESOLVED, FIXED, or DONE somewhere inside it." The first hand-run of this
class of heuristic produced 14 false
positives out of 22 candidates on a real vault todo.md for exactly that
reason, which is why the shipped script has no closure-marker heuristic at
all — only the checkbox. Run: python3 test_todo_mover.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("todo_mover", os.path.join(HERE, "todo-mover.py"))
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

FAILURES = []


def check(name, cond):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}")
    if not cond:
        FAILURES.append(name)


def run(name, fn):
    print(f"{name}:")
    fn()
    print()


TODO_FIXTURE = """# todo.md

## Active

- [x] **Ship the thing (2026-08-01).** Done and verified.

- [ ] **Still open, mentions FIXED inside prose (2026-08-02).** The sub-bug was
  **FIXED** last week but the parent item this bullet describes is not closed
  yet, so this whole block must NOT move.

- Open item with no checkbox at all (2026-08-03). Untouched either way.

- [x] **Second checked item, multi-line (2026-08-04).**
  Continuation line one.
  Continuation line two.

- [ ] Plain open item with a nested sub-bullet inside its own prose:
    - [x] this nested checkbox belongs to the PARENT block and must not be
      treated as a separate top-level block or moved on its own.
"""

JOURNAL_FIXTURE = "# journal.md\n\nHistorical record.\n\n---\n\n## 2026-05-09\n\nSeed content.\n"


def test_finds_only_checked_top_level_blocks():
    checked = tm.find_checked_blocks(TODO_FIXTURE)
    check("exactly 2 top-level [x] blocks found", len(checked) == 2)
    headlines = [bt.split("\n", 1)[0] for (_, _, bt) in checked]
    check("first is 'Ship the thing'", "Ship the thing" in headlines[0])
    check("second is 'Second checked item'", any("Second checked item" in h for h in headlines))


def test_refuses_open_block_with_closure_words_inside():
    checked = tm.find_checked_blocks(TODO_FIXTURE)
    combined = "\n".join(bt for (_, _, bt) in checked)
    check("the still-open FIXED-inside-prose block was NOT captured",
          "Still open, mentions FIXED" not in combined)


def test_nested_checkbox_not_split_out_as_its_own_block():
    checked = tm.find_checked_blocks(TODO_FIXTURE)
    combined = "\n".join(bt for (_, _, bt) in checked)
    check("nested checkbox text did not get pulled in as a 3rd block",
          len(checked) == 2 and "nested checkbox belongs to the PARENT" not in combined)


def test_apply_move_moves_verbatim_and_leaves_the_rest():
    checked = tm.find_checked_blocks(TODO_FIXTURE)
    new_todo, new_journal = tm.apply_move(TODO_FIXTURE, JOURNAL_FIXTURE, checked, "2026-08-20")
    check("moved blocks appear verbatim in the new journal",
          "Ship the thing" in new_journal and "Second checked item" in new_journal)
    check("moved blocks are gone from the new todo",
          "Ship the thing" not in new_todo and "Second checked item" not in new_todo)
    check("the still-open FIXED-mentioning block survives in the new todo",
          "Still open, mentions FIXED" in new_todo)
    check("the no-checkbox item survives in the new todo",
          "Open item with no checkbox" in new_todo)
    check("the nested-checkbox parent block survives in the new todo",
          "nested checkbox belongs to the PARENT" in new_todo)
    check("journal gets a dated todo-groom heading",
          "## 2026-08-20 — todo groom (mechanical)" in new_journal)


def test_empty_input_is_a_noop():
    checked = tm.find_checked_blocks("# todo.md\n\n## Active\n\n- Nothing checked here.\n")
    check("zero blocks found in a checkbox-free file", len(checked) == 0)


def main():
    run("finds only checked top-level blocks", test_finds_only_checked_top_level_blocks)
    run("refuses an open block with closure words inside its prose",
        test_refuses_open_block_with_closure_words_inside)
    run("does not split a nested checkbox out as its own block",
        test_nested_checkbox_not_split_out_as_its_own_block)
    run("apply_move moves verbatim and leaves everything else",
        test_apply_move_moves_verbatim_and_leaves_the_rest)
    run("no-op on a checkbox-free file", test_empty_input_is_a_noop)

    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
