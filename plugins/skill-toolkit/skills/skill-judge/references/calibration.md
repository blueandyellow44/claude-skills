# Calibration — skill-judge

Do NOT load during a standard evaluation. Load only after scoring is complete and you need to verify a specific disputed score against a worked example, or when revising or calibrating this judge.

---

## D2: Mindset vs Procedures — worked examples

**Expert thinking pattern** (high value):
```markdown
Before designing, ask yourself:
- Purpose: What problem does this solve? Who uses it?
- Constraints: What are the hidden requirements?
- Differentiation: What makes this memorable?
```

**Valuable domain procedure** (high value — Claude wouldn't know this sequence):
```markdown
OOXML redlining workflow:
1. Convert to markdown: pandoc --track-changes=all
2. Map text to XML: grep for text in document.xml
3. Implement changes in batches of 3–10
4. Pack and verify: confirm ALL changes applied
```

**Generic procedure** (low value — Claude already knows):
```markdown
Step 1: Open the file
Step 2: Find the section
Step 3: Make the change
Step 4: Save and test
```

---

## D3: Anti-Pattern Quality — worked examples

**Expert anti-pattern** (specific + reason):
```markdown
NEVER use generic AI-generated aesthetics:
- Overused fonts: Inter, Roboto, Arial
- Cliché color schemes: purple gradients on white
- Default border-radius on everything
```
The WHY is implicit and non-obvious — these patterns signal AI generation to trained eyes.

**Weak anti-pattern** (vague, no value):
```markdown
Avoid making mistakes.
Be careful with edge cases.
Don't write bad code.
```

---

## D4: Description quality — worked examples

**Excellent description** — answers WHAT, WHEN, KEYWORDS:
```yaml
description: "Comprehensive document creation, editing, and analysis with support
for tracked changes, comments, formatting preservation, and text extraction.
When Claude needs to work with professional documents (.docx files) for:
(1) Creating new documents, (2) Modifying or editing content,
(3) Working with tracked changes, (4) Adding comments, or any other document tasks"
```

**Poor description** — vague, no trigger:
```yaml
description: "A helpful skill for various tasks"
```

**Activation flow** (why description is the critical field):
```
User Request → Agent sees ALL skill descriptions → Decides which to activate
              (only descriptions, not bodies!)

If description doesn't match → Skill NEVER gets loaded
If description lacks keywords → Skill is invisible to Agent
```

---

## D5: Loading trigger quality — worked examples

**Good trigger** (embedded in workflow, with Do NOT Load):
```markdown
### Creating New Document
MANDATORY — READ ENTIRE FILE: Before proceeding, read `docx-js.md` completely.
NEVER set range limits when reading this file.
Do NOT load `ooxml.md` or `redlining.md` for this task.
```

**Bad trigger** (listed at end, no context):
```markdown
## References
- docx-js.md — for creating documents
- ooxml.md — for editing
```

---

## D6: Freedom calibration — worked examples

**High freedom** (creative task, multiple valid answers):
```markdown
Commit to a BOLD aesthetic direction. Pick an extreme: brutally minimal,
maximalist chaos, retro-futuristic, organic natural...
```

**Medium freedom** (judgment required but principles exist):
```markdown
Review priority:
1. Security vulnerabilities (must fix)
2. Logic errors (must fix)
3. Performance (should fix)
4. Maintainability (optional)
```

**Low freedom** (fragile operation, one wrong byte corrupts):
```markdown
MANDATORY: Use exact script in scripts/create-doc.py
Parameters: --title "X" --author "Y"
Do NOT modify the script.
```

---

## D8: Practical usability — worked examples

**Good usability** (decision tree + fallback):
```markdown
| Task | Primary | Fallback | When to use fallback |
|---|---|---|---|
| Read text | pdftotext | PyMuPDF | Need layout info |
| Extract tables | camelot-py | tabula-py | camelot fails |

Common issues:
- Scanned PDF: pdftotext returns blank → use OCR first
- Encrypted PDF: permission error → use PyMuPDF with password
```

**Poor usability** (vague):
```markdown
Use appropriate tools for PDF processing.
Handle errors properly.
```

---

## Self-evaluation reference (skill-judge scored against itself)

Run after any revision to confirm the refactor did not regress the core dimensions.

| Dimension | Target | Key evidence to check |
|---|---|---|
| D1 | ≥15/20 | E:A:R ratio; no "what is a Skill" tutorials in SKILL.md |
| D2 | ≥12/15 | Meta-question present; evaluation protocol is thinking-first |
| D3 | ≥13/15 | NEVER list is expert-specific, not generic |
| D4 | ≥14/15 | Description has natural trigger phrases |
| D5 | ≥13/15 | SKILL.md ≤ 320 lines; report template load trigger present |
| D6 | ≥12/15 | Score rubrics give structure; judgment not mechanical |
| D7 | ≥9/10 | Tool pattern, appropriately sized |
| D8 | ≥13/15 | Protocol is actionable; failure patterns cover edge cases |
| **Total** | **≥101/120 (B+)** | |
