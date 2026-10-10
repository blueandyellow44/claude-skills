# second-brain

A session manager for a markdown vault. It keeps what a Claude Code session did, decided and left open in files you own: a daily log, a todo list, one hub note per project, a lessons file and a short rules file. The vault is plain markdown that opens in Obsidian; nothing here needs Obsidian to run.

It is a public export of a plugin built for one vault and then made generic. The skills assume the layout below. They do not adapt to a different one.

## Setup

1. Set `SECOND_BRAIN_VAULT` to the absolute path of your vault, somewhere Claude Code's shell will see it (your shell profile, or `env` in Claude Code's settings).

       export SECOND_BRAIN_VAULT="$HOME/notes"

   Every script reads this variable. When it is unset a script stops with a message; none of them guesses a path. Most also take `--vault PATH`.
2. No vault yet? Run the `vault-setup` skill. It asks where the vault should live, scaffolds the layout below from templates, and tells you what to set the variable to.
3. Python 3 and git (the scripts were run on Python 3.14). A few steps want more:
   - PyYAML: the audit's `hub_yaml` check, `check_base_syntax.py`, and the frontmatter check in `ruling-capture`.
   - Pillow: only for the image contact sheet in `object-record`.
4. Optional: set `SECOND_BRAIN_OWNER` to your first name (comma-separated for several). `object-record` and `ruling-capture` then treat messages that speak about you in the third person as relays, not as your own words.

## The layout these skills expect

```
<vault>/
  CLAUDE.md                  routing: what lives where, startup read order
  Rules-of-Engagement.md     the short, always-read list of active rules
  Home.md, Start-here.md     the two pages written for the owner, not the AI
  Daily/YYYY-MM-DD.md        one note per day: a "## Log" with one "### <title> (<surface>)" entry per session
  Tasks/todo.md              forward-only open work
  Tasks/lessons.md           the full story behind each rule, under "## YYYY-MM-DD" headings
  Tasks/journal.md           completed todo blocks, moved here verbatim
  Projects/Projects.md       the board: one row per project
  Projects/<Name>/<Name>.md  a project hub: frontmatter status, last_touched, next_step; "## Rules"; "## Log"
  Context/                   durable facts about the owner and their world
  Intelligence/              captured material: transcripts, sources, research
  Resources/operator/        state files the scripts write (logs, ledgers, your own config)
  Resources/Prompts/         session handoffs (session-handoff-YYYY-MM-DD-xx.md)
  Resources/Reviews/         weekly reviews
  Skills/                    your own notes for skills, and skill drafts
  _inbox/                    unsorted capture
  .backups/                  snapshots taken before a canonical file is edited
```

Each folder has its own `CLAUDE.md` saying what belongs in it. `vault-setup` writes all of this.

## Skills

| Skill | What it does | Needs |
|---|---|---|
| `session-wrap` | End of session: commits repo work, checks off todos, appends the daily entry, updates the project hub and project memory, logs lessons, records candidates for new skills | the vault |
| `session-ledger` | Keeps the session's request, requirements, decisions and done-conditions in a file, and checks work against it | nothing (writes under `~/.claude/session-state/`) |
| `ruling-capture` | Writes the owner's decision into the project hub and project memory the turn it is made; a sweep lists decisions in transcripts that never reached the hub | the vault, a project hub |
| `object-record` | Before one thing is edited: its git history, the rules and lessons that name it, and what the owner said about it | the vault, a project hub, a git repo |
| `vault-setup` | Scaffolds a new vault: folders, routing files, Obsidian config, templates, an optional audit script | nothing |
| `vault-doctor` | Runs the 19-check vault audit and the vitals script, then walks each finding to a disposition | the vault |
| `vault-groom` | Fixes what the vitals measure: dead links, `../` links, orphans, missing frontmatter | the vault |
| `todo-groom` | Moves finished todo blocks to the journal; proposes chain collapses and age triage | the vault |
| `canon-health` | Judges whether the always-loaded rules are small and few enough to be followed | the vault |
| `canon-slim` | Builds a ledger of rules to keep, move to lessons, or compress; edits only after the owner rules | the vault |
| `weekly-review` | Writes a weekly review from the week's lessons, rules, dailies and captures, with one calibration question | the vault |
| `morning-agenda` | Chat briefing: today's calendar, open items from the last handoff, open todos, active projects | the vault; a calendar connector for the calendar part |
| `daily-generator` | End-of-day sheet from calendar, sent email and git activity in folders you list | the vault; calendar and email connectors for those parts |
| `calendar-summary` | Sidecar note with today's events and sent email | the vault; calendar and email connectors |
| `handoff-audit` | Audits a session handoff document against a checklist before it is used | the vault |

Three agents ship for fan-out: `canon-compressor` (builds a canon-slim ledger and stops), `vault-finding-auditor` (read-only check that a finding is real), `vault-groom-worker` (applies one class of confirmed fixes).

The scripts the skills call are in `operator/` and in each skill's own folder. The four that edit your notes (`normalize-wikilinks.py`, `tie-orphans.py`, `todo-mover.py`, `relocate-misfiled-backups.py`) are dry-run unless given `--apply`.

## How the project is resolved

`object-record` and `ruling-capture` need to know which project hub a working folder belongs to. `skills/object-record/scripts/project_resolver.py` decides, deepest folder first:

1. a hub that lists the folder under `workspaces:` in its frontmatter owns it;
2. else a hub whose folder name, `title` or an entry in `aliases:` equals the folder's name;
3. else the hub whose text mentions the folder as `~/path`, if it is the only one or mentions it at least twice as often as the next.

Otherwise nothing resolves and the script asks for `--project <hub name>`. Add `workspaces: [~/code/your-repo]` to a hub to settle it. A session run with the vault itself as the working folder never resolves to a project.

## What is not included

- **Hooks.** The source vault runs hooks that deliver the daily, todo and project hub into every session at start, re-deliver the session ledger after compaction, remind about unwrapped sessions, and surface matching lessons on each prompt. None of them ship. Each skill says where it would have used one. The practical cost: nothing reminds a session to wrap or to re-read its ledger, and a rule moved out of the rules file into `Tasks/lessons.md` is found again only when a session searches that file.
- **Calendar and email access.** `morning-agenda`, `daily-generator` and `calendar-summary` use whatever connectors your session has. Without one they still run and mark that section as not connected.
- **The `sessions-index` skill.** It indexes captured session transcripts per project, and the transcripts come from a separate capture plugin that is not published.
- **Sync and scheduling.** No autosync job, no scheduled tasks. `skills/vault-doctor/run-weekly.sh` is a script you may schedule yourself.
- **Mirrors and load checks.** `canon-slim` used a script that live-tests whether a slimmed rules file still loads; here that step is done by hand.

## Known limits

- `morning-agenda` and `weekly-review` read open items from a `**Still open**` block in `Tasks/todo.md` (under a `## Session review` heading for the agenda). The `vault-setup` todo template has no such block, so both report no open loops until your todo file has one. Neither reads the `## Active` list.
- `weekly-review` links each review to a note named `Reviews`. Create `Resources/Reviews/Reviews.md`, or that link is dead.
- `daily-generator` writes a sectioned day sheet; `session-wrap` and the templates use one log entry per session. A vault can hold both, but should name one as its format in `Daily/CLAUDE.md`.
- `normalize-wikilinks.py` repairs renames and aliases only from two maps inside the script, which ship empty. A vault that needs them keeps its own edited copy.
- `vault-vitals.py` watches no capture pipelines until you list yours in the script; the audit's `vitals_trend` check reads a trend file nothing here writes, and says so.
- `object-record` and `ruling-capture` read Claude Code transcripts from `~/.claude/projects/` on this machine only. An empty result is not proof that nothing was said.
- The scripts were written on macOS. `run-weekly.sh` is bash.

## What was run

On the export itself, on macOS with Python 3.14: every script in the plugin was run at least once against a scratch vault built from the `vault-setup` templates, and each script that reads `SECOND_BRAIN_VAULT` was also run with it unset. The four bundled test files pass (`operator/test_todo_mover.py`, `operator/test_capability_candidates.py`, `skills/session-ledger/tests/test_ledger.py`, `skills/vault-setup/references/operator/test_vault_audit.py`), as do the seven sweep cases in `skills/ruling-capture/tests/sweep_cases.py`. The audit exits 0 on that scratch vault.

Not run: the skills as prompts inside a Claude session, the agents, anything against a calendar or email connector, and a scaffolded vault opened in Obsidian.
