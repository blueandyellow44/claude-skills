# voice-deferral.md

When daily-generator runs, the vault's writing-voice rules apply selectively. Most
of the Daily file is mechanical and should NOT be written as prose.

## Sections that are mechanical (no voice rules)

- **Frontmatter**: copy from the skeleton verbatim, fill `{{DATE}}`.
- **Log**: bullet-list of timestamped entries from calendar events, sent
  emails, and git commits. Terse. Like an itemized receipt.
- **Meetings**: name, time, attendees, link to meeting-notes if found.
- **New in the vault today**: list of files created or modified today
  (from git activity or file mtime).

These sections are literal data. Do not rewrite, do not editorialize, do not
add adjectives. Bullet lists are fine here.

## Sections that MAY take the owner's voice (only if the owner asks for prose)

- **Focus**: a one-line summary of the day's intent. Default to the literal
  bullet-style placeholder from the skeleton (`(what am I working on today?)`).
  Only switch to prose if the owner has asked for prose Daily files in their
  standing instructions.

- **Decisions**: terse bullets by default. If the owner asks for narrative,
  follow their voice rules.

- **Tomorrow**: one bullet, action-oriented. No prose unless asked.

## Where the voice rules live

If a section needs prose AND the owner has signaled a prose preference, read the
vault's writing rules before drafting: `Context/voice-and-writing.md`, and a
`Context/voice-profile/` folder if the vault keeps one. Neither is created by this
plugin. If the vault has no such file, write plain, short sentences and add a note
at the top of the file: `> [!warn] no voice rules found in Context/; prose
sections written plainly.`

## Default behavior

When in doubt, write terse bullets. The Daily file is a log, not an essay.
The owner edits it after the fact if they want prose. Generating prose they then
have to rewrite is wasted work.
