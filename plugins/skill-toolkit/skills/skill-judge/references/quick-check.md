# Quick preflight checklist

Use only when explicitly asked for a checklist or fast preflight. For full evaluations, use the protocol in SKILL.md instead — the checklist compresses judgment into boxes and misses nuance.

```
SKILL EVALUATION PREFLIGHT

KNOWLEDGE DELTA (D1 — most important):
  [ ] No "What is X" explanations for basic concepts
  [ ] No tutorials for standard operations
  [ ] Has decision trees for non-obvious choices
  [ ] Has trade-offs only experts would know
  [ ] Has edge cases from real-world experience

MINDSET + PROCEDURES (D2):
  [ ] Has "Before doing X, ask yourself..." thinking frameworks
  [ ] Includes domain-specific procedures Claude wouldn't know
  [ ] Distinguishes valuable procedures from generic ones

ANTI-PATTERNS (D3):
  [ ] Has explicit NEVER list
  [ ] Each anti-pattern is specific, not vague
  [ ] Includes WHY (non-obvious reason)

SPECIFICATION (D4 — description is critical):
  [ ] Valid YAML frontmatter; name ≤ 64 chars, lowercase
  [ ] Description answers: WHAT, WHEN, KEYWORDS
  [ ] Contains natural trigger phrases ("evaluate this skill", "is this skill good?")

STRUCTURE (D5):
  [ ] SKILL.md < 500 lines (ideal < 300)
  [ ] Heavy content in references/, not dumped in SKILL.md
  [ ] Loading triggers embedded in workflow (not just listed)
  [ ] Has "Do NOT Load" guidance where relevant

FREEDOM (D6):
  [ ] Creative tasks → high freedom (principles, not scripts)
  [ ] Fragile operations → low freedom (exact scripts)

PATTERN (D7):
  [ ] Follows one of: Mindset/Navigation/Philosophy/Process/Tool
  [ ] Size matches pattern target

USABILITY (D8):
  [ ] Decision trees for multi-path scenarios
  [ ] Error handling and fallbacks present
  [ ] Agent can act immediately without figuring things out
```
