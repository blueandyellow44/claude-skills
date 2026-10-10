---
name: vault-doctor
description: "Run the vault's deterministic health audit (vault-audit.py, 19 checks covering root files, routing coverage, the Obsidian layer, hub/board/root triangle, hub YAML, canon size and rule-count budgets, generated-artifact staleness, pipeline freshness, misfiled backups, _inbox aging, todo hygiene, stale size claims, vitals trend) plus vault-vitals, then walk every finding with its shipped fix: apply-now, save-to-plan, or declined by the owner, never flag-only. Triggers on 'vault doctor', 'audit the vault', 'vault health', 'run the vault audit', 'full vault sweep', 'is the vault healthy'."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

## vault-doctor

Part of the vault-ops suite. Siblings: vault-groom (executes remediation), canon-slim (size budgets), todo-groom, vault-setup.

You are running vault-doctor. Deterministic detection first, judgment second, and every finding leaves with a disposition.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable. The scripts stop with a message when it is unset; never guess a vault path. In the commands below:

- `AUDIT="${CLAUDE_PLUGIN_ROOT}/skills/vault-setup/references/operator/vault-audit.py"` (a vault that took vault-setup's operator layer also has its own copy at `Resources/operator/vault-audit.py`; either works)
- `OP="${CLAUDE_PLUGIN_ROOT}/operator"`

### Ground rules

- **Agent-free by design.** The detector layer is `vault-audit.py`: plain python, so it runs whole when the API is shedding load and every fan-out agent is dying mid-audit. Subagents are an optional accelerant for the walk, never a dependency.
- **Trust the detector only as far as its proofs.** `test_vault_audit.py` (beside the audit script) seeds a known-bad for every check. If you edit vault-audit.py, run the test file in the same turn; a permanently clean check points at nothing.
- **Every finding ships a fix, nothing is flag-only.** Each finding's `fix` field is the starting proposal. Disposition per finding: apply now / save to plan (todo.md entry) / the owner declines (recorded). No open-warning pile that carries across runs.
- **Snapshot before any canonical edit** (`.backups/<name>.<timestamp>` at the vault root).

### What can run unattended vs what waits for you

`run-weekly.sh` in this skill folder is a scheduled-run script. Nothing installs it: schedule it yourself (cron, launchd, a CI job) with `SECOND_BRAIN_VAULT` in the job's environment, and only on the owner's word, because a job that edits the vault is a standing change. It does two phases. **Mechanical self-tending** applies only provably-safe passes: `relocate-misfiled-backups.py --apply` (moves stray snapshots into the root `.backups/` under path-encoded names, never deletes, idempotent) and `normalize-wikilinks.py --apply` (rewrites a link ONLY when it is currently dead AND the repair resolves to exactly one real file; never touches the transcript layer). Set `VAULT_DOCTOR_DETECT_ONLY=1` to skip that phase. **Detection** then runs vault-audit; findings plus anything the mechanical phase changed land in a dated `_inbox/` report.

Everything judgment-shaped stays out of the schedule and waits for a session: displacing canon, killing todo items, repointing an ambiguous link, writing frontmatter that asserts status, tying an orphan into the graph.

### Procedure

1. `python3 "$AUDIT" --json` (add `--vault PATH` to audit a vault other than `$SECOND_BRAIN_VAULT`). Exit 2 = fail findings, 1 = warn only, 0 = clean.
2. `python3 "$OP/vault-vitals.py"` for the curated-layer metrics (orphans, dead links, `../` links, frontmatter gaps). The audit's own `vitals_trend` check reads a trend file this plugin does not write, so on most vaults it reports "trend NOT checked"; the vitals run is the measurement.
3. Walk findings most-severe first. Mechanical fixes (file moves, index rebuilds, single-field frontmatter) apply now. Semantic fixes (routing rewrites, hub/board reconciliation wording, anything touching canon meaning) are proposed to the owner per item.
4. Route by finding type: `canon_budgets` and `canon_rule_count` go to canon-slim; `todo_hygiene` to todo-groom; orphans, dead links and frontmatter gaps to vault-groom.
5. Close: one summary in chat (counts, what was applied, what waits on the owner), daily-log entry at wrap. No HTML, no report file unless the owner asks.

### Output example

```
vault-audit 2026-08-18: 19 checks: 1 fail, 6 warn, 2 info
Applied now (2): moved 2 root strays to .backups/, backfilled one hub's last_touched.
Routed (2): rules file over hard line -> canon-slim ledger for the owner; dead links -> vault-groom queue.
Owner's call (1): retire or revive a capture folder that has been dark for 84 days.
```
