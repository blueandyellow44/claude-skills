# Accuracy checklist: pre-handoff checks + the operator's fidelity gate

A profile is not done when it is written. The mechanical checks below (citations, invented traits, stated confidence, usability) are yours to run and clear before handoff; they catch a profile that invented traits or hid its gaps. Whether the profile actually reproduces the voice is not yours to certify: you write the blind draft as evidence and present it to the operator, who grades fidelity (Step 6). The binding accuracy lock happens downstream in voice-profile-iteration's operator-graded per-register gate. Run every mechanical check before presenting.

## Check 1: every trait is cited

Walk every trait, rule, and lexicon entry. Each must have a real quote behind it. Any uncited claim is deleted or demoted to low-confidence with a flag. No exceptions. This is the check that separates a profile from a horoscope.

## Check 2: nothing was invented

Re-read the profile against the corpus with one question: did the source actually show this, or did it come from a stereotype of the subject? A profile of a frontier character should not import "frontier" cliches the text never used. Cut anything that came from priors rather than evidence.

## Check 3: the blind-draft test

Write a short passage (a few sentences, or a paragraph of dialogue) in the subject's voice, using only the profile. **Pick a situation the corpus never covered before you write a word.** This is the first move, not a fallback for when you notice yourself copying: a model told to "be original" will still paraphrase a famous scene without noticing, because it has no reliable signal for its own paraphrasing (tested head to head, an agent asked for original lines reworded a canonical scene and a canonical verbal tic and believed both were new). Removing the famous scene from reach is what makes the draft genuinely new; intent does not. A paraphrase passes the eye test while proving nothing: it tests your memory of the source, not whether the profile generates the voice. Then read it against these questions and surface what you find. You do not get to certify that it sounds like the subject; that fidelity verdict is the operator's grade (Step 6 AskUserQuestion), and the binding lock is downstream in voice-profile-iteration. The mechanical items below (anti-rule breaks, uncited traits) you fix yourself:

- Does it sound like the subject, or like a parody of the subject? Parody means the profile over-indexed on a few loud tics and missed the rhythm.
- Does it hit the sentence rhythm and length from the rubric?
- Does it break any anti-rule? If the drafter (you) broke one without noticing, the anti-rule needs to be louder or the profile is internally inconsistent.
- Put it next to a real quote from real-examples.md. Does it sit comfortably beside the real line, or does the seam show?

If the draft breaks an anti-rule or surfaces an uncited trait, fix that and revise once, then go back to Step 3 if the fix runs deep. But you do not decide on your own read whether the profile "is wrong" on fidelity: present the blind draft to the operator (Step 6) and let their grade decide. Do not self-certify the profile as accurate and do not self-clear it for ship; accuracy is operator-graded here and locked downstream in voice-profile-iteration.

Escape hatch: if the blind draft fails twice on the same dimension, stop looping. A third pass on the same gap is almost never the corpus revealing more; it is you grinding. Name the dimension that resists and the likely cause (the corpus is too thin in that register, or one tic is over-weighted and drowning the rhythm), then ask for more samples or cut the scope to the registers the evidence actually supports. A loop with no exit is how a profile session burns an hour and ships nothing.

## Check 4: confidence is stated honestly

The README must name the evidence base and the thin spots. A register with no samples is marked as uncovered, not quietly faked. A trait resting on one example is marked low-confidence. A profile that hides its gaps is more dangerous than one that admits them, because it gets trusted where it should not be.

## Check 5: the profile is usable, not just correct

A drafter under time pressure should be able to read the README and non-negotiables in under a minute and produce something in-voice. If the profile is accurate but sprawling, tighten it. The calibration set and the non-negotiables carry most of the practical weight; make sure they are strong.

## Sign-off

Checks 1, 2, 4, and 5 are mechanical and yours to clear. Check 3's fidelity verdict (does it sound like the subject?) is the operator's, not yours. Do not deliver until the operator has graded the blind draft. After the operator's grade: deliver, state the confidence level out loud, and offer to save the profile as an approved example. The binding accuracy lock is downstream in voice-profile-iteration.
