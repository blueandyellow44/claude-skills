---
name: session-ledger
description: "Keep this session's ledger: the request, the requirements it accumulates, the decisions and their reasons, and what done means; check work against it at scope changes, phase transitions, after compaction, and before a commit, deploy or PR. Use at the start of substantive work ('build X', 'fix Y', 'do all phases'), whenever the user adds or changes a requirement mid-session ('also make it...', 'no, it should...', 'cut that'), when they rule on something, before declaring done, and for 'drift check', 'are we still on track', 'what did I ask for', 'check against the plan'. Not for trivial or conversational turns."
metadata:
  workflow: true
allowed-tools:
  - Bash
  - Read
---

# session-ledger

## Goal

A session that runs long, compacts, or changes scope keeps hold of what it was asked to do. The ledger is the session's own record of the request, the requirements, the decisions, and the definition of done, written as they happen, so drift is checked against something on disk instead of against memory.

## Trigger

- Start of substantive work: record the request and what done means before the first edit.
- The owner adds, changes or cuts a requirement mid-session: add it, or drop the old one with their reason.
- The owner rules on something: record it as a decision with the why (and route the ruling to the hub through `ruling-capture` if it binds the project).
- A phase ends, the scope changes, or the session was compacted or resumed: re-read the ledger with `show` before continuing.
- Before declaring done, and before a commit, deploy or PR.

## Inputs

- The session id. Claude Code names each session's transcript `~/.claude/projects/<encoded working folder>/<session id>.jsonl`; the newest `.jsonl` there is normally this session. If you cannot determine it, choose a short slug, say that you did, and reuse the same slug for the whole session.
- The owner's words for the request, each requirement and each decision (quote them; do not paraphrase a ruling).

## Prerequisites

- `python3`. Nothing else: the ledger is a JSON file under `~/.claude/session-state/` and does not touch the vault.

## Procedure

The script is `${CLAUDE_PLUGIN_ROOT}/skills/session-ledger/scripts/ledger.py`, called `<ledger>` below (it is also `scripts/ledger.py` in this skill's base directory).

1. `python3 <ledger> --session <SID> request "<the ask, in the owner's words>"`
2. One `req` per requirement and one `done-when` per completion test. A done-when must be checkable: name the test, the file, or the screen.
3. `decide "<decision>" --why "<reason>"` for each load-bearing choice.
4. When a requirement is met, `check req <n>`; when a done-when holds, `check done <n>` (only after running the check, never on intent).
5. Scope change: `drop req <n> --why "<the owner's words>"`; it stays in the ledger as history.
6. Drift check: `show --open`, then compare the current plan and the last few changes against each open item. Name any mismatch in one line, fix the plan or the ledger, then continue.

## Outputs

- `~/.claude/session-state/<SID>.ledger.json`, printed back as open items after every write.
- Read by `session-wrap` at the end of the session. Hooks of your own can read the same file (to re-deliver it after compaction, or to list open items before a commit); none ship with this plugin, so re-reading it is this skill's job.

## Failure handling

- `check` or `drop` on a number that does not exist exits non-zero and says how many exist: re-run `show`.
- A missing session id: infer it as above and say so; never write a ledger under a guessed id silently.
- The ledger is advisory context. If it disagrees with the owner's newest words, the owner wins: update the ledger, do not argue from it.

## Verification

- `python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-ledger/tests/test_ledger.py"` (7 cases, unhappy paths first).
- Live: after `request` and one `req`, `show --open` lists the open requirement.

## Related

- `ruling-capture` (rulings that bind the project go to the hub)
- `session-wrap` (the wrap reads the ledger's decisions and open items)
