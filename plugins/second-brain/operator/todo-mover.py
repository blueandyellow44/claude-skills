#!/usr/bin/env python3
"""todo-mover.py — tier-1 mechanical pass for the todo-groom skill.

Tasks/CLAUDE.md's contract: todo.md is forward-only. When a task ships, the
whole block moves to journal.md with the outcome, verbatim.

This script owns ONLY the unambiguous case: a top-level `- [x]` block. It
never touches an open `- [ ]` block, even one whose prose mentions CLOSED,
RESOLVED, FIXED, or DONE somewhere inside it — that word is often describing
a sub-clause of a still-open item (a pull request merged while the deploy it
unblocks is still pending, for instance), and deciding otherwise is chain
collapse or age triage, which the todo-groom skill routes to the owner, not to
a script. See test_todo_mover.py beside this file for the seeded proof of
that boundary.

Run: python3 todo-mover.py --date YYYY-MM-DD [--apply] [--vault PATH | --todo <path> --journal <path>]
The files default to Tasks/todo.md and Tasks/journal.md in the vault named by
--vault, else by the SECOND_BRAIN_VAULT environment variable.
Without --apply, prints the candidate blocks and does nothing else.
"""
import argparse
import os
import re
import shutil
import sys

BLOCK_START_RE = re.compile(r"^- ")
HEADING_RE = re.compile(r"^#")
CHECKED_RE = re.compile(r"^- \[x\]", re.IGNORECASE)


def parse_blocks(text):
    """Split into (start, end) line-index ranges for each top-level `- ` block.
    A block runs until the next top-level `- ` or a heading; everything in
    between (continuation prose, nested sub-bullets) stays inside the block."""
    lines = text.split("\n")
    n = len(lines)
    blocks = []
    i = 0
    while i < n:
        if BLOCK_START_RE.match(lines[i]):
            start = i
            j = i + 1
            while j < n and not BLOCK_START_RE.match(lines[j]) and not HEADING_RE.match(lines[j]):
                j += 1
            blocks.append((start, j))
            i = j
        else:
            i += 1
    return lines, blocks


def find_checked_blocks(text):
    """Return [(start, end, block_text), ...] for every top-level `- [x]` block."""
    lines, blocks = parse_blocks(text)
    out = []
    for (s, e) in blocks:
        block_text = "\n".join(lines[s:e])
        if CHECKED_RE.match(lines[s]):
            out.append((s, e, block_text))
    return out


def apply_move(todo_text, journal_text, checked_blocks, date_str):
    """Return (new_todo_text, new_journal_text). Pure function, no I/O, so it's
    directly unit-testable without touching real files."""
    lines = todo_text.split("\n")
    remove_idx = set()
    for (s, e, _) in checked_blocks:
        remove_idx.update(range(s, e))
    new_todo_lines = [l for idx, l in enumerate(lines) if idx not in remove_idx]
    new_todo_text = re.sub(r"\n{3,}", "\n\n", "\n".join(new_todo_lines))

    moved = "\n\n".join(bt for (_, _, bt) in checked_blocks)
    addition = (
        f"\n## {date_str} — todo groom (mechanical)\n\n"
        "Moved from `todo.md` per its forward-only rule: blocks already checked "
        "`[x]`. Verbatim, byte-identical to their todo.md form.\n\n"
        f"{moved}\n"
    )
    new_journal_text = journal_text.rstrip("\n") + "\n" + addition
    return new_todo_text, new_journal_text


def resolve_vault(arg=None):
    """--vault wins, then the SECOND_BRAIN_VAULT environment variable. Never guessed."""
    v = arg or os.environ.get("SECOND_BRAIN_VAULT")
    if not v:
        sys.exit("SECOND_BRAIN_VAULT is not set and no --vault was given. Set it to the "
                 "absolute path of your vault (see the plugin README).")
    v = os.path.abspath(os.path.expanduser(v))
    if not os.path.isdir(v):
        sys.exit("vault not found: %s (check SECOND_BRAIN_VAULT or --vault)" % v)
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vault", default=None,
                    help="vault root; default: the SECOND_BRAIN_VAULT environment variable")
    ap.add_argument("--todo", default=None, help="default: <vault>/Tasks/todo.md")
    ap.add_argument("--journal", default=None, help="default: <vault>/Tasks/journal.md")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD for the journal heading")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not (args.todo and args.journal):
        vault = resolve_vault(args.vault)
        args.todo = args.todo or os.path.join(vault, "Tasks", "todo.md")
        args.journal = args.journal or os.path.join(vault, "Tasks", "journal.md")
    for path in (args.todo, args.journal):
        if not os.path.isfile(path):
            sys.exit("not found: %s" % path)

    with open(args.todo) as f:
        todo_text = f.read()
    checked = find_checked_blocks(todo_text)

    print(f"Tier-1 [x]-checked blocks found: {len(checked)}")
    for (s, e, bt) in checked:
        headline = re.sub(r"\s+", " ", bt)[:140]
        print(f"  L{s+1}-{e}  {headline}")

    if not args.apply:
        print("\n(dry run — pass --apply to move these blocks to journal.md)")
        return

    if not checked:
        print("\nNothing to move.")
        return

    backup_dir = os.path.join(os.path.dirname(os.path.abspath(args.todo)), "..", ".backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = args.date.replace("-", "") + "-todo-mover"
    shutil.copy(args.todo, os.path.join(backup_dir, f"todo.md.{stamp}"))
    shutil.copy(args.journal, os.path.join(backup_dir, f"journal.md.{stamp}"))

    with open(args.journal) as f:
        journal_text = f.read()
    new_todo, new_journal = apply_move(todo_text, journal_text, checked, args.date)

    with open(args.todo, "w") as f:
        f.write(new_todo)
    with open(args.journal, "w") as f:
        f.write(new_journal)

    print(f"\nMoved {len(checked)} blocks. Backups in {backup_dir}/")
    print(f"todo.md: {len(todo_text)} -> {len(new_todo)} chars")


if __name__ == "__main__":
    main()
