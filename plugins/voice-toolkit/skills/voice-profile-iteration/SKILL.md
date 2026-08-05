---
name: voice-profile-iteration
description: Calibrate and harden an EXISTING voice profile by writing one original example per register, having the user grade each, and iterating to a locked set. Use it to pressure-test a profile, prove it generates the voice rather than only describing it, calibrate or lock its registers, or build a graded exemplar set. Triggers include "calibrate the registers", "grade these voice examples", "write examples of all the registers", "lock the voice examples", "harden the voice profile", and "is this profile any good". The refinement counterpart to voice-profile-builder, which BUILDS a profile from source; if no profile exists yet, build one first, then use this.
---

# Voice profile iteration

Take a voice profile that already exists and harden it by writing in the voice and letting the user grade the result, one register at a time, until every register is locked.

This is a different test from the one that built the profile. The builder calibrates against the *source*: does each trait cite a real quote. This skill calibrates against the *target*: can a writer holding only this profile actually generate the voice. A profile can be accurate and still fail to generate, because description drifts and the loud traits crowd out the plain ones. The graded loop catches that gap, and the locked example set it produces becomes the most useful single artifact in the profile for matching the voice later.

## Preconditions

An existing profile: a `voice-profile-builder` folder, or any reference with a core voice and named registers. If none exists, stop and build one first; this skill refines, it does not create from nothing.

## The loop

### 1. Enumerate the registers

From the profile's core-voice and its `registers/` files. If the profile states a register-frequency ratio, lead from the plainest, most-frequent register rather than the flashiest: that is where the voice actually lives most of the time, and where drafts most often drift.

Registers are not only modes (what the subject is doing — confiding, commanding, joking); they are also relationships (who the subject is speaking to). For a character with a few load-bearing relationships, the voice changes as much across interlocutors as across modes: the same warmth that is right with one person is off-voice with another, and the same cold precision that lands on an antagonist is wrong with an intimate. Enumerate the principal relationships as registers in their own right and write an example for each, not only one example per abstract mode. Skipping this produces a profile that nails the modes and still generates wrong lines the moment a scene names a specific person.

### 2. Write one original example per register

One line or short passage per register. The rules here are what make the loop work:

- **Choose an un-scened occasion, a situation the source never dramatized. This is the highest-leverage rule in the skill, and it is a structural safeguard, not a stylistic preference.** Two reasons, the second more important than the first. (1) An example built on a famous staged scene gets graded against the reader's memory of the original and loses every time; an un-scened line has nothing to measure against, so it is judged on the voice alone. (2) A model told to "be original" will still paraphrase a famous scene without noticing, because it has no reliable internal signal for "this is a paraphrase of something real." Tested head to head, a capable agent asked for original Bullock lines reworded the canonical trout-offer scene and the canonical "What else?" anger tic and believed both were new. Intent to stay original does not work. Removing the famous scene from reach is what works: write about bent nails and a widow's account, and there is no canonical line to drift toward. **Change the occasion; do not rely on discipline.**
- **Original prose, never a reproduced or lightly-edited source quote.** This follows automatically once the occasion is un-scened, which is why the occasion rule comes first. A paraphrase clears the "not verbatim" bar and still proves nothing about the profile, only about your memory of the source.
- **Verify any source claim the example leans on before presenting it.** A sample built on a wrong premise teaches the wrong thing and spends the user's correction budget on a fact instead of the voice. Check it with the same rigor you would give committed work.
- **One per register** keeps grading fast and lets the user place each line precisely against the register it is supposed to hit.

### 3. Present for grading

Show the whole set, labeled by register and numbered, with the occasion noted under each. If the profile has many registers (eight or more), grade in batches rather than dumping all at once, or the feedback goes shallow. Ask the user to grade each one (a simple scale like perfect / close / not quite works well) with terse feedback: perfect locks the register, close and not quite both go to Step 4 (the difference is how much you rework). Do not defend a line that gets marked down; capture the note and move on.

### 4. Iterate per register

Rework only the misses. Keep what passed; re-presenting locked lines wastes the user's attention. These are the recurring failure modes; name which one is in play before you redraft, because the fix depends on the failure:

- **Failed and the example sat on a famous staged scene** → move it to an un-scened occasion. This is the most common fix and usually the whole problem.
- **"Parody" or "too much"** → the line is over-performing. Flatten it toward the register's plain baseline; the signature flourish is rationed, not constant.
- **A canon or premise error** → fix the fact, not the phrasing. Re-verify against the source.
- **"Close"** → usually one beat is off (the wrong wound, a soft closer where it should be physical, a curse doing no work). Change the one thing, not the whole line.
- **A state or overlay register (intoxication, grief, panic, fatigue) graded wrong** → almost always a corpus-inference error in the profile, not a wording problem. The builder read the subject's *spoken words* and inferred the generic idea of the state, but the real behavior of a state register lives in stage directions and performance, not in vocabulary, and the inference is often the exact opposite of the truth. Open the actual scene where the state occurs, model the syntax from what the subject does there, and fix the profile's register file, not just the line. (Worked case: an "on laudanum" register drafted slurred and halting; the real scene showed baroque, over-flowering periodic sentences with the impairment carried in a displaced physical task and a lost thread. The fix was to rewrite the register file from the scene.)
- **"Would say this to anyone but X" / right line, wrong person** → the line is keyed to the wrong relationship, not mis-worded. The mode can be perfect and the relationship still wrong. Re-aim it at the relationship the register names, or split that relationship into its own register per Step 1.
- **Every line reads plausible but none sounds like the subject** → the profile is describing the voice without generating it; the loud traits are crowding out the plain baseline. This is the failure the whole skill exists to catch, and it is a profile problem, not a line problem. Fix the profile (reorder core-voice to lead from the floor, add an anti-rule), not the example.

Re-present the reworked lines. Repeat until every register is locked. But if one register fails twice, stop redrafting the line: the fault is almost certainly in the profile, not your wording. Fold the fix into the profile per Step 5 and move on, rather than grinding a third draft.

Two loop-level stops sit above the per-register one. After a full pass, if the only remaining misses are profile faults rather than wording, lock what passed and switch to editing the profile instead of running another grading round. And if the user's grades on the same line contradict across rounds, the disagreement is about the target, not the draft: ask one clarifying question about what the register should sound like before redrafting again.

### 5. Persist on lock

- Save the locked set to the profile folder as `<subject>-register-examples.md`: one example per register, each labeled with its register and its occasion, plus a short provenance note (graded by whom, on what date) and the un-scened-occasion principle so the next reader understands why the occasions were chosen.
- Fold any method lesson the iteration surfaced back into the profile itself, not just the example file. If the grading revealed that the profile led with the wrong register, reorder core-voice. If it revealed a recurring wrong move, add an anti-rule. The example set records the result; the profile should absorb the cause.
- Link the example set from the profile's README, and log the lesson wherever the project keeps lessons.

## Principles

- **Change the occasion; do not trust discipline.** The skill's load-bearing rule; full rationale in Step 2.
- **Verify before presenting.** A demonstration built on a wrong fact is worse than no demonstration.
- **Lead from the plain baseline.** The frequent, quiet register is where the voice lives and where drafts drift.
- **One example per register.** Fast to grade, precise to place.
- **Do not defend; generalize.** A correction on one line is usually a rule for the whole register. Pull the rule, not just the patch.

## Example (one register)

**Register:** transactional floor. **Occasion (un-scened):** a body to dispose of at the saloon, a routine the show never staged as a set-piece.

> "He's dead."
> "Back room."
> "Anybody see it?"
> "Two of the girls."
> "They talk?"
> "Not yet."
> "Then it's not yet a problem. Get him to Wu's pigs before he stiffens. And put both girls on the floor tonight where I can watch their mouths."

Why it locked: plain short lines (the register's floor), interrogation-as-control rather than a direct answer, one fused profanity doing work, and a concrete instruction to close instead of commentary. Nothing here competes with a remembered scene, so it was graded on the voice alone.

## Related

- `voice-profile-builder` — builds the profile this skill refines. Use it first if no profile exists.
