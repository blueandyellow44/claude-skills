# Source formats

The extractor reads four shapes of source file. Format is auto-detected per file from the first ~400 non-blank lines, and can be forced per run with `--format {screenplay,stageplay,prose}`. Detection is conservative: when signals are weak it falls back to prose, because a wrong script guess on prose invents turns, and inventing turns is the cardinal sin.

A turn is always one speaker's continuous span of speech, attributed by label (scripts) or by an adjacent dialogue tag (prose). Stage cues — text in `(parentheses)` or `[brackets]` — are kept inline in the corpus and excluded from every word-based metric.

## screenplay (movie scripts and TV transcripts)

Two opener styles, both handled by the same parser:

- **Caps cue on its own line.** A short ALL-CAPS line is a character cue; the dialogue is the block beneath it, running until the next cue or a scene/slug line. A parenthetical extension is allowed and ignored for attribution: `AL (CONT'D)`, `AL (V.O.)`.
- **`NAME:` inline opener.** Transcript and interview style, where the name and the first words of dialogue share a line: `AL: Cocksucker.` The block continues on following lines until the next opener.

Scene and structural lines are never cues and never open a turn: `INT.`, `EXT.`, `FADE IN`, `CUT TO`, `ACT`, `SCENE`, `CHAPTER`, `ENTER`, `EXEUNT`, and the like (see `SLUGLINE_RE` in the script). If a real character is named one of these reserved words (a literal `CHORUS` speaker), force the format and correct the roster with the operator; do not edit the regex mid-run.

## stageplay (theatre scripts)

The distinctive signature is the **period-delimited inline cue**: `HAMLET. To be, or not to be...`. The name, a period (the colon form is also accepted), then the dialogue on the same line and any following lines until the next cue. Whole-line stage directions in `(...)` or `[...]` are kept inline and not counted. Act and scene headers are excluded exactly as in screenplay.

Period cues are the reason stageplay is detected before screenplay: the screenplay parser cannot read a `NAME.` opener, so a misrouted stage play loses every turn. If the format tally shows a stage play as `screenplay`, force `--format stageplay`.

## prose (novels and short fiction)

Two corpora come out of prose, and they never mix.

**Dialogue.** Every quoted span (`"..."` or `“...”`) is tested for an adjacent dialogue tag, and attributed only if one is found:

- after the quote: `"..." said Al`, `"..." Al said`
- before the quote: `Al said, "..."`, `said Al, "..."`

The attribution name must be one to three capitalized tokens. A quote with no adjacent tag is **dropped**, not guessed. A pronoun tag (`he said`, `she growled`) is **not** resolved to a name — anaphora is interpretation, so the line is dropped. This is deliberate: prose corpora are smaller and cleaner than a naive grab, and they never teach the builder a line the character did not say.

**Narration** (only with `--include-narration`, prose only). Emitted as a separate file. The default mode is `first-person`: narration is pulled only when the file reads as a first-person narrator (a narrator who uses "I" as a sentence subject often enough). That narrator is bound to the requested speaker, on the theory that a first-person narrator IS the point-of-view character. **This binding is an assumption the operator must confirm** — if you extract Al's corpus from a novel narrated by Bullock, the narration would wrongly attach to Al. The narration file carries a warning header to this effect. Third-person narration is never attributed, because there is no speaker to attribute it to.

## The roster rule

Detection finds candidate speakers; the operator confirms them. `--detect-roster` prints the format tally and every dialogue label with a turn count and a file count. Confirm the target's labels (one character, several labels) and resolve any ambiguous label with the operator before extracting. Never resolve ambiguity in code.

## When no model fits

If a file is OCR sludge, a PDF dump with broken line breaks, or a format none of the three models reads, the right move is to stop and say so, not to coax a regex into half-working. A half-parsed corpus is worse than no corpus, because its errors are invisible downstream.
