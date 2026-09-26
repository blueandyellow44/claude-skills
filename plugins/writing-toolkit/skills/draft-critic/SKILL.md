---
name: draft-critic
description: >-
  Critique a nonfiction draft (newsletter, essay, blog post, LinkedIn post, memo, proposal, client
  report) for the tells that make competent prose read as generated or over-polished: over-explanation,
  dead lines, abstraction where an example belongs, flat rhythm, figures that thud, and paragraphs that
  keep landing on a verdict. Runs a deterministic craft sheet first, then grades six dimensions from it
  plus a close reading, and returns a line-by-line flag list. Flags; never rewrites. Use when someone
  says "critique this draft", "why does this sound like AI", "is this too polished", "tighten this post",
  "what is wrong with this essay", or "review this before I send it". Not for fiction, grammar checks,
  or fact-checking.
---

# Draft critic

Most weak drafts are not wrong. They are competent and airless: every sentence is fine, and the piece
still reads like it was assembled rather than written. The usual causes are countable. The draft
explains what its own example already showed. It reaches for "essentially" where a specific belongs.
Every paragraph ends on a neat little verdict. Every sentence runs the same length. This skill finds
those, quotes them, and names the move that fixes each one. The writer makes the edit.

## When to use

One draft per run: a post, an essay, a newsletter issue, a memo, a proposal, a generated client report.
Not for fiction (dialogue and scene craft need different dimensions), not for grammar or spelling, and
not for checking whether claims are true. Those are separate jobs.

## Process

### Step 1: Scope and the craft sheet

Confirm the draft and who will read it. If a program, template, or mail merge produced the document
and a client will read it, also read `references/document-tells.md` now.

Run the sheet:

```
python3 scripts/check_draft.py --draft <file> [--diction words.txt] [--phrases phrases.txt] [--json out.json]
```

`--diction` and `--phrases` extend the starter lists with the writer's own tics. The sheet reports
rhythm stats, filter and adverb density, abstraction leaks, stock phrases, echoes, prestige-word
frequency, closing suspicion, paragraph-close patterns, verdict landings, and negation reveals. Every
item is a candidate. It exits 0 on any readable draft and 2 only when the file cannot be read.

### Step 2: Read closely

Read the whole draft, letting the sheet point you. The sheet cannot tell an earned repetition from a
tic, or a deliberate hard close from a reflex. The reading decides.

### Step 3: Grade six dimensions

Read `references/critique-method.md` in full. Grade each dimension pass or revise, with the quoted
line behind every revise:

1. Line aliveness
2. Over-explanation
3. Concreteness
4. Rhythm
5. Figurative landing
6. Verdict landings and polish

Two sheet reports are reported even when every dimension passes, because both are frequency problems a
single edit cannot fix: the diction-frequency table and the verdict-landing rate.

### Step 4: Verdict and flags

Read `references/verdict-template.md` and fill it in. Each flag carries the quoted line, the problem,
and the move (cut, concretize, vary, sharpen, ask). The writer approves the flags before anyone edits.

### Step 5: Learn from overrides

When the writer keeps a flagged line or fixes it differently, write that down in `lessons.md` next to
this file: the line, the flag, what they did, and why. Read `lessons.md` at Step 3 on every later run.
Taste calibrates on the writer's real edits, not on this skill's defaults.

## Rules

1. **Sheet before judgment.** Run the script first. Grading from vibes launders a bad page or flags a
   writer's best risk.
2. **Flag, do not rewrite.** Name the line, the problem, and the move. A critic that rewrites has
   stopped being a judge, and the rewrite will sound like the critic.
3. **Quote every locus.** A flag without the exact line is not actionable.
4. **Never invent a specific.** The concretize move is where made-up facts enter nonfiction. A
   concretization must come from the writer's own material. If the draft and the notes you were given
   do not contain the example, the flag says `ask the writer for the real example`. That is a finished
   outcome, not a failure.
5. **Prefer removal.** Most fixes are cuts. Never satisfy a flag by adding a quirky beat to seem human;
   a shape associated with human writing is not evidence of it.
6. **A detector can point; it cannot flag.** If an AI-detector score or highlight comes with the draft,
   use it only as a map. A line gets flagged only when a craft reason survives your own reading. If none
   does, say so and leave the line alone.
7. **Protect the writer's voice.** Plain, blunt, clipped, run-on, or oddly built sentences that sound
   like a person talking are the goal, not a defect. Do not sand them.
8. **Cap your confidence.** Until `lessons.md` holds real overrides from this writer, confidence stays
   low and every flag is a proposal.

## Files

- `scripts/check_draft.py`: the craft sheet (stdlib Python)
- `scripts/test_check_draft.py`: its tests; run after any edit to the script
- `references/critique-method.md`: the six dimensions and how to grade them
- `references/document-tells.md`: extra checks for generated business documents
- `references/verdict-template.md`: the output shape
