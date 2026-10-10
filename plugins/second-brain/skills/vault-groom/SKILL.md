---
name: vault-groom
description: "Remediation executor for the vault's red metrics: repair dead wikilinks (walk-per-item), tie curated orphans into the graph (tie-orphans.py), backfill missing frontmatter on curated notes, normalize ../-prefixed wikilinks (normalize-wikilinks.py), file vault-root strays, and age out _inbox items. The loop that turns the vault vitals from red to green: vault-doctor detects, vault-groom fixes. Triggers on 'groom the vault', 'fix dead links', 'tie orphans', 'clean up the vault', 'work the vitals', 'vault groom'."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

## vault-groom

Part of the vault-ops suite. Siblings: vault-doctor (detects; run it first when in doubt), canon-slim, todo-groom.

You are running vault-groom. This skill exists because tracked-but-unacted metrics are rot with a dashboard: orphans and dead links that climb for days, measured daily, remediated never.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable; the scripts stop with a message when it is unset. They live in `OP="${CLAUDE_PLUGIN_ROOT}/operator"`. `normalize-wikilinks.py` and `tie-orphans.py` print their target vault on the first line of stderr: read that line before trusting any result, and always before `--apply`.

### Ground rules

- **Scope is the curated layer only.** `vault-vitals.py` defines it; capture folders (Intelligence transcripts, Daily, Journal, Resources/sessions, _inbox, skill machinery) are exempt by design. Never "fix" them into the graph.
- **Snapshot before every canonical edit** (`.backups/` at the vault root). Batch snapshots per file, not per link.
- **Mechanical vs semantic.** Normalizing `../`-links and exact-rename repairs are mechanical: apply in bulk, report counts. Repointing a dead link to a *different* target, merging notes, or writing frontmatter that asserts status/type is semantic: walk per item, the owner confirms destination or wording when the choice is not forced.
- **Use the shipped scripts.** `normalize-wikilinks.py` and `tie-orphans.py` are dry-run by default. `normalize-wikilinks.py` repairs renames and aliases only from its two maps (`RENAMES_*`, `ALIASES`), which ship empty: a vault that needs them keeps its own edited copy of the script (for example in `Resources/operator/`), because the plugin's copy is replaced on update.
- **Measure before and after.** Run `vault-vitals.py` at start and end; the close reports the deltas. A groom that does not move a number says so plainly.

### Procedure

1. Baseline: `python3 "$OP/vault-vitals.py"` (record orphans / dead links / dotdot / frontmatter gaps).
2. Cheapest mechanical class first: dotdot-link normalization (`python3 "$OP/normalize-wikilinks.py"`, then `--apply`), then dead links whose target exists under another exact path (rename repairs), then frontmatter backfill on curated notes (type/date/status derived from folder + git history, never invented), then orphan tie-in (`python3 "$OP/tie-orphans.py"`, then `--apply`, for skill and project machinery; for a real note, a link from the owning folder's CLAUDE.md or nearest hub in a real routing sentence, not a link dump).
3. Ambiguous items accumulate into a walk list for the owner, capped at what one sitting can rule on (~20); the rest stays in a dated queue note in Tasks/.
4. Close: before/after metric table in chat, daily-log entry at wrap.

For a large groom, fan out with the two agents this plugin ships: `vault-finding-auditor` confirms a batch of findings first (read-only), then one `vault-groom-worker` per class per batch applies the confirmed ones.

### Output example

```
vault-groom 2026-08-18: dotdot 103->0 (mechanical), dead links 2,501->2,180 (321 rename-repairs),
frontmatter gaps 592->510 (82 derived backfills), orphans 223->219 (4 tied; 19 queued for the owner).
Snapshots in .backups/, deltas verified by vault-vitals re-run.
```
