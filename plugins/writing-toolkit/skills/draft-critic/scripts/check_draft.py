#!/usr/bin/env python3
"""
check_draft.py: the deterministic craft sheet for draft-critic.

Taste is not fully mechanical, but many of the tells that make a nonfiction draft read as generated or
over-polished ARE countable. Surfacing them first stops the critic from grading on vibes. This script
reads one draft and reports: sentence-rhythm flatness, filter and adverb density, abstraction leaks,
stock phrases, unintentional echoes, prestige-word frequency, closing-sentence suspicion, paragraph-close
patterns, verdict-shaped landings, and negation reveals ("This is not a plan. It is a wish.").

Every report is ADVISORY. The sheet finds candidates; a close reading decides which are real. An earned
repetition or a deliberate hard close is not a defect.

Exit codes: 0 whenever the draft is readable (no finding changes the exit code); 2 only when it is not.
Stdlib only.

Usage:
  python3 check_draft.py --draft <file.md> [--diction <words.txt>] [--phrases <phrases.txt>] [--json OUT]
"""

import argparse
import json
import os
import re
import sys

# Distancing verbs: "I realized that ..." holds the reader one step back from the thing itself.
FILTERS = ["felt", "saw", "watched", "noticed", "realized", "realised", "seemed", "knew",
           "understood", "heard", "wondered", "thought", "sensed", "observed", "perceived",
           "could see", "could feel", "could hear", "began to", "started to"]
# Abstraction leaks: analyst vocabulary standing where a concrete example belongs.
ABSTRACTION = ["load-bearing", "the dynamic", "essentially", "fundamentally", "on some level",
               "in a sense", "a kind of", "a sort of", "in many ways", "at its core",
               "the reality is", "the truth is", "metaphorically"]
# Starter list of stock phrases. Extend with --phrases; this is a pointer list, not a ban list.
STOCK = ["at the end of the day", "game changer", "game-changer", "in today's world",
         "in today's fast-paced", "it's worth noting", "it is worth noting", "needless to say",
         "move the needle", "low-hanging fruit", "think outside the box", "the elephant in the room",
         "a testament to", "plays a crucial role", "navigate the complexities", "in the realm of",
         "unlock the potential", "deep dive", "at the heart of", "heart pounded", "deep breath",
         "time stood still", "weight of the world"]
# Starter prestige-word families: words that read as considered once and as a tic by the third use.
# Counted per document. Extend with --diction.
DICTION = ["quiet", "quietly", "weight", "shape", "truly", "genuinely", "deeply", "profound",
           "crucial", "robust", "seamless", "journey", "landscape", "navigate", "leverage",
           "resonate", "nuanced", "tapestry", "delve", "matter", "mattered"]
DICTION_PHRASES = ["as if", "the thing that", "what it meant", "the whole of it", "here is the thing"]

SENT_SPLIT = re.compile(r"[.!?]+[\"'”’)]?\s+")  # quote-aware: breaks after `rarely can.”`
WORD = re.compile(r"\b[\w'’-]+\b")
ADVERB = re.compile(r"\b\w{3,}ly\b")
TOBE = re.compile(r"\b(was|were|is|are|been|being|be)\b", re.I)
ANTITHESIS = re.compile(r"\b(more\s+\w+\s+than\b|rather than\b|instead of\b|not\s+\w+,\s+not\s+\w+)", re.I)
# Negation reveal. STRUCTURAL shapes only: a negated copula taking a predicate NOUN ("is not a plan"),
# or a negated sentence followed by a short "It is..." reveal. Predicate adjectives ("was not ready")
# are excluded on purpose: ordinary negation is not a reveal.
NEG_COPULA_NOMINAL = re.compile(
    r"\b(?:is|are|was|were)\s+not\s+(?:a|an|the|its|his|her|their|my|our|your)\b"
    r"|\b(?:is|are|was|were)n(?:'|’)?t\s+(?:a|an|the|its|his|her|their|my|our|your)\b"
    r"|\bnone of (?:this|that|it|these|those|them)\s+(?:is|are|was|were)\b", re.I)
REVEAL_FOLLOWER = re.compile(
    r"^(?:It|That|This|They)(?:(?:'|’)s|(?:'|’)re|\s+is|\s+was|\s+are|\s+were)\b", re.I)
# Closing-sentence shapes that tend to seal a piece instead of ending it.
ENDING_PAT = [
    (r"\bnot\b[^.;]{1,40}?\bbut\b", "not-X-but-Y"),
    (r"the thing that told|was the thing that|the whole of it|that was that|that's that", "thesis/'the thing that'"),
    (r"\b(unsaid|what mattered|nobody said|neither of us said)\b", "silence-labeling"),
    (r"\blike (a|the|you|someone|something)\b[^.]{0,60}$", "trailing interpretive simile"),
    (r"\band that(?:'|’)?s (?:the|what|why|how)\b|\bthat is (?:the|what|why|how)\b", "summing-up close"),
]
STOP = set("the a an and or but of to in on at for with as it its his her their they she he you "
           "i we him them that this these those a was were is are be been had has have do did not "
           "so then there here from by into out up down over under again than".split())
SEPARATORS = ("* * *", "***", "---")
SHORT_CLOSE_WORDS = 8     # a paragraph-final sentence at or under this length counts as a short close
LONG_BUILD_WORDS = 30     # a sentence at or over this length before a short close is a long->short cadence
ECHO_WINDOW = 50          # words
ECHO_MIN = 3              # a content word this many times inside one window is an echo
DICTION_MIN = 3           # a family this many times per document is worth a justification
FLAT_STDEV = 6            # sentence-length stdev under this, over enough sentences, reads as a drone
FLAT_MIN_SENTENCES = 8


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def read_list(path):
    """Newline-separated extension list. Unreadable is reported, never fatal."""
    if not path:
        return [], None
    txt = read(path)
    if txt is None:
        return [], f"could not read {path}; ignored"
    return [t.strip().lower() for t in txt.splitlines() if t.strip() and not t.startswith("#")], None


def paragraphs(text):
    """Paragraph blocks from raw text. Headings and separators become boundaries, never content."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        lines.append("" if (s.startswith("#") or s in SEPARATORS) else line)
    return [p.strip() for p in re.split(r"\n\s*\n", "\n".join(lines)) if p.strip()]


def sentences(para):
    flat = " ".join(l.strip() for l in para.splitlines())
    return [s.strip() for s in SENT_SPLIT.split(flat) if s.strip()]


def strip_front_matter(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4:]
    return text


def body_text(text):
    """Prose only: drop headings, separators and blank lines."""
    return "\n".join(l for l in text.splitlines()
                     if l.strip() and not l.strip().startswith("#") and l.strip() not in SEPARATORS)


def clip(s, n=110):
    return s if len(s) <= n else s[:n - 3] + "…"


def line_hits(body, needles):
    hits, low = [], body.lower()
    for n in needles:
        start = 0
        while (i := low.find(n, start)) != -1:
            hits.append((n, body[max(0, i - 30): i + len(n) + 30].replace("\n", " ").strip()))
            start = i + len(n)
    return hits


def diction_counts(body, words, phrases):
    low, out = body.lower(), []
    for w in words:
        c = len(re.findall(r"\b" + re.escape(w) + r"\b", low))
        if c >= DICTION_MIN:
            out.append((w, c))
    for p in phrases:
        c = low.count(p)
        if c >= DICTION_MIN:
            out.append((p, c))
    return sorted(out, key=lambda x: -x[1])


def echoes(words):
    """Windowed maxima, not document totals: `word×4` means four is the most inside any 50-word window."""
    found, low = {}, [w.lower() for w in words]
    for i, w in enumerate(low):
        if w in STOP or len(w) < 4:
            continue
        c = low[i:i + ECHO_WINDOW].count(w)
        if c >= ECHO_MIN:
            found[w] = max(found.get(w, 0), c)
    return found


def ending_shape(sentence):
    for pat, label in ENDING_PAT:
        if re.search(pat, sentence, re.I):
            return label
    return None


def paragraph_closes(paras):
    """How paragraphs end. An inspection index, never a verdict: an earned hard close stays."""
    counts, examples, short_flags, cadence = {}, {}, [], []
    for p in paras:
        sents = sentences(p)
        if not sents:
            short_flags.append(False)
            continue
        last = sents[-1]
        is_short = len(WORD.findall(last)) <= SHORT_CLOSE_WORDS
        short_flags.append(is_short)
        if is_short and len(sents) >= 2 and len(WORD.findall(sents[-2])) >= LONG_BUILD_WORDS:
            cadence.append(clip(last, 100))
        label = ending_shape(last)
        if label:
            counts[label] = counts.get(label, 0) + 1
            examples.setdefault(label, [])
            if len(examples[label]) < 3:
                examples[label].append(clip(last))
    return {"paragraphs": len(paras), "short_closes": sum(short_flags),
            "short_close_rate": round(sum(short_flags) / max(1, len(paras)), 2),
            "short_close_runs": runs_of_three(short_flags),
            "long_then_short": len(cadence), "long_then_short_examples": cadence[:4],
            "pattern_counts": counts, "pattern_examples": examples}


def runs_of_three(flags):
    starts, run = [], 0
    for i, f in enumerate(flags):
        run = run + 1 if f else 0
        if run == 3:
            starts.append(i - 2)
    return starts


def verdict_landings(paras):
    """Paragraphs that END on a verdict-shaped sentence: balanced antithesis, negation reveal,
    X-not-Y apposition, thesis close, or a short gnomic line. One polished landing is craft; the flag is
    CLUSTERING, when paragraph after paragraph lands the same way. Structural shapes, no phrase lists."""
    gnomic = re.compile(r"\b(never|always|only|there (is|are) (two|one|no)\b)", re.I)
    verdict_open = re.compile(r"^(That|It|This|Such)('s| is| was| were)\b", re.I)
    apposition = re.compile(r"\b\w+,\s*not\s+(a|an|the|your|his|her|their)?\s*\w+", re.I)
    flags, examples = [], []
    for p in paras:
        sents = sentences(p)
        if not sents:
            flags.append(False)
            continue
        last, wc = sents[-1], len(WORD.findall(sents[-1]))
        shape = None
        if ANTITHESIS.search(last):
            shape = "balanced antithesis"
        elif NEG_COPULA_NOMINAL.search(last):
            shape = "negation reveal"
        elif wc <= 40 and apposition.search(last):
            shape = "X-not-Y apposition"
        elif ending_shape(last):
            shape = "thesis close"
        elif wc <= 18 and (gnomic.search(last) or verdict_open.match(last)):
            shape = "gnomic/verdict"
        flags.append(shape is not None)
        if shape and len(examples) < 6:
            examples.append((shape, clip(last)))
    return {"paragraphs": len(paras), "landings": sum(flags),
            "landing_rate": round(sum(flags) / max(1, len(paras)), 2),
            "runs": runs_of_three(flags), "examples": examples}


def negation_reveals(paras):
    """Every sentence and adjacent pair, not only paragraph closes: the shape often opens a paragraph.
    The governing test is LIVENESS, which only a reader can apply: was the negated idea ever something
    the reader was actually entertaining? If yes, the negation is doing argumentative work and stays."""
    singles, pairs, examples = 0, 0, []
    for p in paras:
        sents = sentences(p)
        for i, s in enumerate(sents):
            if not NEG_COPULA_NOMINAL.search(s):
                continue
            nxt = sents[i + 1] if i + 1 < len(sents) else None
            is_pair = bool(nxt and REVEAL_FOLLOWER.match(nxt) and len(WORD.findall(nxt)) <= 14)
            pairs, singles = (pairs + 1, singles) if is_pair else (pairs, singles + 1)
            if len(examples) < 6:
                examples.append(("negate-then-reveal pair" if is_pair else "negated noun",
                                 clip(s + ". " + nxt if is_pair else s, 120)))
    return {"total": singles + pairs, "pairs": pairs, "singles": singles, "examples": examples}


def closing_flags(paras):
    """Heightened suspicion on the last two paragraphs' final sentences: pieces over-polish their ends."""
    flags = []
    for p in paras[-2:]:
        sents = sentences(p)
        if sents and (label := ending_shape(sents[-1])):
            flags.append((label, clip(sents[-1], 130)))
    return flags


def build_sheet(raw, extra_diction=(), extra_phrases=()):
    raw = strip_front_matter(raw)
    body = body_text(raw)
    paras = paragraphs(raw)
    words = WORD.findall(body)
    sents = [s for s in SENT_SPLIT.split(body) if s.strip()]
    lens = [len(WORD.findall(s)) for s in sents] or [0]
    mean = sum(lens) / len(lens)
    stdev = (sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5
    return {
        "words": len(words), "sentences": len(sents),
        "sentence_mean": round(mean, 1), "sentence_stdev": round(stdev, 1),
        "flat_rhythm": stdev < FLAT_STDEV and len(sents) > FLAT_MIN_SENTENCES,
        "filters": line_hits(body, FILTERS),
        "abstraction": line_hits(body, ABSTRACTION),
        "stock_phrases": line_hits(body, STOCK + list(extra_phrases)),
        "adverbs": len(ADVERB.findall(body)), "to_be": len(TOBE.findall(body)),
        "echoes": echoes(words),
        "diction": diction_counts(body, DICTION + list(extra_diction), DICTION_PHRASES),
        "closing": closing_flags(paras),
        "paragraph_closes": paragraph_closes(paras),
        "verdict_landings": verdict_landings(paras),
        "negation_reveals": negation_reveals(paras),
    }


def print_sheet(name, s, notes):
    n = max(1, s["words"])
    per1k = lambda c: round(c / n * 1000, 1)
    print(f"# craft sheet: {name}  ({s['words']} words, {s['sentences']} sentences)")
    for note in notes:
        print(f"  note: {note}")
    print(f"  sentence length: mean {s['sentence_mean']}, stdev {s['sentence_stdev']}"
          + ("   ** LOW VARIANCE: rhythm may be flat **" if s["flat_rhythm"] else ""))
    print(f"  filter words: {len(s['filters'])} ({per1k(len(s['filters']))}/1k)   "
          f"-ly adverbs: {s['adverbs']} ({per1k(s['adverbs'])}/1k)   to-be: {s['to_be']} ({per1k(s['to_be'])}/1k)")
    for key, title in (("abstraction", "ABSTRACTION LEAK"), ("stock_phrases", "STOCK PHRASES")):
        if s[key]:
            print(f"  ** {title} ({len(s[key])}): **")
            for term, ctx in s[key]:
                print(f"     [{term}]  …{ctx}…")
    if s["echoes"]:
        top = sorted(s["echoes"].items(), key=lambda x: -x[1])[:8]
        print(f"  echoes (content word ≥{ECHO_MIN}x in {ECHO_WINDOW} words): " + ", ".join(f"{w}×{c}" for w, c in top))
    if s["filters"]:
        print("  filter-word loci (first 6): " + " | ".join(f"{t}:…{c}…" for t, c in s["filters"][:6]))
    if s["diction"]:
        print(f"  ** DICTION FREQUENCY ({len(s['diction'])} families ≥{DICTION_MIN}x): justify each kept use or cut. "
              "A single line edit does not fix a frequency problem. **")
        print("     " + ", ".join(f"{t}×{c}" for t, c in s["diction"]))
    if s["closing"]:
        print(f"  ** CLOSING SUSPICION ({len(s['closing'])}): the ending may seal instead of land **")
        for label, sent in s["closing"]:
            print(f"     [{label}]  {sent}")
    pc = s["paragraph_closes"]
    if pc["paragraphs"]:
        print("  paragraph closes (ADVISORY, an index, never a verdict):")
        print(f"     short closes (≤{SHORT_CLOSE_WORDS}w): {pc['short_closes']}/{pc['paragraphs']} "
              f"(rate {pc['short_close_rate']})   long→short cadences: {pc['long_then_short']}")
        if pc["short_close_runs"]:
            print(f"     runs of 3+ short closes start at paragraph: {pc['short_close_runs']}")
        for label, exs in pc["pattern_examples"].items():
            for e in exs[:2]:
                print(f"       [{label}]  {e}")
        for e in pc["long_then_short_examples"]:
            print(f"       [long→short]  {e}")
    vl = s["verdict_landings"]
    if vl["paragraphs"]:
        print("  verdict landings (ADVISORY, clustering is the flag; one good landing stays):")
        print(f"     {vl['landings']}/{vl['paragraphs']} paragraphs land on a verdict (rate {vl['landing_rate']})")
        if vl["runs"]:
            print(f"     runs of 3+ start at paragraph: {vl['runs']}")
        for shape, e in vl["examples"][:4]:
            print(f"       [{shape}]  {e}")
    nr = s["negation_reveals"]
    if nr["total"]:
        print(f"  negation reveals (ADVISORY): {nr['total']} ({nr['pairs']} pairs, {nr['singles']} single). "
              "Test: was the negated idea ever live for the reader?")
        for shape, e in nr["examples"][:4]:
            print(f"       [{shape}]  {e}")
    print("\n  sheet done. Every item above is a candidate; the close reading decides.")


def main():
    ap = argparse.ArgumentParser(description="Deterministic craft sheet for draft-critic.")
    ap.add_argument("--draft", required=True, help="the draft to read (markdown or plain text)")
    ap.add_argument("--diction", help="extra prestige words to count, one per line")
    ap.add_argument("--phrases", help="extra stock phrases to find, one per line")
    ap.add_argument("--json", help="also write the sheet as JSON to this path")
    args = ap.parse_args()
    raw = read(args.draft)
    if raw is None:
        print(f"cannot read --draft {args.draft}", file=sys.stderr)
        sys.exit(2)
    extra_d, note_d = read_list(args.diction)
    extra_p, note_p = read_list(args.phrases)
    sheet = build_sheet(raw, extra_d, extra_p)
    print_sheet(os.path.basename(args.draft), sheet, [n for n in (note_d, note_p) if n])
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(sheet, f, indent=2)
    sys.exit(0)


if __name__ == "__main__":
    main()
