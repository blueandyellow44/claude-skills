# Weekly Review template (reference)

The `scripts/run.py` script renders the review inline. This file documents the structure for future maintenance. Do not modify the rendered output by hand if you want subsequent runs to behave deterministically.

## Section order

1. **Frontmatter**: `title`, `type: review`, `iso_week`, `week_start`, `week_end`, `generated`.
2. **H1**: `Weekly Review YYYY-W##`.
3. **Subtitle line**: a wikilink to a `Reviews` note, then `Week of <Mon Apr 27> to <Sun May 03, 2026>.`
4. **Trend banner** (conditional):
   - `[!warning]` if previous week's `Answer:` slot was empty.
   - `[!info]` if no previous review file exists.
   - Nothing if previous answer was filled in.
5. **Calibration** (always FIRST after trend banner):
   - Question: `**Did the vault help me find or write or decide anything this week?**`
   - Empty `Answer:` slot.
6. **New lessons logged**: dated entries from `Tasks/lessons.md`, summary truncated to first sentence or 240 chars.
7. **ROE entries dated this week**: rules from `Rules-of-Engagement.md` whose most recent date pointer is in the week.
8. **Daily entries**: one wikilink per daily file (named by its date) with > 300 bytes.
9. **Cowork sessions**: wikilinks to `[[<filename>|<slug>]]` for sessions matching the week's date prefixes.
10. **Captured sources**: wikilinks to `[[<filename>|<title>]]` for sources matching the week's date prefixes.
11. **Open loops**: snapshot of the most recent `**Still open**` bulletlist from `Tasks/todo.md`, capped at 20 items.

## Why calibration goes first

The owner needs to see the question before scrolling through summary content. The summary content is context for the answer, not the answer itself.

## Empty-week behavior

Every section renders `(none this week)` text rather than being omitted. This keeps the review file structurally consistent across weeks and makes it obvious when activity is genuinely zero.
