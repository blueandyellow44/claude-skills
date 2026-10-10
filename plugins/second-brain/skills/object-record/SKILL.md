---
name: object-record
description: "Pull the decision record of ONE object in ANY project before it is edited (a file, feature, component, prompt, image asset or sprite): its git history with every prior version viewable, the hub rules, project memory and lessons that name it, and the owner's own words about it from the transcripts. The project is resolved from the working folder (or --project). Use before any edit to a thing the owner has ruled on or approved, and whenever the user says 'we decided this', 'you had it right before', 'we fixed this already', 'check the record', 'object record', or names a specific piece (e.g. the pricing table, the header clock, the opening view). Not for a whole-project orientation."
allowed-tools:
  - Bash
  - Read
  - Edit
---

# object-record

It works in any project: the hub, every Claude Code project-memory folder and every transcript folder that resolve to the project are found by `project_resolver.py` beside the script (see "How the project is resolved" in the plugin README). The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable; the script stops with a message when it is unset. Per-project data (name aliases, the default path for a bare slug, standing notes, extra transcript folders) lives in an optional `Projects/<Hub>/object-record.json` in the vault.

## Goal

Before one object changes, the session knows what was decided about that object, by whom, what was rejected and what was approved. The record is read per object, every time, not once at session start.

## Why this exists

A piece gets redrawn twice while the version its owner called perfect is one `git log` away. The project record was read at session start and never again for the object on the table. The lesson: before touching a thing, read ITS record.

## Tools

Bash (git, python3; Pillow only for the image contact sheet), Read (to look at the contact sheet). No browser, no network.

## Steps

1. **Run the script.** From the project's folder:
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/object-record/scripts/object_record.py" <slug-or-path> [--alias "other name"] [--project <hub>]`
   A bare slug resolves to the config's `default_path`, else to any tracked file whose name is the slug, else to commits, hub, memory and words only.
   It writes `.agents/object-records/<slug>-<YYYYMMDD>.md` inside the project's repo, and for a `.png` it exports every committed version to `.agents/object-records/<slug>/versions/` and builds a contact sheet.
2. **Look at the contact sheet** with the Read tool. This step is obligatory for an image. A version the owner approved is recognized by eye and by date, not by its commit subject.
3. **Read each lessons.md entry the record names**, in full, at the line numbers given. Read the commit bodies that name the object: `git show -s <sha>`. Reading these is obligatory; the list alone is not the read.
4. **Read the owner's words in section 5.** Two tiers, kept apart. NAMED: they typed the object's name. CONTEXT ONLY, UNCERTAIN: they did not name it and the assistant's turn just before was about this piece alone; each such line is a lead, so open the transcript row given and read what was being answered before quoting it as about this object. Remarks made while several pieces were on the table are not attributed to any of them. Text they pasted, text copied back from the assistant, scripted prompts and third-person relays are never shown as their words. (The CONTEXT tier needs the object's aliases in `object-record.json`.)
5. **Fill in section 6 of the record** (decided, rejected, approved version, what the planned change touches and which ruling covers it). Evidence only; no recall. If the planned change reverses a ruling, stop and ask the owner one closed question before editing.
6. **Report the brief in chat** in five lines or fewer before the first edit.

## The optional per-project config

`Projects/<Hub>/object-record.json`, every key optional:

```json
{
  "aliases": {"clock-tower": ["the clock", "tower clock"]},
  "default_path": "public/sprites/{slug}.png",
  "extra_transcript_globs": ["-Users-me-other-folder/*.jsonl"],
  "standing": [{"title": "Sprite notes", "when_path_prefix": "public/sprites/", "lines": ["Sprites are 512px, transparent background."]}]
}
```

## Rules

1. Reading the named lessons, commit bodies and the contact sheet is obligatory at the named steps. The skill does not get to skip them.
2. An empty search is not a negative. "No record on this machine" is the most that can be said; name what was not searched (other machines, chat surfaces, phone sessions).
3. Messages typed while the assistant was working are stored as `queue-operation` rows in the transcript, not `user` rows. Any hand search of transcripts must include them; the script does, once per message.
4. If the owner says "we decided this", run this skill before answering, then record the ruling with `ruling-capture` the same turn.
5. A re-run refreshes the evidence. A re-run on the same day rewrites that day's record file, section 6 included, so copy a brief you already filled in back into it. Never delete a record.
6. No hook enforces this skill. The rule is to run it before the edit, every time.
7. When the owner defines a thing this skill should not do, record that as a ruling in the project hub the same turn.

## Output

The record file path, and a brief of five lines or fewer in chat: decided, rejected, approved version, what the change touches, and whether the owner's word is needed.
