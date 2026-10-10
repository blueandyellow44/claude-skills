---
type: skill-reference
skill: handoff-audit
updated: 2026-05-03
---

# handoff-audit CHECKLIST

The audit criteria for a session-to-session handoff document. The skill `handoff-audit` reads this file at runtime. Edit here when you discover a new failure mode worth catching.

---

## REQUIRED sections (P1 if missing)

Every handoff doc must have ALL of these. A miss is a P1 finding.

### 1. Header block with paste-this-prompt instruction

The opening lines must tell the next session HOW to load the handoff. Concrete prompt format the user can paste into a fresh session. Without this, the handoff is just a memo, not a usable bridge.

Example: `> **Paste this entire file into a fresh session and tell Claude: "load handoff at \`<absolute path>\`".**`

### 2. "What you are inheriting" summary

One paragraph. Quantitative state (file counts, version numbers, what shipped). Qualitative urgency (what matters this week, what is blocked). Should NOT exceed five sentences.

### 3. Universal-rules read list

The handoff MUST tell the new session to read these BEFORE doing project-specific work:

- Vault root `CLAUDE.md` (routing layer and startup order)
- `Rules-of-Engagement.md` (the active operational rules)
- The vault's writing-voice rules, if it keeps any (`Context/voice-and-writing.md`, a `Context/voice-profile/` folder)

If the universal-reads section is missing, it is P1 even if the project-specific reads are perfect. The next session needs the vault's rules loaded before it writes anything on the owner's behalf.

### 4. Project-specific reads list

Files for the active work. At minimum: `Tasks/lessons.md`, `Tasks/todo.md`. Plus any skill READMEs or HANDOFF docs the next session will need. Order matters; put the most-critical first.

### 5. State of the world

Bulleted, quantitative. File counts, item counts, version markers. The next session should be able to verify the handoff matches reality with two or three Bash commands. If a number is in the handoff, it must be checkable.

### 6. Open items in priority order

Use explicit High / Medium / Low headers. Each item: what, why it matters, what blocks it (if anything), recommended next action. If an item has been blocked for more than two sessions, flag the blocker explicitly so the next session does not waste time on it.

### 7. Critical operator notes

Vault-specific or session-specific gotchas the next session WILL hit if not warned. Examples: tool permission constraints, mount-table quirks, voice-rule overrides, banned outputs, file-system separation between Write tool and bash sandbox.

### 8. "Maintain a running handoff as you work" instruction

The new session must be told to UPDATE the handoff as work progresses, not write one only at session end. Without this, a crash or context-fill mid-session loses everything since the previous handoff. Required language: instruct the next session to write or update `Resources/Prompts/session-handoff-YYYY-MM-DD-XX.md` after milestones, before risky operations, and any time context approaches limit.

### 9. "What this session shipped" record

Bulleted list of changes made in the session that produced this handoff. The next session uses this to understand what is new vs what was already there. Include code modifications, file moves, deletions, lessons added.

### 10. "If the user just says continue from handoff" guidance

A specific recommended action sequence the next session should follow if the owner gives no direction. This prevents the next session from re-asking what to work on.

---

## VOICE VIOLATIONS (P2, narrow scope only)

Writing-voice rules apply ONLY to user-facing prose drafted for someone other than the owner to read under the owner's name. Handoff documents are internal session-state artifacts and are OUT OF SCOPE. Do NOT flag dashes, contractions, or other style patterns as P2 findings on the handoff body itself.

The narrow exception: if the handoff contains a draft email, message, briefing doc, blog post, or other user-facing prose staged for the owner's review (e.g., embedded inside a `> ` blockquote or inside a code block labeled as draft text), apply the vault's voice rules to that embedded content only. Flag as P2. A vault with no written voice rules has nothing to flag here.

Always flag, regardless of scope:

### Banned outputs (any context)
- "No response requested", banned without exception.

### Self-superseding language inside the doc
If the handoff itself states a voice rule (e.g., quotes a no-em-dash rule from the vault's rules file) and then immediately violates that quoted rule in the same paragraph, that is a P0 self-contradiction (see INTERNAL CONTRADICTIONS section below), not a P2 voice issue.

---

## INTERNAL CONTRADICTIONS (P0 if found: highest priority)

These mislead the next session. Always check:

### State count consistency
The numbers in "State of the world" must match the numbers used elsewhere in the doc. Example: if state says "196 sessions captured" but a later section says "197 files," that is P0.

### todo.md alignment
Open items in the handoff must not contradict `Tasks/todo.md`. If the handoff says "v1.4 done" but todo.md still has v1.4 as in-progress, that is P0. Either the handoff is wrong or todo.md is stale; the audit must flag the mismatch and recommend which to update.

### Priority label vs recommended order
If "Recommended order" in the "If user says continue" section does not begin with the highest-priority open item, that is a contradiction. Either the priority label is wrong or the recommendation is wrong.

### Voice rule meta-violation (rare)
Only fires if the handoff doc itself QUOTES a voice rule (e.g., copies a no-em-dash rule into its own body for emphasis) and then violates the quoted rule in the same paragraph. Bare dashes or contractions in handoff prose are NOT a P0; they are out of scope. P0 here only when the doc is internally self-contradicting itself.

### Self-superseding language
If the handoff supersedes a prior handoff, it must say so in YAML frontmatter (`supersedes: <prior-filename>`). If it does not, the next session may load both and be confused about which is current.

---

## ACCURACY VERIFICATION (P0 if any check fails)

The handoff's claims about state must match the actual filesystem. If a number appears in the handoff, it must be verifiable in 30 seconds with a bash command. Run these checks on every audit.

### File counts
For every claim like "X files in Y/" or "Z entries in /path/", run `ls | wc -l` or equivalent. Mismatch is P0.

### Line counts
For every claim like "ROE is 145 lines" or "todo.md grew from 504 to 526," run `wc -l <path>`. Off-by-one is tolerable (frontmatter or trailing-newline rounding). Off by more than 5 is P0.

### Path existence
For every absolute path or file link cited as live, verify `ls -d "<path>"` succeeds. A handoff that links to a deleted folder is a trap for the next session.

### Command syntax
For every shell one-liner the owner is told to run, parse for: balanced quotes, no smart-quote contamination (`"..."` not `“…”`), no unescaped spaces in paths inside double-quoted strings, no shell-injectable substitutions. Past failures: smart-quote pasted from chat as `“…”` instead of `"..."`, breaking the rm.

### Command outcome (when the owner already ran something)
If the handoff says the owner ran a cleanup command in this session, verify the filesystem reflects the expected outcome. Example: a cleanup one-liner deleted four folders; an audit run afterward must confirm the four folders are gone, otherwise the handoff is misrepresenting state.

---

## FRESHNESS / UP-TO-DATE (P1 if stale)

A handoff written mid-session goes stale fast. Anything that happened after the handoff was last written but before audit time must be captured. Check.

### Latest session work captured
Compare the handoff's "What this session shipped" section against the files actually modified in the current session. If a file was edited after the handoff was generated, the handoff is stale. P1.

### todo.md sync
The handoff's open items must match what is currently in `Tasks/todo.md`. If todo.md was updated after the handoff was written (e.g., a Session review block appended), the handoff must reference the new state.

### lessons.md / ROE sync
If new lessons were appended in this session, the handoff's "What this session shipped" must list them. If the active rule was also added to ROE, the handoff should call out the ROE update.

### Daily file sync
The current `Daily/<today>.md` must reflect the state the handoff describes. If the handoff describes Session 3 work but Daily/<today>.md only has Session 1 and 2, that is P1.

### Time-of-day suffix matches reality
A handoff filename suffix `-eod` written at 16:00 is misleading if work continued until 22:00. Either rewrite the file to reflect EOD reality or use a more accurate suffix.

---

## RECOMMENDED sections (P3 if missing)

Not strictly required but improve handoff quality:

### YAML frontmatter
At minimum: `type: session-handoff`, `date: YYYY-MM-DD`, `time: AM | PM | EOD`, `supersedes: <prior-filename>`, `links: ["[[<date>]]", "[[<active-project>]]"]`. Helps Obsidian indexing and navigation.

### Time of day in filename
`session-handoff-YYYY-MM-DD-pm.md` not just `session-handoff-YYYY-MM-DD.md`. Multiple handoffs per day are common during heavy work, and the suffix prevents collision.

### Wiki-links to active hubs
The handoff body should wikilink the active project hubs and the day's daily note. Connects the handoff into the graph and prevents it from being a true orphan.

### Distinction between true file orphans vs unresolved-link ghosts
If the handoff mentions graph orphans, it should clarify whether it means:
- True file orphan: a real .md file with no incoming or outgoing edges
- Unresolved-link ghost: a wikilink pointing at a file that does not exist
The fixes are different. Conflating them is a P3 clarity issue.

---

## SUGGESTIONS (P4)

### Sentence-start variety
No more than three consecutive sentences starting with the same word, especially "I" or "The".

### Section length
A "What this session shipped" section longer than 15 bullets is probably too granular. Roll up similar items.

### Time references
Prefer absolute dates (`2026-04-26`) over relative references (`yesterday`, `today`). The next session may be reading the handoff days later.

### Clickable links
For files the owner should open from the handoff, prefer a clickable link over a plain path where the reading surface supports one.

---

## Audit output format

Always group findings in this order: P0 (contradictions), P1 (missing required), P2 (voice), P3 (missing recommended), P4 (suggestions). Within each group, sort by location in the document (top to bottom). End with a one-line summary of counts and a recommendation for next action.
