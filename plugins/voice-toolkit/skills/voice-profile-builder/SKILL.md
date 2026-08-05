---
name: voice-profile-builder
description: Build a robust, evidence-based voice profile for any person, character, or brand from their writing samples, transcripts, interviews, or public posts. Use this whenever someone wants to capture, document, codify, reverse-engineer, or clone a writing voice or tone of voice, set up a style guide for a person or brand, onboard an AI to write as someone, or asks to "create a voice profile", "capture my voice", "profile this writer", "build a tone-of-voice guide", "reverse-engineer this style", or "make the model write like X". Produces a multi-file profile with core voice traits, anti-rules, register variants, a lexicon, and a real-example calibration set, every claim grounded in actual quotes.
---

# Voice profile builder

Build a voice profile that lets a writer, or an AI, reliably reproduce a subject's voice. The profile is the deliverable. It is a folder of linked markdown files, modeled on the gold-standard structure in `references/profile-structure.md`, with one rule above all others: every trait is grounded in a real quote from the source material. A profile that invents traits is worse than no profile, because it produces confident wrong output.

This skill builds a profile of the SUBJECT. It does not impose the operator's personal voice rules on the subject. If the subject writes with em-dashes and contractions, the profile says so. Accuracy means fidelity to the evidence, not to anyone's house style.

## When to use

Trigger on any request to capture, document, codify, or reproduce a voice: a person, a fictional character, a brand, a show, a publication. Source can be writing samples, transcripts, emails, posts, or an interview when samples are thin. Do not use this for one-off "rewrite this in X's style" requests where no reusable artifact is wanted. This skill produces a durable profile, not a single rewrite.

## Reference loading

Reading a reference means reading the whole file, not skimming headings. Skipping a required read is the top failure mode for this skill. Each reference loads at a specific step, not all up front, so the context stays lean.

Load at the named step:

- `references/extraction-rubric.md` — the dimensions and the evidence rule. MANDATORY at Step 3.
- `references/profile-structure.md` — the anatomy and file layout. MANDATORY at Step 4.
- `references/anti-rules-guide.md` — how to write anti-rules that constrain output. MANDATORY at Step 4, before writing the anti-rules file.
- `references/accuracy-checklist.md` — the validation gate. MANDATORY at Step 6.
- `examples/` — any approved prior profile, read as a model of good. Read at Step 4 if the folder is non-empty.

Load conditionally:

- `references/interview-questions.md` — read ONLY when Step 2 flags thin evidence and the interview path fires. Do NOT load it on the common path where real samples exist; it wastes context.

## Tools

Read, Write, Edit, Glob, Grep for source material and profile files. AskUserQuestion for every human-in-the-loop step. Optional WebSearch and web_fetch when the subject is a public figure and more samples are needed. No external API is required.

## Process

Two kinds of step live below, and they want different things from you. The mechanical steps have one correct behavior and no room to improvise: read the named reference in full, cite a real quote for every trait, run the blind-draft gate before shipping. Do not deviate on those; a shortcut there corrupts the profile silently. The judgment steps are where taste belongs: which traits matter, which registers the use actually needs, how to phrase an anti-rule so a drafter can act on it. On those, generate options and let the operator choose. Knowing which step you are on is half the skill.

### Step 1: scope the subject

Confirm who or what is being profiled and what the profile is for. A show transcript with many speakers forces a choice: the overall authorial voice, or one character. The intended use (write new prose, draft emails, generate marketing copy) determines which registers matter.

- Human in the loop: AskUserQuestion. Offer the plausible subjects and uses as options, never a single guess.
- Output: a one-line scope statement (subject, target registers, intended use).

### Step 2: gather and clean source material

Collect every sample. Strip non-voice cruft: scraped web navigation, timestamps, speaker labels you are not profiling, boilerplate. Note word count and how many distinct samples or registers are represented. Thin evidence is a confidence problem, flag it now.

- Human in the loop: none, unless samples are too thin to proceed, then fire the interview path from `references/interview-questions.md`.
- Output: a cleaned corpus and a coverage note (word count, register spread, confidence level).

### Step 3: extract evidence-cited traits

MANDATORY: read `references/extraction-rubric.md` in full before extracting. Work through every dimension it lists: diction, sentence rhythm and length, syntax habits, punctuation tics, openings and closings, structure, what the subject avoids, emotional register, figurative language. For each observed trait, pull at least one verbatim quote as evidence. No quote, no trait.

Two dimensions are systematically under-served by a spoken-text-only read and must be handled deliberately. (1) **State and overlay registers** (intoxication, grief, panic, exhaustion): the behavior that defines them lives in stage directions and performance, not in the words, so a builder reading only the dialogue will infer the generic idea of the state and frequently get it backwards. Do not infer a state register from the spoken text alone; open the scene(s) where the state occurs, read what the subject actually does, model the register from that, and mark it low-confidence so the iteration pass verifies it. (2) **Relational registers**: who the subject speaks to shapes the voice as much as what they are doing. Enumerate the principal relationships, not only the abstract modes, because the same trait can be right with one interlocutor and off-voice with another.

- Human in the loop: none.
- Output: a trait inventory, each entry paired with one or more real quotes.

### Step 4: draft the profile elements

MANDATORY: read `references/profile-structure.md` and `references/anti-rules-guide.md` in full before drafting, plus any prior profile in `examples/`. Turn the trait inventory into the profile files per that structure. At minimum: an overview with a register decision tree, core voice, anti-rules, register variants, a lexicon of signature words and avoided words, non-negotiables, and do/don't side-by-side rewrites. Every claim cites its evidence.

- Human in the loop: AskUserQuestion to confirm the register set and any judgment calls. Offer variations, not a single draft.
- Output: draft profile files in the subject's folder.

### Step 5: build the calibration set

Assemble `real-examples.md`: the subject's strongest actual lines, grouped by register, chosen so a writer can calibrate against real text rather than description. Quotes only, lightly annotated with what each one demonstrates.

- Human in the loop: none.
- Output: a calibration file of real quotes per register.

### Step 6: validate with a blind draft

MANDATORY: read `references/accuracy-checklist.md` in full, then run every check in it. Write a short passage in the subject's voice on a situation the corpus never covered, never a paraphrase of a real line, then check it against the anti-rules and the calibration set. Use the draft to surface uncited traits and anti-rule breaks and fix those. You do not certify fidelity yourself: present the blind draft to the operator (next line) and let their grade decide whether it sounds like the subject. If the operator marks it off, go back to Step 3 with their note. If the draft fails twice on the same dimension, stop looping and use the escape hatch in the checklist: name the resisting dimension and its cause, then ask for samples or cut scope.

- Human in the loop: AskUserQuestion. Show the blind draft and ask whether it sounds like the subject. The operator's grade decides pass/fail; the binding accuracy lock is downstream in voice-profile-iteration.
- Output: the blind draft plus the specific gaps named, presented for the operator's grade.

### Step 7: assemble and deliver

Write the final folder, plus a single-file summary index that links every element. Report the confidence level and any thin spots honestly.

- Human in the loop: AskUserQuestion. Offer to save the profile as an approved example.
- Output: the finished profile folder and summary.

## Rules

These predict the failure modes for this skill. Update this section when the skill gets a correction.

1. **Read the reference files.** Steps that name a reference must read it. Do not work from memory of the structure.
2. **Every trait cites a real quote.** No quote, no trait. Invented traits are the cardinal sin. If evidence is thin, say "low confidence" and ask for more samples, do not fabricate.
3. **Profile the subject, not the operator.** Never impose your own house style, a no-em-dash or no-contraction rule or any other personal preference, on a subject's profile. The profile reflects the evidence.
4. **Return variations, not single answers.** At every human-in-the-loop step, give the operator options to react to. Single drafts are an anti-pattern.
5. **Separate description from quotation.** A trait line states the habit; the evidence line quotes the proof. Do not blur them.
6. **Clean before you analyze.** Strip scraped nav, timestamps, and non-subject speakers first, or the profile learns the cruft.
7. **State confidence.** Every profile names its evidence base and where it is thin. A profile that hides its gaps gets trusted where it should not be.
8. **The blind-draft test is mandatory.** A profile that has not been tested by writing in the voice is not ready to present. The blind draft is evidence for the operator's grade; writing in the voice does not by itself validate the profile, the operator's grade does, and the binding lock is downstream in voice-profile-iteration.
9. **Profile frequency, not just flavor.** Lead core-voice with the subject's most frequent, plainest register and state the plain-to-ornate ratio. The loud, quotable register is the most memorable and the least frequent; a profile that leads with it produces parody.

## Progressive updates and self-learning

1. When the operator defines a clear thing this skill should not do, update this rules section in place.
2. At the end of every run, ask via AskUserQuestion whether to save the profile as a good example. On yes, write input summary plus the profile path plus timestamp plus optional notes to `examples/YYYY-MM-DD-HHMM.md`. Future runs read `examples/` as a model.

## Anti-patterns

Do not:

- Invent a trait the samples do not show. Why: a fabricated trait produces confident wrong output every time the profile is used, which is worse than a gap the drafter knows to fill.
- Describe a voice in adjectives with no quotes behind them. Why: adjectives like "warm" or "punchy" drift between readers; a real quote does not.
- Profile a multi-speaker transcript without first choosing whose voice. Why: blending speakers yields a voice that belongs to no one and matches nothing.
- Impose the operator's personal style rules on the subject. Why: the profile exists to capture the subject, and a subject who uses contractions and em-dashes must be recorded that way or the profile lies.
- Ship a profile without running the blind-draft test. Why: a profile reads plausibly and still fails to reproduce the voice; only writing in it exposes the gap.
- Pass the blind-draft test with a paraphrase of a real line. Why: a near-copy of a quote the subject actually said sails through the eye test while proving nothing about whether the profile generates the voice. It tests your memory, not the profile. The draft has to be new prose on a fresh prompt or the gate is theater.
- Bloat the profile files with the operator's commentary. Why: a working reference is read under time pressure, and essays bury the quotes and rules that do the work.

## Related

- `references/profile-structure.md`
- `references/extraction-rubric.md`
- `references/anti-rules-guide.md`
- `references/interview-questions.md`
- `references/accuracy-checklist.md`
- Any mature voice profile you already trust, read as a structural reference before building a new one.
