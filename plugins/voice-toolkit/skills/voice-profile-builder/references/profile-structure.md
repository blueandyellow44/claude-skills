# Profile structure: anatomy of a voice profile

The canonical layout for a profile this skill produces. The profile is a folder of linked markdown files plus a summary index. Adapt the register files to the subject; keep the core spine constant.

## File layout

```
<subject-slug>/
  README.md            # overview + register decision tree + confidence note + links to every file
  core-voice.md        # foundational traits, always read first
  anti-rules.md        # what NOT to do (see anti-rules-guide.md)
  non-negotiables.md   # the 3 to 7 hard rules that are never broken
  lexicon.md           # signature words/phrases, and words the subject avoids
  registers/           # one file per register that matters for the intended use
    <register>.md
  real-examples.md     # calibration set: real quotes grouped by register
  do-and-dont.md       # side-by-side rewrites: generic line vs in-voice line
```

For a small subject (one register, light use) a single file with these as headings is acceptable. For a rich subject (a character, a show, a brand with many channels) use the full folder. Default to the folder when in doubt.

## What each file contains

### README.md
- One-paragraph summary of the voice.
- A register decision tree: "Writing an email to a stranger, use professional-formal. Writing dialogue for this character in a fight, use the confrontation register." The tree routes a future writer to the right file fast.
- A confidence note: how many samples, which registers are well-covered, where evidence is thin.
- Links to every other file.

### core-voice.md
The traits that hold across every register. Each trait is one line of description plus at least one real quote as evidence. Cover: register and formality, sentence rhythm, default sentence length, how the subject opens and closes, level of directness, warmth, humor, characteristic moves. Order the traits by frequency: lead with the subject's most common, plainest register and state the plain-to-ornate ratio explicitly. A core-voice file that leads with the signature flourish trains the drafter to over-perform and produces parody.

### anti-rules.md
The negative space. What this voice never does, written as rules a drafter can check against. Each anti-rule leads with the rule, then a Why line, then a How-to-apply line. See `anti-rules-guide.md`.

### non-negotiables.md
The 3 to 7 rules that, if broken, instantly break the voice. The shortlist a drafter reads when time-pressed. Pulled from core-voice and anti-rules, stated as imperatives.

### lexicon.md
Two lists. Signature words and phrases the subject reaches for (with a quote each). Words and constructions the subject avoids or never uses. This is where a voice is often won or lost.

### registers/<register>.md
One file per register relevant to the intended use. Each holds the rules specific to that context plus 2 to 4 real quotes in that register. Common registers: email, formal/institutional, casual/social, creative/prose, dialogue, marketing. Only build the ones the subject's use actually needs.

### real-examples.md
The calibration set. The subject's strongest real lines, grouped by register, lightly annotated with what each demonstrates. Quotes only. This is the single most useful file for matching a voice, because description drifts and real text does not.

### do-and-dont.md
Side-by-side pairs: a flat or generic version of a line, next to the same intent rewritten in the subject's voice. Teaches the gap between "correct" and "in voice" faster than any description.

## Sizing

Keep each file tight. The profile is a working reference, not an essay. If a file grows past roughly a screen and a half, it is carrying commentary that should be cut. Quotes and rules earn their place; analysis prose does not.
