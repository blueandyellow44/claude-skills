---
name: morning-agenda
description: "Forward-looking daily agenda for the vault's owner. Triggers on 'what's on the agenda', 'what's on deck', 'what's on deck today', 'morning agenda', 'what do I have today', 'agenda check', 'today's plan', 'what's coming up today'. Pulls today's calendar events (through a calendar connector of your own), open items from the latest session handoff in Resources/Prompts/, and Still-open work from Tasks/todo.md. Output is a chat briefing, not a vault file. Companion to daily-generator (which logs what already happened); this one projects what is coming."
user-invocable: true
---

# morning-agenda

Skill assets: `assets/briefing-template.md`. Skill references: `references/voice-deferral.md`.

A forward-looking briefing. The mirror of "what did I do today." Pulls together calendar, open work, and project hub state so the owner can wake up, type one phrase, and see the day.

This skill never writes to the vault. It returns a markdown briefing to chat. The output is ephemeral by design.

---

## When to use this skill

Trigger on any of:

- "what's on the agenda"
- "what's on deck" / "what's on deck today"
- "morning agenda"
- "what do I have today"
- "agenda check"
- "today's plan"
- "what's coming up today"

If another installed skill already claims "morning briefing," "daily brief," "prep my day," or "start my day," leave those phrases to it rather than competing.

Also skip this skill when the user asks "what did I do today" or any backward-looking variant. Those go to the existing daily review path.

---

## Workflow

```
START
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 1: GATHER STATIC DATA (script)                    │
│ • Run gather_agenda.py against the vault                │
│ • Returns JSON with:                                    │
│   - latest_handoff_path + open_items[]                  │
│   - todo_open[]    (from Tasks/todo.md latest review)   │
│   - active_projects[]  (from Projects/*/  hubs)         │
│   - voice_rule_reminder (1 line, only if relevant)      │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 2: GATHER LIVE DATA (calendar connector)          │
│ • List today's events with your calendar connector      │
│   (primary calendar, time_min/max: today, TZ-aware)     │
│ • If none is connected → skip with a [!todo] callout    │
│ • Never crash on auth failure, always render briefing   │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 3: SYNTHESIZE                                     │
│ • Format using briefing-template.md                     │
│ • One-line "Suggested focus" at the bottom, pick the    │
│   single highest-leverage item given the day's context  │
│ • Cite source files for each section                    │
│ • Output to chat. Do NOT write to a file.               │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation

### Step 1: Run the gather script

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable. The script reads it; with it unset (and no `--vault`) the script prints an error object and exits 2.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/morning-agenda/scripts/gather_agenda.py"
```

The script returns JSON to stdout. Schema:

```json
{
  "today_iso": "2026-04-26",
  "today_human": "Sunday, April 26, 2026",
  "latest_handoff": {
    "path": "Resources/Prompts/session-handoff-2026-04-26-eod.md",
    "title": "Session Handoff, 2026-04-26 EOD",
    "open_items": ["...", "..."]
  },
  "todo_open": ["...", "..."],
  "active_projects": [
    {"name": "Alpha-Site", "hub": "Projects/Alpha-Site/Alpha-Site.md"},
    {"name": "Garden-Book", "hub": "Projects/Garden-Book/Garden-Book.md"}
  ],
  "warnings": []
}
```

If the script fails entirely, fall back to a minimal briefing using only calendar data and tell the owner.

### Step 2: Call the calendar connector

This plugin ships no calendar access. Use whatever calendar connector is available in this session (a tool that lists events for a date range; for Google Calendar, its list-events tool):

- calendar: the primary one
- `time_min`: today at 00:00 in the owner's local time zone (the machine's zone unless the vault's `Context/` says otherwise)
- `time_max`: today at 23:59:59
- at most 25 results

**Interpreting the response** (the shapes below are Google Calendar's; adapt to your connector):

- **Response has an `events` array (with one or more entries)**: render those events normally.
- **Response is `{accessRole, summary, timeZone, updated}` with NO `events` key**: this is the API's "zero events" signal, not an error. Render the section as `- (no events today)`. Do NOT add a `[!todo]` callout. The day is genuinely empty.
- **Response is an error object or the call throws (auth, connection), or no calendar connector is available**: render `> [!todo] Calendar connector error: <details>` and continue.

The distinguisher: a metadata-only response means the calendar is reachable AND empty. An error response means the calendar is not reachable. Treat them differently.

### Step 3: Render the briefing

Use the structure in `assets/briefing-template.md`. Output to chat.

**Voice rules**: This is a status snapshot, not prose under the owner's name. The vault's writing-voice rules do NOT apply. Use plain technical language. No marketing copy. No announcer lines.

**Suggested focus**: One sentence at the bottom, naming the single highest-leverage item. Pick from open handoff items first, then todo, then upcoming meetings. If everything looks low-stakes, say so.

**Pipeline health**: If `~/.claude/session-state/pipeline-health.json` exists and its `warnings` array is non-empty, surface each warning as one line under a "Pipeline health" heading. That file is written only by a startup probe of your own that watches capture pipelines; nothing in this plugin writes it. If the file is absent, skip silently.

**Citations**: At the end of the briefing, list the source files (vault-relative paths).

---

## Failure modes

1. **Calendar connector missing or not authenticated**. Skip the section with a `> [!todo]` callout. Briefing still renders.
2. **`Tasks/todo.md` missing or malformed**. Script returns a warning in the `warnings[]` array. Skill surfaces the warning at the top of the briefing.
3. **No handoff files in `Resources/Prompts/`**. Script returns `latest_handoff: null`. Skill omits that section.
4. **`SECOND_BRAIN_VAULT` unset, or the vault path does not exist**. Script exits with code 2 and an `error` field. Skill tells the owner what the script said; it does not guess another path.
5. **Subagent loops or stalls during Calendar call**. Use `max_results: 25` and a sane time range. Do not retry more than once on transient errors.

## Verification (before declaring a run successful)

- [ ] Briefing rendered with at least one of: Calendar, handoff, todo
- [ ] Source citations present at the bottom
- [ ] Suggested focus is one sentence and references a real item
- [ ] No voice-profile prose accidentally inserted
- [ ] No file written to the vault

## Rollback

This skill writes nothing persistent. To roll back: ignore the trigger and the briefing is gone.
