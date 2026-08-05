---
name: voice-corpus-extractor
description: Extract one speaker's complete, source-cited dialogue corpus from a folder of speaker-attributed sources — movie scripts, TV transcripts, stage plays, or prose novels — with countable voice metrics (turn-length distribution, short-turn share, aria frequency, profanity rate), as the deterministic front end to voice-profile-builder. For prose it can emit a separate narration corpus alongside the dialogue. Use when someone wants to pull every line a character or real person speaks across a source set in order to build or refine a voice profile, or says "extract X's corpus", "pull every line X says", "build the voice corpus for X", "get all of X's dialogue", or needs analysis-ready dialogue separated out by speaker.
---

# Voice corpus extractor

Turn a folder of speaker-attributed sources into one speaker's complete, source-cited corpus, with a header of countable voice metrics. The corpus is the deliverable, and it is the deterministic front end that feeds `voice-profile-builder`. This skill counts; it does not judge. Register, tone, and what a trait means belong to the builder downstream. This skill's only job is to pull the right lines, cite them, and measure what can be measured without opinion.

It reads four source formats, auto-detected per file: **screenplay** (movie scripts and TV episode transcripts), **stageplay** (theatre scripts), and **prose** (novels and short fiction). Poetry is out of scope in this version. For prose it can emit a second, separate **narration** corpus so the builder can weight a character's spoken voice and their narrating voice independently.

One rule sits above the rest: a turn is attributed to a speaker or it is left out. The skill never guesses an attribution to pad a corpus. A corpus that includes a line the speaker did not say is worse than one that misses a line, because it teaches the builder a voice that is not real. This rule holds across every format: an untagged quote in prose is dropped exactly as an unlabeled block in a script is.

## When to use

Trigger on any request to pull one speaker's lines out of a source set for voice work: "extract Al's corpus," "pull every line Bullock says," "build the voice corpus for X." The source is a folder of files where speech is attributable — a script with character cues, or prose with dialogue tags. One speaker per run. Do not use this to summarize a source, to extract a scene, or to profile a voice; profiling is `voice-profile-builder`'s job, and this skill hands off to it.

## The work is a script, not a re-derivation

This is a fragile data operation. One wrong attribution corrupts every profile built on the corpus, so the parsing is not improvised per run. The skill runs the bundled, tested `scripts/extract_corpus.py`. Do NOT hand-parse sources, do NOT write a fresh regex in the chat, do NOT eyeball-extract. If the script's detected format is wrong for a file, force it with `--format`; if the source does not fit any of the block models, say so and stop rather than work around it.

## Reference loading

Reading a reference means reading the whole file. Skipping a named reference is the top failure mode for any skill. Load each at its step, not all up front.

- `references/source-format.md` — the format models (screenplay, stageplay, prose), the roster rule, how stage cues and cruft are handled, how prose dialogue is tagged and how narration is split out. MANDATORY at Step 2, before any extraction, and before any change to the script.
- `references/metric-defaults.md` — the thresholds, the profanity list, what each metric means and how to override it. MANDATORY at Step 4.
- `references/output-shape.md` — the corpus and registry layout, the two-file prose output, and how to read a run for correctness. MANDATORY at Step 5.
- `references/source-maps/<source>.json` — the filename-to-citation map. Load ONLY the one matching the source folder. Do NOT load every map; they are unrelated per-project configs.

Do NOT load the example runs in `examples/` unless you want a model of a clean run; they are not needed to operate the skill.

## Process

The one judgment step is roster confirmation, where the operator corrects what detection found. Everything else is mechanical: read the reference, run the script, read the output for correctness.

### Step 1: scope the run

Confirm the source folder, the target speaker, the project to write into, and whether the sources are scripts, prose, or mixed. State the labels you will assume for the target and let the operator correct them, since one character often appears under several labels (Bullock is labeled "Seth"). For prose, ask whether a narration corpus is wanted (default: dialogue only).

- Human in the loop: AskUserQuestion if folder, speaker, labels, or prose-narration intent are unclear.
- Output: a one-line run scope, including the format if the operator already knows it.

### Step 2: detect and confirm the roster

MANDATORY: read `references/source-format.md` in full first. Run the script in detect mode:

```
python3 scripts/extract_corpus.py --transcripts <DIR> --detect-roster
```

It prints the per-file format tally and every detected dialogue speaker with a turn count. Real speakers recur in the dozens to hundreds; stray matches sit at one or two. If the format tally looks wrong for any file (a stage play read as screenplay, a prose chapter read as a script), re-run that subset with `--format` forced, and confirm before extracting.

- Human in the loop: AskUserQuestion. Present the detected roster, the format tally, and the labels you will treat as the target. The operator confirms or corrects, and resolves any ambiguous label (two characters labeled "Bill") here. Never resolve ambiguity in code.
- Output: the confirmed target labels and the confirmed per-format routing.

### Step 3: extract

Run the script with the confirmed labels and the matching source map. Write the corpus into the project being profiled, and append the registry row in the skill folder. For prose where a narration corpus is wanted, add `--include-narration`; it writes a second file next to the dialogue corpus.

```
python3 scripts/extract_corpus.py \
  --transcripts <DIR> --speaker "<Name>" --labels "<l1,l2,...>" \
  --source-map references/source-maps/<source>.json \
  --out <PROJECT>/Reference/voice-corpus/<slug>.md \
  --registry registry.md
  # prose with a separate narration corpus:
  # --include-narration   (writes <slug>.narration.md alongside)
```

- Human in the loop: none.
- Output: the corpus file (and the narration file when requested) plus new registry rows.

### Step 4: confirm the metrics are sane

MANDATORY: read `references/metric-defaults.md` in full first. Check the stats against the quick reads in `output-shape.md`: turn count tracks the roster count for the main label, mean words per turn sits where the character's rhythm predicts, sources covered matches where the character appears. If a calibration character exists (Al returns ~54% short turns, ~7% arias), confirm the run is near it. For a narration corpus, confirm the cited narrator IS the target speaker before trusting it.

- Human in the loop: none, unless a number is off, then surface it.
- Output: a pass, or a named discrepancy and its likely cause.

### Step 5: report and hand off

MANDATORY: read `references/output-shape.md` in full first if you have not. Report the corpus path (both paths for prose with narration), the headline stats, any files skipped and why, and any unresolved label ambiguity. Name coverage and thin spots honestly so the builder knows where the evidence is thin. For prose, name how much of the corpus came from tagged dialogue versus how many quotes were dropped for having no adjacent tag. Hand the corpus path to `voice-profile-builder`.

- Human in the loop: AskUserQuestion. Offer to save this run as a good example.
- Output: a short report and the handoff pointer.

## Rules

These predict the failure modes. Update this section when the skill gets a correction.

1. **Read the reference files.** Steps that name a reference read it in full. Do not parse from memory of the format.
2. **Run the script, do not re-derive.** Extraction is `scripts/extract_corpus.py`. No hand-parsing, no fresh regex in chat. If a file's auto-detected format is wrong, force it with `--format`; if no model fits, stop and say so.
3. **Attribute or omit, never guess.** A turn whose speaker is not confirmed is left out, not assigned. In prose this means a quoted line with no adjacent dialogue tag is dropped, and a pronoun tag ("he said") is not resolved to a name. Inventing attribution is the cardinal sin.
4. **Count, do not judge.** Threshold-based metrics only. Register, tone, and meaning are the builder's job. Do not smuggle interpretation into the stats.
5. **Confirm the roster before extracting.** The detected roster and the format tally are shown to the operator and corrected before any turn is pulled. Ambiguous labels are surfaced, never resolved silently.
6. **One home for the corpus.** The full corpus lives in the project. The skill registry holds only a pointer and the stats, never a duplicate. On a re-run, overwrite the project file and append a fresh registry row.
7. **Stage cues are kept but never counted.** Parentheticals and bracketed directions stay in the corpus, inline, and are excluded from every word-based metric, in every format.
8. **Dialogue and narration never merge.** The narration corpus is a separate file with its own header and its own warning. Confirm the narrator is the target speaker before using it. Do not concatenate the two.
9. **Empty is reported, not written.** Zero turns means report and stop (the script exits 3). Do not write an empty corpus.
10. **State coverage honestly.** The report names total turns, source spread, files skipped, dropped-untagged-quote counts for prose, and thin spots, so the builder knows where the evidence is thin.

## Progressive updates and self-learning

1. When the operator defines a clear thing this skill should not do, update this rules section in place.
2. At the end of every run, ask via AskUserQuestion whether to save the run as a good example. On yes, write the run scope plus the stats plus the corpus path plus a timestamp to `examples/YYYY-MM-DD-HHMM.md`. Future runs may read `examples/` as a model of a clean extraction.

## Anti-patterns

Do not:

- Guess a speaker attribution to make a corpus look more complete. A wrong line corrupts every profile built on it.
- Trust auto-detection blindly. A stage play with act headers can look like a screenplay; confirm the format tally before extracting.
- Resolve a prose pronoun tag ("she said") to a name in code. Anaphora is interpretation; the line is dropped, not guessed.
- Merge the narration corpus into the dialogue corpus, or assume the first-person narrator is the target without confirming.
- Count stage-cue words as spoken words. It inflates turn length and every metric downstream.
- Write a second copy of the corpus into the skill folder. Two copies drift; keep one source of truth and a pointer.
- Compute a register or tone label. That is interpretation, and it belongs to the builder.
- Ship a corpus without a coverage report. A corpus that hides its thin spots gets trusted where it should not be.

## Related

- `voice-profile-builder` (the downstream consumer)
- `scripts/extract_corpus.py` (the extractor, run it, do not re-derive it)
- `references/source-maps/` (load only the matching map)
