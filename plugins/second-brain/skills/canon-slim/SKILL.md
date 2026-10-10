---
name: canon-slim
description: "Budget keeper for the always-loaded canon files (Rules-of-Engagement.md, root CLAUDE.md, Tasks/todo.md; budgets declared in vault-audit.py CANON_BUDGETS). When a file trips its budget, build a displacement ledger (every rule tagged keep / displace-to-lessons / compress, with the lessons.md pointer verified or written first), the owner rules, then execute in one pass: .backups snapshot, edit, and a live check that the slimmed file still loads. Enforces compress-or-displace, never accrete. Triggers on 'slim the ROE', 'canon slim', 'the rules file is too big', 'displacement ledger', 'canon over budget'."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

## canon-slim

Part of the vault-ops suite. Sibling: vault-doctor (its `canon_budgets` check routes here).

You are running canon-slim. This skill exists because a size contract that lives only in prose is not a tripwire: a rules file crosses its warning line with the receipt sitting in a daily note nobody re-reads, and keeps accreting. The budget lives in `vault-audit.py` where it fires; this skill is what firing leads to.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable; the audit stops with a message when it is unset. `AUDIT="${CLAUDE_PLUGIN_ROOT}/skills/vault-setup/references/operator/vault-audit.py"` (or the vault's own copy at `Resources/operator/vault-audit.py`, whose budgets are the ones to trust if the owner retuned them).

### The contract

- `Rules-of-Engagement.md` (ROE) holds ACTIVE FORMS only: what to do, with a dated pointer to lessons. `Tasks/lessons.md` holds the full story, so ROE never needs the worked example.
- A rule displaces when it is a dated one-project story, a stack recipe, or subsumed by a kept rule. A rule compresses when it is genuinely cross-cutting but carries its anecdote with it. Non-negotiables are the owner's, untouchable without their explicit word.
- **Nothing is deletion-only**: a displaced rule must have its lessons.md entry VERIFIED at a line number first, and verified means reading the heading under the right `## date` section, not a keyword grep (cheap grep probes match wrong headings; heading-under-date settles it). Rules with no entry get one WRITTEN before removal.
- Target is the WARN line minus real headroom (read the budgets from CANON_BUDGETS, never from this line), because landing a few hundred chars under the line is how a file trips again a week later. A vault with a second-tier rules file (for example `Context/engineering-rules.md`) can displace engineering-craft rules there instead of only to lessons.md.

### Procedure

1. Measure: `python3 "$AUDIT" --only canon_budgets`.
2. Build the ledger at `Tasks/<canon-file>-displacement-ledger-<date>.md`: one row per rule with its tag, chars, lessons pointer or **write-first** marker, and reason. A small generator script beats hand-listing.
3. **The owner rules on the ledger.** Per row or per block. No edit before the ruling.
4. Execute in ONE pass: timestamped `.backups/` snapshot, then write missing lessons entries, then apply displacements and compressions, so git sees one coherent change. If the vault runs a sync job with a shrink guard, tell the owner before a large shrink trips it.
5. Prove the load in the same wrap: start a fresh session in the vault (or `claude -p` from the vault folder) and confirm it can quote a rule from the slimmed file. Nothing ships with this plugin to automate that check. If the vault keeps mirrors or generated indexes of its root files, re-run their generators now.

### Output example

```
canon-slim 2026-08-18: ROE 46,568 -> 36,900 chars. 18 displaced (6 lessons entries written first),
33 compressed, 130 untouched. Ledger: Tasks/roe-displacement-ledger-2026-08-18.md (the owner ruled per block).
Load check: a fresh session quoted rule 3. Mirrors: none in this vault.
```
