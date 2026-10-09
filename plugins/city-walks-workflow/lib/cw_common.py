"""Shared helpers for the city-walks-workflow scripts. Stdlib only."""
import os, re

# The map app's repo. Set CITY_WALKS_REPO to its path. Unset, the hooks stay silent
# and the scripts ask for --repo.
REPO = os.path.expanduser(os.environ.get("CITY_WALKS_REPO", ""))

# How each piece is named in conversation. Used ONLY to decide which piece a stretch
# of transcript is about; loose single words are acceptable there and nowhere else.
PIECE_ALIASES = {
    "ferry-building": ["ferry building", "ferry", "the pier"], "de-young": ["de young", "deyoung"],
    "legion-of-honor": ["legion"], "saints-peter-paul": ["saints peter", "sspp", "peter and paul"],
    "palace-of-fine-arts": ["palace"], "conservatory-of-flowers": ["conservatory"],
    "golden-gate-bridge": ["golden gate bridge", "gg bridge", "the bridge"], "salesforce-tower": ["salesforce", "sales force"],
    "coit-tower": ["coit"], "sutro-tower": ["sutro", "sutra"], "city-hall": ["city hall"],
    "grace-cathedral": ["grace cathedral"], "cliff-house": ["cliff house"], "dutch-windmill": ["windmill"],
    "columbus-tower": ["columbus"], "oracle-park": ["oracle park", "ballpark", "baseball"], "alcatraz": ["alcatraz"],
    "transamerica": ["transamerica", "trasamerica", "pyramid"],
}
_ALIAS_RE = {s: re.compile("|".join(re.escape(a) for a in [s] + al), re.I) for s, al in PIECE_ALIASES.items()}


def spellings(slug, extra=()):
    """ferry-building -> several ways the object is named in prose and code."""
    words = slug.replace("_", "-").split("-")
    out = {slug, " ".join(words), "".join(words)}
    if len(words) > 1:
        out.update(w for w in words if len(w) >= 5 and w not in {"tower", "house", "building", "park", "saints", "bridge", "young", "honor", "flowers", "cathedral", "golden", "windmill"})
    out.update(e for e in extra if e)
    return sorted(out, key=len, reverse=True)


def pattern(names):
    return re.compile("|".join(re.escape(n) for n in names), re.I)


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[*`_>#]| ", " ", t)).strip().lower()


def _words(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def _shingles(words, n=5):
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def pieces_named(text):
    """{slug: count} of known pieces named in a stretch of text."""
    return {s: len(r.findall(text)) for s, r in _ALIAS_RE.items() if r.search(text)}


def dominant(context, slug):
    """Was `slug` THE piece on the table? Named in the last assistant turn, and at
    least twice as often as any other piece. A set-wide discussion has no dominant piece."""
    mine = context.get(slug, 0)
    others = max([c for s, c in context.items() if s != slug], default=0)
    return mine >= 1 and mine >= 2 * others


def excerpt(text, match, width=220):
    a = max(0, match.start() - width // 2)
    b = min(len(text), match.end() + width // 2)
    s = " ".join(text[a:b].split())
    return ("..." if a else "") + s + ("..." if b < len(text) else "")
