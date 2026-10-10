#!/usr/bin/env python3
"""
List what the owner decided in the transcripts and how each decision stands against
the project hub. A LEAD LIST for a person or session to read, not a classifier.

Cause it fixes: a decision is made in conversation and never written to the hub
or the code, so a later session reports it as undecided.

For every typed message that reads like a durable decision, the record (hub, and
project memory unless --no-memory) is searched for the owner's words:

  EXACT        the whole message is quoted in the record. Shown with the record
               line, because a quote can sit inside a line that REVERSES it.
  CONTRADICTED the record line holding those words also says remove / rejected /
               superseded / no longer / never. Always shown.
  PARTIAL      some five-word run is in the record, the whole message is not.
               Shared words do not establish agreement; shown with the line.
  ABSENT       none of the words are in the record.

Immediate permissions ("approved", "do it", "deploy it") and questions are listed
apart: they authorise one action and are not durable rules. Messages whose
authorship is uncertain (a controller relaying the owner, a scripted prompt, text
copied back from the assistant) are listed apart and never counted as rulings.

LIMITS: markers are keyword patterns. A decision phrased without one is missed;
a complaint phrased with one is listed. Whether a record line AGREES is
a judgment this script does not make. Paraphrases in the record read as ABSENT.

The project is resolved from the working folder (or --project), its hub and EVERY
project-memory folder that resolves to it are searched, and its transcripts are
read. The vault is the SECOND_BRAIN_VAULT environment variable; an explicit --hub
FILE with --transcripts needs neither.

Usage: sweep_rulings.py [--project HUB] [--hub FILE] [--since YYYY-MM-DD] [--grep TERM] [--top N]
                        [--no-memory] [--transcripts GLOB ...] [--show-exact]
Exit 1 when any decision is ABSENT, PARTIAL or CONTRADICTED; 0 otherwise.
"""
import argparse, glob, os, re, sys

# The shared, project-aware helpers live with object-record in the same plugin.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "object-record", "scripts"))
import project_record as cw

DURABLE = re.compile(r"\b(never|always|must|has to|have to|need(s)? to|from now on|no more|i want|we want|i don'?t want|should(n'?t| not)? be|only|not allowed"
                     r"|would ruin|take my word|rule|ruling|we decided|key decision|kill it|take it off|private|public|by default|durable|universal|every (page|piece|route|screen|time))\b", re.I)
PERMISSION = re.compile(r"^\W*(yes|yep|ok(ay)?|approved?|do it|go ahead|go|deploy( it| to [\w.]+)?|ship it|click it|proceed|continue|sure)\b[\W\w]{0,60}$", re.I)
QUESTION_ONLY = re.compile(r"^[^.!]*\?\s*$")
NEGATION = re.compile(r"\b(remove[ds]?|removal|rejected?|superseded|no longer|reversed?|never|not\b|do not|don'?t|struck|withdrawn|off the map|killed?)\b", re.I)


def norm_words(t):
    return re.sub(r"[^a-z0-9 ]+", " ", t.lower().replace("'", "").replace("’", "")).split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--hub", default=None); ap.add_argument("--since", default="")
    ap.add_argument("--grep"); ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--no-memory", action="store_true"); ap.add_argument("--show-exact", action="store_true")
    ap.add_argument("--transcripts", nargs="*")
    a = ap.parse_args()
    try:
        info = cw.configure(project=a.project)
        print(f"project: {info['hub']} ({info['how']}); memory dirs: {len(info['memory_dirs'])}")
    except SystemExit as exc:
        if not a.hub:
            raise
        info = None   # an explicit --hub (fixtures, other vaults): no memory or transcripts unless given
        print(f"project: not resolved ({exc}); checking --hub only")
    a.hub = a.hub or info["hub_path"]
    files = [a.hub] + ([] if a.no_memory else cw.memory_files(include_index=True))
    lines = []   # (file, lineno, raw, " normalised ")
    for f in files:
        for i, raw in enumerate(open(f, encoding="utf-8", errors="replace").read().splitlines(), 1):
            w = norm_words(raw)
            if w:
                lines.append((os.path.basename(f), i, raw, " " + " ".join(w) + " "))

    def locate(words):
        """-> (level, record line or None). Whole message first, then any 5-word run."""
        whole = " " + " ".join(words) + " "
        for f, i, raw, nw in lines:
            if whole in nw:
                return "EXACT", (f, i, raw)
        for k in range(len(words) - 4):
            run = " " + " ".join(words[k:k + 5]) + " "
            for f, i, raw, nw in lines:
                if run in nw:
                    return "PARTIAL", (f, i, raw)
        return "ABSENT", None

    buckets = {k: [] for k in ("ABSENT", "CONTRADICTED", "PARTIAL", "EXACT", "PERMISSION", "UNCERTAIN")}
    seen = set()
    for m in cw.human_messages(a.transcripts or cw.transcripts()):
        text = m["typed"]
        if m["ts"][:10] < a.since or not text or len(text) > 1500 or text in seen:
            continue
        seen.add(text)
        if a.grep and a.grep.lower() not in text.lower():
            continue
        words = norm_words(text)
        flat = " ".join(text.split())[:300]
        where = f"{m['ts']} [{m['sid']} row {m['row']}]"
        if m["source"] != "typed" or m["relay"]:
            if DURABLE.search(text):
                buckets["UNCERTAIN"].append((where, flat, "scripted prompt" if m["source"] != "typed" else "relays the owner in the third person"))
            continue
        if PERMISSION.match(text.strip()) and not DURABLE.search(text):
            buckets["PERMISSION"].append((where, flat, ""))
            continue
        if QUESTION_ONLY.match(text.strip()) or not DURABLE.search(text) or len(words) < 4:
            continue
        note = " [assistant text was also copied back here; only the typed words are shown]" if m["copied"] else ""
        level, hit = locate(words) if len(words) >= 5 else ("ABSENT", None)
        if hit and NEGATION.search(hit[2]) and not NEGATION.search(text):
            level = "CONTRADICTED"
        rec = f"{hit[0]}:{hit[1]}: {' '.join(hit[2].split())[:240]}" if hit else ""
        buckets[level].append((where, flat + note, rec))

    print("record checked: " + ", ".join(files))
    print("transcripts: " + (", ".join(a.transcripts) if a.transcripts else "default globs") + "; times UTC\n")
    titles = [("CONTRADICTED", "the owner's words are in a record line that also says remove / rejected / not. READ IT: the record may reverse them"),
              ("ABSENT", "none of the owner's words are in the record"),
              ("PARTIAL", "some of the owner's words are in the record; this does NOT show the record agrees"),
              ("EXACT", "the whole message is quoted in the record (read the line to confirm it agrees)"),
              ("UNCERTAIN", "authorship uncertain; not counted as the owner's rulings"),
              ("PERMISSION", "immediate go-aheads; they authorise one action, not a standing rule")]
    for key, title in titles:
        rows = buckets[key]
        print(f"## {key}: {len(rows)}  ({title})")
        if key in ("EXACT", "PERMISSION") and not a.show_exact:
            print("   (not listed; --show-exact lists them)\n")
            continue
        for where, flat, rec in rows[:a.top]:
            print(f"- {where} \"{flat}\"" + (f"\n    record -> {rec}" if rec else ""))
        if len(rows) > a.top:
            print(f"   ... {len(rows) - a.top} more (raise --top)")
        print()
    print("Every line is a lead. Read it in its transcript row, decide whether it is a ruling, then capture it verbatim and dated (ruling-capture) or say why not.")
    sys.exit(1 if any(buckets[k] for k in ("ABSENT", "PARTIAL", "CONTRADICTED")) else 0)


if __name__ == "__main__":
    main()
