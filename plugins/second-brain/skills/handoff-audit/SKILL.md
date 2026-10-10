---
name: handoff-audit
description: "Audit a session-to-session handoff document against the rules in this skill's CHECKLIST.md. Manual triggers: 'audit handoff', 'review handoff', 'audit this handoff', 'is this handoff thorough', 'check the handoff', 'handoff audit', 'handoff review'. Automatic chain: also fires as the required final step of any session-handoff workflow ('save handoff', 'ship handoff', 'wrap up handoff', 'finalize handoff') so every fresh handoff gets audited before it is presented to the owner. Audits cover contradictions and accuracy (P0, filesystem vs claims), missing-required and freshness (P1, handoff vs current state), voice violations (P2), recommended sections (P3), and suggestions (P4). Produces findings grouped P0 through P4, ending with a one-line summary and recommendation."
user-invocable: true
---

# handoff-audit

Sidecar: `CHECKLIST.md` in this skill folder (the audit checklist).

Validates that a handoff document is complete, consistent, voice-compliant, and immediately usable by the next session.

The skill is a thin orchestrator. The audit criteria live in `${CLAUDE_PLUGIN_ROOT}/skills/handoff-audit/CHECKLIST.md`, which is the single source of truth. A vault can keep its own edited copy at `Skills/handoff-audit/CHECKLIST.md`; when that file exists, it wins.

The vault is the folder named by the `SECOND_BRAIN_VAULT` environment variable. If it is unset or not a folder, say so and stop; never guess a path. Handoffs live at `Resources/Prompts/session-handoff-*.md` in the vault.

---

## When to use this skill

### Manual triggers

- "audit handoff"
- "review handoff"
- "audit this handoff"
- "is this handoff thorough"
- "check the handoff"
- "handoff audit"
- "handoff review"

If the user does not name a specific file, default to the most recently modified `Resources/Prompts/session-handoff-*.md`.

Do NOT trigger on generic "review this" or "check this." The user must specifically reference a handoff or session-handoff doc.

### Automatic chain after session-handoff (required)

This skill is the final step of any session-handoff workflow. When the calling agent (or a handoff-writing skill of your own; none ships with this plugin) writes a fresh handoff to `Resources/Prompts/session-handoff-*.md`, the very next action is to invoke this skill against that path, unless the owner explicitly says "skip the audit" in the same turn.

Trigger phrases that imply this chain:

- "save handoff"
- "ship handoff"
- "wrap up handoff"
- "wrap up session"
- "finalize handoff"
- "save and audit handoff"
- "handoff prompt" (when paired with generation language)

The chain produces this overall flow:

1. The handoff file is written.
2. handoff-audit reads CHECKLIST.md and runs Phases 1 to 4 against the file.
3. handoff-audit reports findings, grouped P0 through P4.
4. If P0 or P1 findings exist, the agent fixes them in the handoff file and re-audits.
5. If only P2 to P4 findings exist, the agent surfaces them to the owner and lets the owner decide whether to ship.

To make this chain a standing rule in your vault, add it to `Rules-of-Engagement.md`.

---

## Workflow

```
START
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 1: LOCATE TARGET                                  │
│ • If user named a file: use that path                   │
│ • Else: glob Resources/Prompts/session-handoff-*.md     │
│   sorted by mtime, take the latest                      │
│ • Verify the file exists and is readable                │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 2: READ CHECKLIST                                 │
│ • Open this skill's CHECKLIST.md                        │
│ • Parse the P0 / P1 / P2 / P3 / P4 categories           │
│ • The checklist defines required sections, voice rules, │
│   contradiction checks, and suggestion criteria         │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 3: RUN CHECKS in priority order                   │
│                                                         │
│ P0 (contradictions + accuracy, highest priority):       │
│ • State count consistency across the doc                │
│ • todo.md alignment vs handoff "What is open"           │
│ • Priority labels match recommended-order ordering      │
│ • Voice rule meta-violation (quotes a rule, breaks it)  │
│ • Self-superseding YAML frontmatter present             │
│ • File / line counts in handoff match disk (run wc -l)  │
│ • Cited paths exist on disk (run ls -d)                 │
│ • Shell one-liners parse cleanly (no smart quotes)      │
│ • Already-run command outcomes match disk state         │
│                                                         │
│ P1 (missing required + freshness):                      │
│ • Header paste-this-prompt block                        │
│ • "What you are inheriting" summary                     │
│ • Universal-rules read list                             │
│ • Project-specific reads list                           │
│ • State of the world                                    │
│ • Open items in priority order                          │
│ • Critical operator notes                               │
│ • "Maintain a running handoff" instruction              │
│ • "What this session shipped" record                    │
│ • "If user just says continue" guidance                 │
│ • Latest session edits captured in handoff              │
│ • todo.md / lessons.md / ROE / Daily sync               │
│ • Time-of-day suffix matches reality                    │
│                                                         │
│ P2 (voice violations):                                  │
│ • Only inside embedded drafts meant for other readers   │
│ • The vault's own voice rules, when it has any          │
│ • Banned phrases (No response requested, etc.)          │
│                                                         │
│ P3 (recommended sections):                              │
│ • YAML frontmatter complete                             │
│ • Time of day in filename (-am/-pm/-eod)                │
│ • Wiki-links to active hubs                             │
│ • Orphan vs ghost distinction explained                 │
│                                                         │
│ P4 (suggestions):                                       │
│ • Sentence-start variety (no 3+ same-word runs)         │
│ • Section length (>15 bullets in any section)           │
│ • Absolute vs relative time references                  │
│ • Clickable links for files the owner should open       │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ Phase 4: REPORT                                         │
│ • Group findings P0 → P1 → P2 → P3 → P4                 │
│ • Within each group, sort by location in document       │
│ • End with one-line summary of counts                   │
│ • Recommend ship-as-is, fix-then-ship, or rebuild       │
│ • Cite the audited file                                 │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation

### Step 1: Find the target

If the user explicitly names a path, use that. Otherwise:

```bash
ls -t "$SECOND_BRAIN_VAULT/Resources/Prompts/"session-handoff-*.md | head -1
```

If zero matches, return: "No handoff docs found in Resources/Prompts/. Nothing to audit."

### Step 2: Read the checklist

Always read the checklist at runtime (the vault's own copy if it has one, else the one in this skill folder). Do not cache. The checklist is the source of truth and may have been edited since the last invocation.

### Step 3: Run the checks

The strict scan has to handle quoted content correctly. A banned phrase inside quotes (an example or rule reference) is NOT a violation. The same phrase bare in prose IS a violation.

Quoted-content detection: a match is allowed if the matching position is inside any of:

- A fenced code block (```...```)
- A double-quoted string (`"..."`)
- A backticked inline code span (`` `...` ``)
- A single-quoted string (`'...'`)
- A wikilink (double square brackets)

Run the strict scan in Python or via bash + grep.

### Step 4: Report

Format:

```
**Audit, <filename>** (using handoff-audit CHECKLIST.md)

P0 contradictions: <count>
[bullet per finding, or "0 found" prose]

P1 missing required sections: <count>
[bullet per finding, or "0 found" prose]

P2 voice violations: <count>
[bullet per finding, or "0 found" prose]

P3 missing recommended: <count>
[bullet per finding]

P4 suggestions: <count>
[bullet per finding]

**Summary: P0/P1/P2/P3/P4 = X/X/X/X/X. <Ship | Fix-then-ship | Rebuild>.**
```

End with a Sources block naming the audited file.

---

## Failure modes

1. **CHECKLIST.md missing or unreadable.** Log the path attempted, return: "Cannot run audit. CHECKLIST.md is the audit source of truth and is missing." Recommend reinstalling the plugin before retrying.
2. **Target handoff file not found.** Return: "No handoff at <path>. Tell me which file to audit, or place a session-handoff-*.md in Resources/Prompts/."
3. **Target file has unparseable structure.** Return: "Could not parse the handoff structure. Most likely missing or malformed YAML frontmatter, or no markdown headers. Treat as P1: missing all required sections, recommend rebuild."
4. **Strict scan tool error (Python, regex compile, etc.).** Fall back to a less-strict grep-only scan and prefix the report with: "Reduced-fidelity audit due to scan tool error: <error>." Do not silently swallow.

## Verification (before declaring an audit run successful)

- [ ] Audit output lists all five priority groups, even if the count is 0
- [ ] Each finding cites the line number or section name in the audited file
- [ ] Final summary line states the count for every group
- [ ] Recommendation matches the worst severity found (P0 → rebuild; P1 → fix-then-ship; P2 → fix-then-ship; P3-P4 only → ship)
- [ ] Source citation present
- [ ] The report itself is plain and technical, not styled prose

## Voice rules for the audit report

This skill's OUTPUT is a status report, not prose under the owner's name. The vault's writing-voice rules do not apply to the report body.

- Plain technical language
- Bullets allowed (this is a tool output, not an email)

## Rollback

The skill writes nothing persistent. The report is ephemeral. To roll back: ignore the trigger.
