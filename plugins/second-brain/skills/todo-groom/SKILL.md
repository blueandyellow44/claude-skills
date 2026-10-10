---
name: todo-groom
description: "Triage Tasks/todo.md back to forward-only: move completed blocks to Tasks/journal.md verbatim (mechanical tier, no ruling needed), collapse superseded status-line chains to the newest state (judgment tier, the owner rules on deletions), and surface stale items by age tier for keep/park/kill calls. The recurring fix for a todo file that has swollen with finished and months-old items. Triggers on 'groom the todo', 'todo groom', 'clean up todo', 'triage the todo list', 'todo is bloated'."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

## todo-groom

Part of the vault-ops suite. Sibling: vault-doctor (its `todo_hygiene` check routes here).

You are running todo-groom. `Tasks/CLAUDE.md` states the contract: todo.md is forward-only; when a task ships, the entire block moves to `Tasks/journal.md` with the outcome.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable; the script stops with a message when it is unset.

### Tiers

1. **Mechanical (apply without asking).** Top-level Active items that are `[x]` checked move, whole block and verbatim, to journal.md under a dated `## YYYY-MM-DD` todo-groom heading. Only the checkbox counts. An earlier version of this tier also moved any open `- [ ]` block carrying a `Superseded/DONE/CLOSED/RESOLVED/FIXED/SHIPPED` marker anywhere in its text; tested against a real todo.md, 14 of 22 candidates were false positives, because the marker was describing a sub-clause of a still-open item (one finding fixed inside a block still open because the deploy it depends on had not shipped). That heuristic is gone. A block whose prose merely mentions a closure word belongs to tier 2 (chain collapse) or tier 3 (age triage), not this tier. Run `python3 "${CLAUDE_PLUGIN_ROOT}/operator/todo-mover.py" --date YYYY-MM-DD` (dry run by default, `--apply` to execute). It parses top-level `- ` blocks with their indented continuations, never splits a block, and snapshots todo.md and journal.md to the vault-root `.backups/` before writing. Its seeded known-bad/known-good cases are in `operator/test_todo_mover.py`.
2. **Chain collapse (propose, the owner rules).** Several items tracking the SAME loop at different moments (a deploy chain five generations deep, say). Propose: newest item stays, older generations move to journal. Present the chain, wait for the ruling.
3. **Age triage (propose, the owner rules).** Items > 30 days untouched, grouped project-first: keep (still real) / park (move to `## Backlog`) / kill (journal with a "dropped" note). Cap one sitting at ~20 rulings.

### Ground rules

- Verbatim preservation: a moved block is byte-identical in journal.md; grooming never rewrites history.
- Verify after: the moved sample greps to exactly one home; `wc -c` before/after reported.
- An item that names another surface's pending action (an owner-only click, a collaborator's deploy) is never killed by groom; it is the open-loop record.

### Output example

```
todo-groom 2026-08-18: 262KB -> 222KB. Mechanical: 28 blocks -> journal. Chains proposed: the deploy chain (5->1),
the sync-server chain (3->1), awaiting ruling. Age triage: 22 old items listed for keep/park/kill.
```
