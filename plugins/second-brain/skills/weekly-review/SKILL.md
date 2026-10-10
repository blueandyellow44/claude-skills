---
name: weekly-review
description: Scan the vault for this week's activity and write a review file at Resources/Reviews/YYYY-W##.md with a single calibration question. Auto-flags if last week's answer slot was empty. Catches the "vault is decorative" failure mode.
allowed-tools: Bash, Read, Write
---

# weekly-review

Sidecar: `assets/template.md` (the rendered structure).

Generates a weekly review file at `Resources/Reviews/YYYY-W##.md` in the vault.

## When to invoke

- **On a schedule of your own** (a Sunday-morning scheduled task suits it). Nothing in this plugin schedules it.
- **On-demand trigger phrases**: "weekly review", "week in review", "vault check", "review the week".

## What it does

For the past ISO week (Monday through Sunday), scan and aggregate:

1. New lessons logged in `Tasks/lessons.md` (entries dated `[YYYY-MM-DD]` falling in the week).
2. New entries in `Rules-of-Engagement.md` (bulleted rules whose most recent `YYYY-MM-DD` date on the line falls in the week).
3. `Daily/<date>.md` entries with non-trivial content.
4. `Intelligence/Cowork-Sessions/` files matching the date prefix range.
5. `Intelligence/Sources/` captures matching the date prefix range.
6. Latest `**Still open**` bulletlist from `Tasks/todo.md` (snapshot of current open loops).

Then two judgment passes over the week's material (these are model reasoning, not regex, they need cross-session context a live hook cannot see, which is why they live in the weekly review):

7. **Repeated-discussion detection.** Scan the week's Daily entries and captures for the same topic, decision, or question surfacing across ≥3 separate sessions without a durable home. Each cluster is a candidate for permanent documentation (a Context file, a lessons entry, or a project-hub section). Propose the doc; do not write it unattended.
8. **Doc-vs-implementation drift.** For each project touched this week, spot-check whether its hub / CLAUDE.md / spec still matches what the code or vault actually does (e.g. a documented path that moved, a retired workflow still described as live, a size or cadence figure that is now stale). Flag mismatches with the file and line.

Render into a templated review file with the calibration question at the top:

> **Did the vault help me find or write or decide anything this week?**
>
> Answer:

The script reads the previous week's review file. If last week's `Answer:` slot is empty or whitespace, render an `[!warning]` callout above this week's question. Two consecutive empty answers means the vault is not earning its keep that period, which is the signal this skill exists to surface.

## Usage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/weekly-review/scripts/run.py"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/weekly-review/scripts/run.py" --week 2026-W18
python3 "${CLAUDE_PLUGIN_ROOT}/skills/weekly-review/scripts/run.py" --dry-run
```

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable. With it unset the script prints an error and exits 2; it never guesses a path.

## Files

- `scripts/run.py`: scanner + renderer (Python 3 stdlib only: `datetime`, `glob`, `re`, `pathlib`, `argparse`).
- `assets/template.md`: documentation of the rendered structure (the script renders inline; this file is a reference for future maintenance).

## Output

Writes to `Resources/Reviews/YYYY-W##.md` in the vault. Idempotent within a week (same week run twice = overwrite, keeping an answer already written in the calibration slot). Cross-week runs create a new file.

Returns to stdout:
- The output path.
- Section population counts (lessons, ROE, daily, sessions, sources, open_loops).
- A FLAG line if the previous week's calibration was empty.
- A NOTE line if no previous week file exists.

## Constraints

- All data sources are vault paths.
- No external API keys or network calls.
- Python 3 stdlib only.
- ISO-week math uses `datetime.date.fromisocalendar()` to handle year boundaries.

## Data shape conventions assumed by the scanner

The formats the scanner reads (do not change them without updating the scanner):

- `Tasks/lessons.md`: `## YYYY-MM-DD` date sections, each lesson a `### Rule: <headline>` entry under its date (an optional `[Project]` tag before `Rule:` is read as the project). The older flat form `- [YYYY-MM-DD] [Project] Rule: <prose>` is still read.
- `Rules-of-Engagement.md`: each rule is a bulleted line beginning `- **<headline>**` that carries at least one `YYYY-MM-DD` date.
- `Intelligence/Cowork-Sessions/<YYYY-MM-DD> <slug>.md` filename convention.
- `Intelligence/Sources/<YYYY-MM-DD> <title>.md` filename convention.
- `Tasks/todo.md`: `**Still open**:` followed by 4-space-indented bullet items. A todo file without that block (the vault-setup template has none) yields an empty open-loops section, not an error.

If any of these conventions change, update the scanner's regex patterns in `scripts/run.py` accordingly.

## Why this exists

The vault compounds value only if it earns its keep each week. The single calibration question is the lowest-friction signal. Two consecutive weeks of empty answers means the vault is decorative, and the skill itself becomes the prompt to either fix the vault or stop pretending it is helping.
