---
name: skill-judge
description: Score and critique Agent Skill design quality against official specifications. Use when asked to evaluate, review, audit, grade, score, or improve a SKILL.md or skill package — including phrasing like "is this skill good?", "how well-designed is this?", "score this skill", "critique this skill", or "audit this skill." Produces D1–D8 scores (120-point total), grade, Expert:Activation:Redundant knowledge-ratio, anti-pattern diagnosis, and ranked improvements.
---

# Skill Judge

Score and critique Agent Skills against official specifications derived from 17+ official examples.

## The core formula

> **Good Skill = Expert-only Knowledge − What Claude Already Knows**

A Skill's value is its **knowledge delta** — what it provides that the model does not already have. When a Skill explains basics Claude knows, it wastes context that costs every invocation.

**Three content types** — categorize every section:

| Type | Definition | Treatment |
|---|---|---|
| **Expert [E]** | Claude genuinely doesn't know this | Keep — this is the value |
| **Activation [A]** | Claude knows but may not think of | Keep if brief |
| **Redundant [R]** | Claude definitely knows this | Delete ruthlessly |

Good Skill: E > 70%, A < 20%, R < 10%. Bad Skill: R dominant.

---

## Evaluation dimensions (120 points)

### D1: Knowledge Delta — 20 pts (THE CORE DIMENSION)

| Score | Criteria |
|---|---|
| 0–5 | Explains basics Claude knows (what is X, standard tutorials, library docs) |
| 6–10 | Mixed: some expert knowledge diluted by obvious content |
| 11–15 | Mostly expert knowledge, minimal redundancy |
| 16–20 | Pure knowledge delta — every paragraph earns its tokens |

**Red flags** (instant ≤5): "What is [concept]" sections · tutorials for standard ops · generic best practices ("write clean code") · definitions of industry-standard terms.

**Green flags**: decision trees for non-obvious choices · trade-offs only experts know · edge cases from real experience · "NEVER X because [non-obvious reason]" · domain-specific thinking frameworks.

Ask of every section: "Does Claude already know this?" If yes, it's R.

---

### D2: Mindset + Appropriate Procedures — 15 pts

| Score | Criteria |
|---|---|
| 0–3 | Only generic procedures Claude already knows |
| 4–7 | Domain procedures present but no thinking frameworks |
| 8–11 | Good balance: thinking patterns + domain workflows |
| 12–15 | Expert-level: shapes thinking AND provides unknown procedures |

**Valuable** (keep): "Before doing X, ask yourself…" frameworks · domain workflows Claude hasn't been trained on · non-obvious ordering ("validate BEFORE packing").

**Redundant** (cut): generic file ops · standard programming patterns · well-documented library usage.

See `references/calibration.md` for worked examples.

---

### D3: Anti-Pattern Quality — 15 pts

| Score | Criteria |
|---|---|
| 0–3 | No anti-patterns mentioned |
| 4–7 | Vague warnings ("be careful", "avoid errors") |
| 8–11 | Specific NEVER list with some reasoning |
| 12–15 | Expert-grade NEVER list — things only experience teaches, each with WHY |

Test: would an expert say "yes, I learned this the hard way"? Or "this is obvious to everyone"?

See `references/calibration.md` for expert vs. weak anti-pattern examples.

---

### D4: Specification Compliance — 15 pts (description is the critical field)

| Score | Criteria |
|---|---|
| 0–5 | Missing or invalid frontmatter |
| 6–10 | Has frontmatter but description is vague or missing trigger scenarios |
| 11–13 | Valid frontmatter, description has WHAT but weak on WHEN/KEYWORDS |
| 14–15 | Description answers WHAT, WHEN, and includes natural trigger phrases |

**Frontmatter requirements**: `name` lowercase alphanumeric+hyphens ≤64 chars. `description` is the only field the Agent sees before deciding whether to load the Skill — poor description = skill never activated.

**Description must answer**: (1) WHAT does it do · (2) WHEN to use it · (3) trigger KEYWORDS including natural user phrasing.

See `references/calibration.md` for excellent vs. poor description examples.

---

### D5: Progressive Disclosure — 15 pts

Three loading layers: (1) description always in memory · (2) SKILL.md body loaded on trigger · (3) `references/` loaded on demand.

| Score | Criteria |
|---|---|
| 0–5 | Everything in SKILL.md (>500 lines, no structure) |
| 6–10 | Has references but no clear loading triggers |
| 11–13 | Good layering with MANDATORY triggers embedded in workflow |
| 14–15 | Decision trees + MANDATORY triggers + "Do NOT Load" guidance |

Loading trigger quality: **Poor** = references listed at end · **Good** = MANDATORY in workflow · **Excellent** = conditional triggers + Do NOT Load.

For Skills with no references (<100 lines): score on conciseness and self-containment.

See `references/calibration.md` for good vs. bad loading trigger examples.

---

### D6: Freedom Calibration — 15 pts

| Score | Criteria |
|---|---|
| 0–5 | Severely mismatched (rigid scripts for creative tasks, vague for fragile ops) |
| 6–10 | Partially appropriate, some mismatches |
| 11–13 | Good calibration for most scenarios |
| 14–15 | Perfect freedom calibration throughout |

| Task type | Freedom | Why |
|---|---|---|
| Creative/Design | High (principles) | Multiple valid approaches |
| Code review | Medium (priorities) | Judgment required |
| File format ops | Low (exact scripts) | One wrong byte corrupts |

Test: "if Agent makes a mistake, what's the consequence?" — high consequence → low freedom.

See `references/calibration.md` for high/medium/low freedom examples.

---

### D7: Pattern Recognition — 10 pts

| Pattern | ~Lines | Best for | Example |
|---|---|---|---|
| **Mindset** | ~50 | Creative tasks requiring taste | frontend-design |
| **Navigation** | ~30 | Multiple distinct scenarios | internal-comms |
| **Philosophy** | ~150 | Art/creation requiring originality | canvas-design |
| **Process** | ~200 | Complex multi-step projects | mcp-builder |
| **Tool** | ~300 | Precise ops on specific formats | docx, pdf, xlsx |

| Score | Criteria |
|---|---|
| 0–3 | No recognizable pattern |
| 4–6 | Partially follows a pattern |
| 7–8 | Clear pattern, minor deviations |
| 9–10 | Appropriate pattern, masterfully applied |

---

### D8: Practical Usability — 15 pts

| Score | Criteria |
|---|---|
| 0–5 | Confusing, incomplete, contradictory |
| 6–10 | Usable but with noticeable gaps |
| 11–13 | Clear guidance for common cases |
| 14–15 | Comprehensive coverage including edge cases and fallbacks |

Check for: decision trees for multi-path scenarios · error handling and fallbacks · edge cases covered · Agent can act immediately without figuring things out.

See `references/calibration.md` for good vs. poor usability examples.

---

## NEVER do when evaluating

- **NEVER** let good Markdown formatting inflate D1 — tables, headers, and bold text are presentation, not expert knowledge.
- **NEVER** score D5 charitably because the content is good — an overlong SKILL.md fails progressive disclosure regardless of quality.
- **NEVER** reward README files or other auxiliary documentation — auxiliary files are Pattern 8 regardless of content.
- **NEVER** treat a repeated checklist or summary as knowledge delta — restating dimension descriptions in a different format is R content.
- **NEVER** give high Freedom Calibration to a judgment skill that turns expert evaluation into mechanical box-checking.
- **NEVER** ignore activation language — a skill that does not fire for natural phrasing like "is this skill good?" is under-specified regardless of how good the body is.
- **NEVER** clear a D1 red flag because the section is well-organized — a tidy table of basics is still redundant content.
- **NEVER** forgive explaining basics with "but it provides helpful context."

---

## Evaluation protocol

Before scoring: identify the Skill's claimed domain, what expertise it is supposed to compress, and what a real practitioner in that domain would know that a general model would not. Use that as the lens for all E:A:R judgments — a section that would be obvious to a generalist but non-obvious to a domain expert is E, not R.

### Step 1 — Knowledge delta scan
Read SKILL.md. Mark each section [E], [A], or [R]. Calculate ratio. Good Skill: E > 70%.

### Step 2 — Structure check
Frontmatter valid? SKILL.md line count? References directory? Loading triggers embedded in workflow? Which pattern? README.md or other auxiliary files present?

### Step 3 — Score D1–D8
For each dimension: find specific evidence, assign score, note fix if below 80% of max.

### Step 4 — Calculate and grade
Total = D1+D2+D3+D4+D5+D6+D7+D8 (max 120). Apply grade scale (A ≥ 108 / B ≥ 96 / C ≥ 84 / D ≥ 72 / F < 72).

### Step 5 — Produce report
**MANDATORY**: load `references/report-template.md` before writing the evaluation report. Fill all sections with specific evidence, not generic notes.

**Do NOT load** `references/quick-check.md` unless the user explicitly asks for a checklist or fast preflight.
**Do NOT load** `references/calibration.md` during a standard evaluation. Load it only after scoring is complete and you need to verify a specific disputed score against a worked example, or when revising or calibrating this judge.

---

## Common failure patterns (index)

| # | Name | Symptom | Root cause |
|---|---|---|---|
| 1 | The Tutorial | Explains basics Claude knows | Author assumes Skill should teach the model |
| 2 | The Dump | SKILL.md 800+ lines | No progressive disclosure design |
| 3 | The Orphan References | Reference files never loaded | No loading triggers |
| 4 | The Checkbox Procedure | Step 1, Step 2, Step 3 | Author thinks in procedures, not frameworks |
| 5 | The Vague Warning | "Be careful", "avoid errors" | Knows things go wrong but not why |
| 6 | The Invisible Skill | Great content, never activates | Description vague or missing trigger phrases |
| 7 | The Wrong Location | "When to use" in body not description | Misunderstands three-layer loading |
| 8 | The Over-Engineered | README.md, CHANGELOG.md, etc. | Treating a Skill like a software project |
| 9 | The Freedom Mismatch | Rigid scripts for creative tasks | Not considering task fragility |

Fix for each: delete the R content (1); offload to references/ (2, 3); reframe as thinking questions (4); add specific NEVER+WHY (5); rewrite description with WHAT/WHEN/KEYWORDS (6); move trigger info to description (7); delete auxiliary files (8); recalibrate to task fragility (9).

---

## The meta-question

> **"Would an expert in this domain say: 'Yes, this captures knowledge that took me years to learn'?"**

Yes → genuine value. No → compressing what Claude already knows. The best Skills are compressed expert brains. What gets compressed must be things Claude does not have.
