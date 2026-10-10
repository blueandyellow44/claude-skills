---
name: daily-generator
description: "Backward-looking end-of-day log generator. Drafts Daily/YYYY-MM-DD.md in the vault from today's calendar events, today's sent email, and git/file activity across configured project folders. Pre-fills Focus / Log / Meetings / New-in-the-vault sections from a skeleton. Mechanical by default, no prose generation. Never clobbers an existing daily file (writes to .draft.md instead). Needs a calendar connector and an email connector of your own for those two sections. Companion to morning-agenda. Triggers on 'log today's daily', 'write today's daily file', 'draft today's daily', 'end-of-day log', 'run the daily generator', 'what did I do today'."
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
user-invocable: true
---

# daily-generator

Skill assets: `assets/daily-skeleton.md.tmpl`. Skill references: `references/voice-deferral.md`.

You are running the `daily-generator` skill. Your job: write a single markdown
file at `Daily/YYYY-MM-DD.md` in the vault (or `.draft.md` if today's already
exists) summarizing today's activity from calendar, email, and project folders.

This skill is mostly mechanical. Default to terse bullets. Do NOT write prose
unless the owner has explicitly asked for prose Daily files. See
`references/voice-deferral.md` for the rule.

**Which daily format.** This skill writes a sectioned day sheet (Focus / Log /
Meetings / Decisions / ...). The session-wrap skill and the vault-setup templates
use a different shape: one `## Log` with a `### <title> (<surface>)` entry per
session. Both can live in one vault because this skill never overwrites an
existing daily file, but pick one as the vault's canonical format and say which in
`Daily/CLAUDE.md`.

**Connectors.** This plugin ships no calendar or email access. Use whatever
calendar connector (a tool that lists events for a date range) and email connector
(a tool that searches sent mail) are available in this session. If one is missing,
say which, mark its section with the `[!todo]` line below, and continue.

---

## Step 0: Resolve paths and date

- Vault root: the `SECOND_BRAIN_VAULT` environment variable
  (`echo "$SECOND_BRAIN_VAULT"`). If it is unset or not a folder, say so and stop;
  never guess a path.
- Output folder: `Daily/` in the vault.
- Today's date: get via `date +%Y-%m-%d` (local time on this machine).
- Skill folder: `${CLAUDE_PLUGIN_ROOT}/skills/daily-generator/`

---

## Step 1: Check for existing daily file

Glob `$SECOND_BRAIN_VAULT/Daily/<today>.md`. If it exists:

- Set the output target to `<today>.draft.md` (so we never clobber the owner's
  in-progress daily).
- Note in the response: "Daily/<today>.md already exists, wrote draft to
  Daily/<today>.draft.md, please merge."

If it does not exist:

- Output target is `<today>.md`.

---

## Step 2: Gather data sources

Run these in parallel where possible. Each source is independent, if one
fails, drop it and continue.

### 2a. Calendar (today)

Call the calendar connector's list-events tool with today's date range (00:00 to
23:59 local). Capture:

- Event title
- Start time
- Attendees (if any)
- Location or video link (if useful)

**Interpreting the response** (the shapes below are Google Calendar's; adapt to your connector):

- **Response has an `events` array**: render those events normally.
- **Response is calendar metadata (`{accessRole, summary, timeZone, updated}`) with NO `events` key**: this is the API's "zero events" signal, not an error. The day is genuinely empty. Write the Meetings section as `- (no external meetings today)` and do NOT include a `[!todo]` callout.
- **Response is an error object or the call throws (auth, connection)**: write `> [!todo] Calendar connector error: <details>` in the Meetings section.

The distinguisher: a metadata-only response means the calendar is reachable AND empty. An error response means the calendar is not reachable. Treat them differently.

### 2b. Sent email (today)

Call the email connector's search tool for mail the owner sent today (for Gmail,
the query `in:sent after:<today>`). Summarize each as:
`to <recipient>, subject "<subject>"`.

If the call fails or returns an auth error, mark the Log section's email
subsection `> [!todo] Email not connected this run` and continue.

### 2c. Project activity

Run the git/mtime scanner via Bash:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/daily-generator/scripts/git_today.py"
```

It reads the list of project folders from
`$SECOND_BRAIN_VAULT/Resources/operator/daily-generator.json` when that file
exists (or from `--config PATH`). Shape:

```json
{"repo_paths": ["~/code/alpha", "~/Alpha Site"], "skip_patterns": ["node_modules", ".git", "dist"]}
```

With no such file it uses the example config beside the script, which lists no
folders, and prints a line saying so. The first time that happens, ask the owner
which project folders to scan and write the config file.

This emits a markdown fragment listing today's commits per repo, with an mtime
fallback for non-git project folders. The script never crashes, empty output
or per-repo errors are handled internally.

Capture stdout into the New in the vault today section.

---

## Step 3: Compose the daily file

Read `${CLAUDE_PLUGIN_ROOT}/skills/daily-generator/assets/daily-skeleton.md.tmpl`
as the template. Replace `{{DATE}}` with today's date. Fill sections as follows:

### Focus

- One line, terse. Default placeholder: `- (one-line summary, fill in)`.
- Do not invent. If you cannot infer a focus from email/calendar with high
  confidence, leave the placeholder.

### Log

Reverse-chronological order is fine. Format each entry as:

```
- **<HH:MM>**, <event>
```

Combine calendar events and sent-email entries here. Skip recurring events
that did not produce content (e.g. blocking holds, focus blocks).

### Meetings

For each calendar event with attendees:

```
- <Event title>, <HH:MM>, <comma-separated attendees>
    - (notes inline)
```

If no meetings today, write `- (no external meetings today)`.

### Decisions

Default: keep the skeleton's placeholder line.
Do not invent decisions from calendar context.

### New in the vault today

Paste the output of `git_today.py` (Step 2c) here.

### Open loops / questions

Default: `- (nothing carrying to tomorrow yet, fill in or delete)`.

### Tomorrow

Default: `- (what should today's future-self tell tomorrow's today-self?)`.

### Related

Keep the template's links section verbatim.

---

## Step 4: Write the file

Use the `Write` tool. Path is `$SECOND_BRAIN_VAULT/Daily/<today>.md` or
`<today>.draft.md` per Step 1.

Do not use `Edit`. This is a new file.

---

## Step 5: Report back

Tell the owner:

1. Which file was written (full path).
2. Whether it was the canonical `.md` or a `.draft.md`.
3. Counts: N calendar events, M sent emails, K project commits/files.
4. Which sources were unavailable this run (calendar, email, project config) so
   the owner knows what to fill in.
5. The next obvious thing to do, e.g.:
   - "Review and merge if .draft.md was written"
   - "Fill in the Focus and Tomorrow lines"

If anything failed unexpectedly, name the failure mode specifically. Do not
say "I had trouble." Say what failed and what data is missing.

---

## When NOT to use this skill

- For forward-looking briefings, use `morning-agenda` instead.
- When the daily file is already complete and the owner wants to add something,
  edit it directly, do not regenerate.

---

## Known limitations

- **Calendar timezone parsing.** Calendar connectors return ISO timestamps; make
  sure to display them in the owner's local timezone when filling Log and
  Meetings.
- **Email thread vs message.** A thread search returns threads, not
  individual messages. For the sent-email summary, the thread subject is good
  enough; do not iterate per message unless asked.
- **Git mtime fallback.** If a project folder is not a git repo, the script
  uses file mtime which can be noisy (touched files != meaningful changes).
  Trust the count more than the file list.
- **No session-transcript ingestion.** This skill does NOT read session
  transcripts. The Daily file references that work happened, not transcript
  content.
