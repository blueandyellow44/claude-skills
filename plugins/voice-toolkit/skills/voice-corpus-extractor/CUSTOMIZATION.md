# Customization notes

This is a customized build of `character-engine:voice-corpus-extractor`, expanded from screenplay/transcript sources to also read stage plays and prose novels.

## Provenance

The installed skill's cache exposed only `SKILL.md` — the original `scripts/extract_corpus.py` and reference files were not present on disk and could not be read or patched. So `scripts/extract_corpus.py` here is a fresh, tested implementation built to the SKILL.md contract, not a diff of the original. Flag names, the registry column layout, and the source-map concept were kept compatible with what the original SKILL.md described (`--transcripts`, `--detect-roster`, `--speaker`, `--labels`, `--out`, `--registry`, episode/source maps). If you still have the original script anywhere, diff the metric thresholds and the Al calibration numbers against it before trusting cross-run comparisons.

## What changed from the original

- **Three source formats, auto-detected per file**: `screenplay` (movie scripts + `NAME:` TV transcripts, the original behavior), `stageplay` (period-delimited theatre cues like `HAMLET.`), and `prose` (novels). Force any file with `--format`.
- **Prose dialogue extraction** by adjacent tag (`"..." said Al` / `Al said, "..."`), attribute-or-omit preserved: untagged quotes and pronoun tags are dropped, never guessed.
- **Separate narration corpus** for prose via `--include-narration`, written to `<slug>.narration.md` with its own header and a confirm-the-narrator warning. Dialogue and narration never merge.
- **Roster detection now reports a per-file format tally** so a misroute is visible before extraction.
- **Structural lines excluded** as cues across formats: `ACT`, `SCENE`, `CHAPTER`, `ENTER`, `EXEUNT`, etc., on top of the original `INT./EXT.` sluglines.
- References renamed/expanded: `transcript-format.md` -> `source-format.md`; `episode-maps/` -> `source-maps/`. `metric-defaults.md` and `output-shape.md` updated for the two-file prose output.

## Poetry

Out of scope in this version by request. The hook to add it later is a fourth format whose "speaker" is the whole work or a labeled dramatic speaker; nothing in the current structure blocks it.

## Install

The skill folder is delivered two ways: written into your vault at `Skills/voice-corpus-extractor/`, and packaged as `voice-corpus-extractor.skill` (a zip) in outputs. Because the running skill is a read-only cache, replacing the installed copy is done through Settings > Capabilities, not by editing the cache in place.
