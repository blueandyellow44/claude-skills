# Metric defaults

Every metric here is a count against a fixed threshold. None is a judgment. Register, tone, and meaning are the builder's job. These defaults live in the top of `scripts/extract_corpus.py`; keep the two in sync if you change a number.

All word-based metrics run on **spoken text** — the turn with stage cues (`(...)` and `[...]`) removed. Stage cues stay in the corpus body but never reach a word count.

## Thresholds

- **short turn**: `<= 4` spoken words (`SHORT_TURN_MAX_WORDS`). The share of short turns is a rhythm signal — clipped, reactive speakers run high.
- **aria**: `>= 60` spoken words (`ARIA_MIN_WORDS`). The share of arias catches the monologuist. A character who never crosses 60 words has a different engine than one who does it every tenth turn.

These are format-independent. A 4-word line is short whether it came from a screenplay cue, a stage cue, or a tagged line of prose.

## The metrics in the header

- **turns** — count of attributed turns in this corpus.
- **spoken words** — total words after stage-cue removal.
- **mean / median words per turn** — central tendency of turn length. Mean catches the arias; median catches the everyday rhythm. Report both; they diverge for characters who mostly clip but occasionally hold the floor.
- **short turns** — count and percent at or below the short threshold.
- **arias** — count and percent at or above the aria threshold.
- **profanity rate** — hits and percent of spoken words, against the profanity list. Hits are exact lowercased word matches.
- **sources covered** — distinct citation labels the turns came from. Compare against where the character actually appears; a gap means a missed source or a label problem.

## Profanity list

A default set ships in the script (`DEFAULT_PROFANITY`). It is deliberately small and English. Override it wholesale with `--profanity-file <path>`, one word per line, lowercased. Use an override when the source register needs it — a period drama, a children's book, a different language. The list is a counting instrument, not a moral one; size it to the corpus.

## Calibration

If a character already has hand-verified numbers, use it as a smoke test. Pin its short-turn share and aria frequency once, then treat those as the calibration point: a fresh run on the same source that lands far from them points at a label problem or a format misroute, not a real change in voice. A new project has no calibration point until you make one, and the first clean run becomes it.

## What is NOT measured here

No sentiment, no readability index, no register label, no "formality score." Those are interpretation. If a number would require a judgment to compute, it does not belong in this header — it belongs to `voice-profile-builder`.
