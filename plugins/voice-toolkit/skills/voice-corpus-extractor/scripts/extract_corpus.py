#!/usr/bin/env python3
"""extract_corpus.py — multi-format voice corpus extractor.

Turn a folder of source files into one speaker's complete, source-cited corpus,
with a header of countable voice metrics. The corpus is the deterministic front
end that feeds voice-profile-builder. This script COUNTS; it does not JUDGE.

Supported source formats (auto-detected per file, or forced with --format):

  screenplay   Movie scripts and TV episode transcripts. Speaker is an
               all-caps cue line (INT. ... excluded) or a "NAME:" block opener.
               Dialogue is the indented/following block until the next cue.
  stageplay    Stage / theatre scripts. "SPEAKER. dialogue" or "SPEAKER: dialogue",
               stage directions in (parens) or [brackets].
  prose        Novels and short fiction. Quoted speech attributed by an adjacent
               dialogue tag ("...," said Al / Al said, "..."). With
               --include-narration, also emits a SEPARATE narration corpus
               (first-person narrator only, by default) so the builder can weight
               dialogue and narration independently.

One rule sits above the rest: a turn is attributed to a speaker or it is left
out. The script NEVER guesses an attribution to pad a corpus.

Exit codes: 0 ok, 2 usage/IO error, 3 zero turns extracted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Optional

# --------------------------------------------------------------------------- #
# Defaults. Override profanity via --profanity-file; thresholds via flags.
# These mirror references/metric-defaults.md. Keep the two in sync.
# --------------------------------------------------------------------------- #

DEFAULT_PROFANITY = {
    "fuck", "fucking", "fucked", "fucker", "fuckin", "motherfucker",
    "shit", "shitty", "bullshit", "horseshit", "cocksucker", "cunt",
    "bastard", "bitch", "ass", "asshole", "damn", "goddamn", "hell",
    "prick", "piss", "whore", "slut", "tits", "bollocks",
}

SHORT_TURN_MAX_WORDS = 4      # turns at or below this are "short"
ARIA_MIN_WORDS = 60           # turns at or above this are "arias"

# Stage-cue spans: parentheticals and bracketed directions. Kept inline in the
# corpus, excluded from every word-based metric.
STAGE_CUE_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")

# Scene / slug / structural lines that look like speaker cues but are not.
SLUGLINE_RE = re.compile(
    r"^(INT\.|EXT\.|INT/EXT|EXT/INT|FADE IN|FADE OUT|CUT TO|DISSOLVE|"
    r"SMASH CUT|MATCH CUT|CONTINUED|THE END|TITLE:|SUPER:|ANGLE ON|"
    r"CLOSE ON|WIDE ON|POV|MONTAGE|INTERCUT|"
    r"ACT\b|SCENE\b|PROLOGUE|EPILOGUE|INTERLUDE|CHORUS\b|CHAPTER\b|"
    r"PART\b|CANTO\b|ENTER\b|EXEUNT|EXIT\b|CURTAIN|DRAMATIS PERSONAE)",
    re.IGNORECASE,
)

# A screenplay character cue: an ALL-CAPS short line, optionally with a
# parenthetical extension like "AL (CONT'D)" or "AL (V.O.)".
SCREENPLAY_CUE_RE = re.compile(
    r"^[ \t]*(?P<name>[A-Z][A-Z0-9 .'\-&]{0,38})(?P<ext>\s*\([^)]*\))?\s*:?\s*$"
)

# A "NAME:" inline block opener (TV transcript / interview style).
LABEL_COLON_RE = re.compile(r"^[ \t]*(?P<name>[^:\n]{1,42}):\s*(?P<rest>.*)$")

# A stageplay speaker cue: "SPEAKER." or "SPEAKER:" then dialogue on same line
# or following lines. Speaker is title-case-or-caps, short.
STAGEPLAY_CUE_RE = re.compile(
    r"^[ \t]*(?P<name>[A-Z][A-Za-z0-9 .'\-]{0,32}?)[.:]\s+(?P<rest>\S.*)$"
)

# Prose dialogue tags. We match a quoted span adjacent to an attribution verb.
# Three quote conventions (curly-double, straight-double, British single-quote),
# auto-detected per file by which captures the most quoted text. MIRRORS the canonical
# detector in arc-structure-extractor/scripts/text_primitives.py — kept local because this
# is a self-contained, cross-domain script (it must run without a cross-plugin import).
# The single-quote close is apostrophe-aware: a ’ before a letter is a contraction
# ("don’t"), not a quote close — without this, British dialogue (Waugh) reads as ~0% and
# the roster comes back empty (the bug fixed 2026-06-15).
_QUOTE_CONVENTIONS = [
    ("curly-double",    re.compile(r"“(?P<said>[^”]+)”")),
    ("straight-double", re.compile(r'"(?P<said>[^"]+)"')),
    ("single-quote",    re.compile(r"‘(?P<said>[^‘]*?)’(?![A-Za-z])")),
]
# Coarse "is there any quoted speech here" matcher for format detection (any convention).
ANY_QUOTE_RE = re.compile(r"“[^”]+”|\"[^\"]+\"|‘[^‘]*?’(?![A-Za-z])")


def dominant_quote_re(text):
    """The quote convention that captures the most quoted text in this file, as a
    compiled regex with a 'said' group. No quotes / ties fall back to curly-double."""
    best_re, best_chars = _QUOTE_CONVENTIONS[0][1], -1
    for _name, pat in _QUOTE_CONVENTIONS:
        chars = sum(len(m.group("said")) for m in pat.finditer(text))
        if chars > best_chars:
            best_re, best_chars = pat, chars
    return best_re
SAID_VERBS = (
    "said|asked|replied|answered|shouted|whispered|muttered|growled|"
    "snapped|cried|called|yelled|murmured|continued|added|began|"
    "exclaimed|hissed|sighed|laughed|spat|drawled|barked|roared|"
    "demanded|insisted|observed|remarked|noted|offered|countered|warned"
)
# "said Al" / "Al said" patterns around a quote. Name is 1-3 capitalized tokens.
NAME_TOK = r"[A-Z][a-zA-Z'\-]+"
TAG_AFTER_RE = re.compile(
    r"^[\s,]*(?:" + SAID_VERBS + r")\s+(?P<name>" + NAME_TOK + r"(?:\s+" + NAME_TOK + r"){0,2})"
)
TAG_AFTER_NAME_FIRST_RE = re.compile(
    r"^[\s,]*(?P<name>" + NAME_TOK + r"(?:\s+" + NAME_TOK + r"){0,2})\s+(?:" + SAID_VERBS + r")\b"
)

WORD_RE = re.compile(r"[A-Za-z0-9']+")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Turn:
    speaker: str
    text: str            # full text, stage cues kept inline
    source: str          # citation label for the file this came from
    kind: str = "dialogue"   # "dialogue" or "narration"


@dataclass
class Stats:
    turns: int = 0
    spoken_words: int = 0
    word_lengths: list = field(default_factory=list)
    short_turns: int = 0
    arias: int = 0
    profane_words: int = 0
    sources: set = field(default_factory=set)


def spoken_text(text: str) -> str:
    """Text with stage cues removed, for word-based metrics only."""
    return STAGE_CUE_RE.sub(" ", text)


def count_words(text: str) -> list[str]:
    return WORD_RE.findall(spoken_text(text).lower())


# --------------------------------------------------------------------------- #
# Format detection
# --------------------------------------------------------------------------- #

def detect_format(text: str) -> str:
    """Best-effort per-file format guess. Conservative: ties go to prose,
    because a wrong screenplay guess on prose invents turns, which is the
    cardinal sin. The operator can always force with --format."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "prose"
    sample = lines[:400]

    caps_cue_own_line = 0     # screenplay: NAME on its own line
    colon_labels = 0          # transcript: NAME: ...  (screenplay parser handles)
    period_inline_cues = 0    # stageplay: NAME. dialogue  (period form, distinctive)
    quote_lines = 0

    for ln in sample:
        stripped = ln.strip()
        if SLUGLINE_RE.match(stripped):
            continue  # structural line, not a cue and not a counter-signal
        # Bare ALL-CAPS cue on its own line (screenplay).
        m = SCREENPLAY_CUE_RE.match(ln)
        if m and not LABEL_COLON_RE.match(ln):
            name = m.group("name").strip()
            if name and len(name.split()) <= 4 and name.upper() == name and not name.isdigit():
                caps_cue_own_line += 1
                continue
        # NAME: ... opener.
        mlc = LABEL_COLON_RE.match(ln)
        if mlc and len(mlc.group("name").split()) <= 5:
            colon_labels += 1
        # NAME. dialogue  — the period form is the stageplay tell. The colon form
        # is ambiguous (both parsers handle it), so only the period counts here.
        msp = STAGEPLAY_CUE_RE.match(ln)
        if msp and "." in ln[: ln.find(msp.group("rest"))]:
            name = msp.group("name").strip()
            if name and name[0].isupper() and len(name.split()) <= 4:
                period_inline_cues += 1
        if ANY_QUOTE_RE.search(ln):
            quote_lines += 1

    n = max(len(sample), 1)
    # Period-delimited cues are the unambiguous stageplay signature; the
    # screenplay parser cannot read them, so route to stageplay first.
    if period_inline_cues / n > 0.10 and period_inline_cues >= caps_cue_own_line:
        return "stageplay"
    # Bare caps cues or NAME: openers: screenplay parser handles both.
    if (caps_cue_own_line + colon_labels) / n > 0.10:
        return "screenplay"
    if quote_lines / n > 0.05:
        return "prose"
    if period_inline_cues:
        return "stageplay"
    return "screenplay" if caps_cue_own_line else "prose"


# --------------------------------------------------------------------------- #
# Normalisation helpers
# --------------------------------------------------------------------------- #

def norm_label(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().upper()


# --------------------------------------------------------------------------- #
# Parsers. Each returns a list[Turn] of ALL speakers (roster), unfiltered.
# Filtering to the target speaker happens once, centrally.
# --------------------------------------------------------------------------- #

def parse_screenplay(text: str, source: str) -> list[Turn]:
    """Caps-cue screenplays AND 'NAME:' transcript blocks. A turn opens on a
    cue and runs until the next cue or a blank-line-then-non-dialogue."""
    turns: list[Turn] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    cur_name: Optional[str] = None
    cur_buf: list[str] = []

    def flush():
        nonlocal cur_name, cur_buf
        if cur_name is not None:
            body = "\n".join(cur_buf).strip()
            if body:
                turns.append(Turn(norm_label(cur_name), body, source))
        cur_name, cur_buf = None, []

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        if not stripped:
            cur_buf.append("")
            i += 1
            continue

        if SLUGLINE_RE.match(stripped):
            flush()
            i += 1
            continue

        # NAME: rest  (inline opener)
        mlc = LABEL_COLON_RE.match(raw)
        if mlc:
            name = mlc.group("name").strip()
            # Avoid matching dialogue with an internal colon: opener name must be
            # short and not a full sentence.
            if len(name.split()) <= 5 and not name.endswith((".", "!", "?")):
                flush()
                cur_name = name
                rest = mlc.group("rest").strip()
                cur_buf = [rest] if rest else []
                i += 1
                continue

        # Bare ALL-CAPS cue line
        msc = SCREENPLAY_CUE_RE.match(raw)
        if msc:
            name = msc.group("name").strip()
            if name and len(name.split()) <= 4 and name.upper() == name and not name.isdigit():
                flush()
                cur_name = name
                cur_buf = []
                i += 1
                continue

        # Otherwise it's body text for the current turn (or orphan narration).
        if cur_name is not None:
            cur_buf.append(stripped)
        i += 1

    flush()
    # Collapse trailing blank lines inside bodies.
    for t in turns:
        t.text = re.sub(r"\n{2,}", "\n", t.text).strip()
    return [t for t in turns if t.text]


def parse_stageplay(text: str, source: str) -> list[Turn]:
    turns: list[Turn] = []
    lines = text.splitlines()
    cur_name: Optional[str] = None
    cur_buf: list[str] = []

    def flush():
        nonlocal cur_name, cur_buf
        if cur_name is not None:
            body = "\n".join(cur_buf).strip()
            if body:
                turns.append(Turn(norm_label(cur_name), body, source))
        cur_name, cur_buf = None, []

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            cur_buf.append("")
            continue
        # A whole-line stage direction.
        if (stripped.startswith("(") and stripped.endswith(")")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            if cur_name is not None:
                cur_buf.append(stripped)
            continue
        m = STAGEPLAY_CUE_RE.match(raw)
        if m:
            name = m.group("name").strip()
            # Speaker cue must be short and look like a name, not a sentence
            # that merely contains a period.
            if len(name.split()) <= 4 and not name[0].islower():
                flush()
                cur_name = name
                rest = m.group("rest").strip()
                cur_buf = [rest] if rest else []
                continue
        if cur_name is not None:
            cur_buf.append(stripped)

    flush()
    for t in turns:
        t.text = re.sub(r"\n{2,}", "\n", t.text).strip()
    return [t for t in turns if t.text]


def parse_prose(text: str, source: str, *, include_narration: bool,
                narration_mode: str) -> list[Turn]:
    """Dialogue: quoted spans with an adjacent attribution tag, attributed by
    name. Narration: optionally emitted as a SEPARATE corpus.

    narration_mode:
      first-person  emit narration only when the file reads as first-person
                    (a narrator who says "I"). Attribution is the target itself,
                    which the caller maps. This avoids guessing who narrates a
                    third-person passage.
      off           never emit narration (default when --include-narration unset)
    """
    turns: list[Turn] = []
    # Pick the file's dominant quote convention once (curly-double / straight-double /
    # British single-quote), so single-quote dialogue is not silently read as zero.
    quote_re = dominant_quote_re(text)

    # --- Dialogue extraction (sentence-ish granularity) ----------------------
    # We scan paragraph by paragraph, find each quote, and look at the text
    # immediately before and after for an attribution tag.
    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        flat = re.sub(r"\s+", " ", para).strip()
        if not flat:
            continue
        for m in quote_re.finditer(flat):
            said = m.group("said").strip()
            if not said or not WORD_RE.search(said):
                continue
            before = flat[:m.start()]
            after = flat[m.end():]
            name = None
            # "..." said Al   /  "..." Al said
            ma = TAG_AFTER_RE.match(after)
            if ma:
                name = ma.group("name")
            if name is None:
                ma2 = TAG_AFTER_NAME_FIRST_RE.match(after)
                if ma2:
                    name = ma2.group("name")
            # Al said, "..."   /  said Al, "..."
            if name is None:
                mb = TAG_AFTER_NAME_FIRST_RE.search(before[-60:])
                if mb:
                    name = mb.group("name")
            if name is None:
                mb2 = TAG_AFTER_RE.search(before[-60:])
                if mb2:
                    name = mb2.group("name")
            if name is None:
                # No tag adjacent to this quote: attribute-or-omit says OMIT.
                continue
            turns.append(Turn(norm_label(name), said, source, kind="dialogue"))

    # --- Narration extraction (separate corpus) ------------------------------
    if include_narration and narration_mode == "first-person":
        # Heuristic for a first-person narrator: the non-dialogue prose uses "I"
        # as a sentence subject often. We strip quotes, then keep narration
        # paragraphs. Attribution is left to the caller (the target speaker),
        # because a first-person narrator IS the POV character.
        narration_chunks: list[str] = []
        for para in paragraphs:
            stripped_quotes = quote_re.sub(" ", para)
            flat = re.sub(r"\s+", " ", stripped_quotes).strip()
            if not flat:
                continue
            narration_chunks.append(flat)
        joined = " ".join(narration_chunks)
        i_subjects = len(re.findall(r"(?:^|[.!?]\s+|\")\s*I\b", joined))
        sentences = max(len(re.findall(r"[.!?]", joined)), 1)
        if i_subjects / sentences > 0.12:
            for chunk in narration_chunks:
                if WORD_RE.search(chunk):
                    # speaker placeholder __NARRATOR__; caller remaps to target.
                    turns.append(Turn("__NARRATOR__", chunk, source, kind="narration"))

    return turns


# --------------------------------------------------------------------------- #
# Driving logic
# --------------------------------------------------------------------------- #

def load_source_map(path: Optional[str]) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("source map must be a JSON object of filename -> citation")
    return data


def citation_for(filename: str, source_map: dict) -> str:
    base = os.path.basename(filename)
    if base in source_map:
        return str(source_map[base])
    stem = os.path.splitext(base)[0]
    if stem in source_map:
        return str(source_map[stem])
    return stem


def iter_source_files(directory: str):
    exts = {".txt", ".md", ".markdown", ".fountain", ".fdx.txt"}
    for root, _dirs, files in os.walk(directory):
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext in exts or ext == "":
                yield os.path.join(root, fn)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse_file(path: str, source: str, fmt: str, *, include_narration: bool,
               narration_mode: str) -> tuple[list[Turn], str]:
    text = read_text(path)
    used = fmt if fmt != "auto" else detect_format(text)
    if used == "screenplay":
        return parse_screenplay(text, source), used
    if used == "stageplay":
        return parse_stageplay(text, source), used
    if used == "prose":
        return parse_prose(text, source, include_narration=include_narration,
                           narration_mode=narration_mode), used
    raise ValueError(f"unknown format: {used}")


def compute_stats(turns: list[Turn], profanity: set[str]) -> Stats:
    st = Stats()
    for t in turns:
        words = count_words(t.text)
        st.turns += 1
        st.spoken_words += len(words)
        st.word_lengths.append(len(words))
        if len(words) <= SHORT_TURN_MAX_WORDS:
            st.short_turns += 1
        if len(words) >= ARIA_MIN_WORDS:
            st.arias += 1
        st.profane_words += sum(1 for w in words if w in profanity)
        st.sources.add(t.source)
    return st


def pct(part: int, whole: int) -> float:
    return (100.0 * part / whole) if whole else 0.0


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def stats_header(speaker: str, kind: str, st: Stats, profanity_n: int) -> str:
    mean_w = (st.spoken_words / st.turns) if st.turns else 0.0
    med_w = median(st.word_lengths) if st.word_lengths else 0
    lines = [
        f"# Voice corpus — {speaker} ({kind})",
        "",
        "> Generated by voice-corpus-extractor. This file COUNTS; it does not",
        "> JUDGE. Register, tone, and meaning belong to voice-profile-builder.",
        "",
    ]
    if kind == "narration":
        lines += [
            f"> NARRATION CORPUS. These passages are the first-person narrator of "
            f"the cited sources, bound here to {speaker}. Confirm {speaker} IS that "
            "narrator before feeding this to the builder. Keep it separate from the "
            "dialogue corpus; do not merge the two.",
            "",
        ]
    lines += [
        "## Metrics",
        "",
        f"- turns: {st.turns}",
        f"- spoken words (stage cues excluded): {st.spoken_words}",
        f"- mean words/turn: {mean_w:.1f}",
        f"- median words/turn: {med_w}",
        f"- short turns (<= {SHORT_TURN_MAX_WORDS} words): {st.short_turns} "
        f"({pct(st.short_turns, st.turns):.1f}%)",
        f"- arias (>= {ARIA_MIN_WORDS} words): {st.arias} "
        f"({pct(st.arias, st.turns):.1f}%)",
        f"- profanity rate: {st.profane_words} hits "
        f"({pct(st.profane_words, st.spoken_words):.2f}% of spoken words; "
        f"list size {profanity_n})",
        f"- sources covered: {len(st.sources)}",
        "",
        "## Corpus",
        "",
    ]
    return "\n".join(lines)


def render_corpus(speaker: str, kind: str, turns: list[Turn], st: Stats,
                  profanity_n: int) -> str:
    out = [stats_header(speaker, kind, st, profanity_n)]
    last_source = None
    for t in turns:
        if t.source != last_source:
            out.append(f"\n### {t.source}\n")
            last_source = t.source
        # Keep stage cues inline exactly as captured.
        body = t.text.replace("\n", " ").strip()
        out.append(f"- {body}")
    out.append("")
    return "\n".join(out)


def append_registry(registry_path: str, row: dict) -> None:
    header = (
        "| timestamp | speaker | kind | format(s) | turns | spoken_words | "
        "short% | aria% | sources | corpus_path |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    line = (
        f"| {row['timestamp']} | {row['speaker']} | {row['kind']} | "
        f"{row['formats']} | {row['turns']} | {row['spoken_words']} | "
        f"{row['short_pct']:.1f} | {row['aria_pct']:.1f} | {row['sources']} | "
        f"{row['corpus_path']} |\n"
    )
    exists = os.path.exists(registry_path)
    needs_header = True
    if exists:
        with open(registry_path, "r", encoding="utf-8") as fh:
            needs_header = "| timestamp |" not in fh.read()
    with open(registry_path, "a", encoding="utf-8") as fh:
        if needs_header:
            fh.write("# voice-corpus-extractor registry\n\n")
            fh.write(header)
        fh.write(line)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def cmd_detect_roster(args, profanity) -> int:
    counts: dict[str, dict] = {}
    fmt_tally: dict[str, int] = {}
    files = list(iter_source_files(args.transcripts))
    if not files:
        print(f"No source files found under {args.transcripts}", file=sys.stderr)
        return 2
    for path in files:
        text = read_text(path)
        used = args.format if args.format != "auto" else detect_format(text)
        fmt_tally[used] = fmt_tally.get(used, 0) + 1
        if used == "screenplay":
            turns = parse_screenplay(text, path)
        elif used == "stageplay":
            turns = parse_stageplay(text, path)
        else:
            turns = parse_prose(text, path, include_narration=False,
                                narration_mode="off")
        for t in turns:
            if t.kind != "dialogue":
                continue
            rec = counts.setdefault(t.speaker, {"turns": 0, "files": set()})
            rec["turns"] += 1
            rec["files"].add(os.path.basename(path))

    print(f"Files scanned: {len(files)}")
    print("Format tally: " + ", ".join(f"{k}={v}" for k, v in sorted(fmt_tally.items())))
    print("\nDetected roster (dialogue speakers), by turn count:\n")
    print(f"{'label':<28} {'turns':>6}  files")
    print("-" * 60)
    for name, rec in sorted(counts.items(), key=lambda kv: -kv[1]["turns"]):
        print(f"{name:<28} {rec['turns']:>6}  {len(rec['files'])}")
    print("\nReal speakers recur in the dozens-to-hundreds; stray matches sit "
          "at 1-2. Confirm the target labels before extracting.")
    return 0


def cmd_extract(args, profanity) -> int:
    labels = {norm_label(x) for x in (args.labels or args.speaker).split(",") if x.strip()}
    if not labels:
        print("No labels resolved for the target speaker.", file=sys.stderr)
        return 2

    source_map = load_source_map(args.source_map)
    files = list(iter_source_files(args.transcripts))
    if not files:
        print(f"No source files found under {args.transcripts}", file=sys.stderr)
        return 2

    dialogue: list[Turn] = []
    narration: list[Turn] = []
    formats_used: dict[str, int] = {}
    skipped: list[tuple[str, str]] = []

    for path in files:
        citation = citation_for(path, source_map)
        try:
            turns, used = parse_file(
                path, citation, args.format,
                include_narration=args.include_narration,
                narration_mode=args.narration_mode,
            )
        except Exception as exc:  # defensive: one bad file must not kill the run
            skipped.append((os.path.basename(path), f"parse error: {exc}"))
            continue
        formats_used[used] = formats_used.get(used, 0) + 1
        matched = 0
        for t in turns:
            if t.kind == "dialogue" and t.speaker in labels:
                dialogue.append(t)
                matched += 1
            elif t.kind == "narration" and args.include_narration:
                # First-person narrator IS the target POV character.
                t.speaker = norm_label(args.speaker)
                narration.append(t)
                matched += 1
        if matched == 0:
            skipped.append((os.path.basename(path), "no matching turns"))

    if not dialogue and not narration:
        print("Zero turns extracted for "
              f"{args.speaker} (labels: {', '.join(sorted(labels))}). "
              "Nothing written.", file=sys.stderr)
        if skipped:
            print("Skipped files:", file=sys.stderr)
            for fn, why in skipped:
                print(f"  - {fn}: {why}", file=sys.stderr)
        return 3

    fmt_str = ", ".join(f"{k}:{v}" for k, v in sorted(formats_used.items()))
    written = []

    def write_one(turns: list[Turn], kind: str, out_path: str):
        st = compute_stats(turns, profanity)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(render_corpus(args.speaker, kind, turns, st, len(profanity)))
        written.append((kind, out_path, st))
        if args.registry:
            append_registry(args.registry, {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "speaker": args.speaker,
                "kind": kind,
                "formats": fmt_str,
                "turns": st.turns,
                "spoken_words": st.spoken_words,
                "short_pct": pct(st.short_turns, st.turns),
                "aria_pct": pct(st.arias, st.turns),
                "sources": len(st.sources),
                "corpus_path": out_path,
            })

    if dialogue:
        write_one(dialogue, "dialogue", args.out)
    if narration:
        narr_path = args.narration_out or _sibling(args.out, "narration")
        write_one(narration, "narration", narr_path)

    # Report
    print(f"Speaker: {args.speaker}   labels: {', '.join(sorted(labels))}")
    print(f"Formats: {fmt_str}")
    for kind, path, st in written:
        print(f"\n[{kind}] -> {path}")
        print(f"  turns={st.turns}  spoken_words={st.spoken_words}  "
              f"short={pct(st.short_turns, st.turns):.1f}%  "
              f"aria={pct(st.arias, st.turns):.1f}%  sources={len(st.sources)}")
    if skipped:
        print("\nSkipped / thin files:")
        for fn, why in skipped:
            print(f"  - {fn}: {why}")
    return 0


def _sibling(path: str, suffix: str) -> str:
    root, ext = os.path.splitext(path)
    return f"{root}.{suffix}{ext or '.md'}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--transcripts", "--sources", dest="transcripts", required=True,
                   help="folder of source files (screenplays, plays, prose)")
    p.add_argument("--format", choices=["auto", "screenplay", "stageplay", "prose"],
                   default="auto", help="force a source format (default: auto-detect per file)")
    p.add_argument("--detect-roster", action="store_true",
                   help="print the detected speaker roster and exit")
    p.add_argument("--speaker", help="target speaker display name")
    p.add_argument("--labels", help="comma-separated labels the speaker appears under "
                                     "(defaults to --speaker)")
    p.add_argument("--source-map", "--episode-map", dest="source_map",
                   help="JSON map of filename -> citation label")
    p.add_argument("--out", help="output corpus path (dialogue)")
    p.add_argument("--narration-out", help="output path for the narration corpus "
                                            "(default: <out>.narration.md)")
    p.add_argument("--include-narration", action="store_true",
                   help="prose only: also emit a separate narration corpus")
    p.add_argument("--narration-mode", choices=["first-person", "off"],
                   default="first-person",
                   help="how to attribute narration (default first-person)")
    p.add_argument("--registry", help="registry markdown to append a run row to")
    p.add_argument("--profanity-file", help="newline-separated profanity overrides")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if not os.path.isdir(args.transcripts):
        print(f"Not a directory: {args.transcripts}", file=sys.stderr)
        return 2

    profanity = set(DEFAULT_PROFANITY)
    if args.profanity_file:
        try:
            with open(args.profanity_file, "r", encoding="utf-8") as fh:
                profanity = {w.strip().lower() for w in fh if w.strip()}
        except OSError as exc:
            print(f"Could not read profanity file: {exc}", file=sys.stderr)
            return 2

    if args.detect_roster:
        return cmd_detect_roster(args, profanity)

    if not args.speaker:
        print("--speaker is required for extraction (or use --detect-roster).",
              file=sys.stderr)
        return 2
    if not args.out:
        print("--out is required for extraction.", file=sys.stderr)
        return 2

    return cmd_extract(args, profanity)


if __name__ == "__main__":
    sys.exit(main())
