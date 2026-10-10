"""Locate each approved beat in the raw footage by its opening and closing words.

For every beat: find the best fuzzy match of `from` anywhere in that source's word list, then the
best match of `to` within 420 s after it. Report match scores; anything under 0.72 is flagged for
review rather than guessed. Output: <project>/work/beats-mapped.json with raw start/end seconds per beat.
Exit code 2 when any beat is flagged: the plan needs a fix before alignment (never render past a flag).
Usage: python map_beats.py <project>
"""
import json, re, sys, difflib, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yr import Project  # noqa: E402
NUM = {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four', '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'}

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
SPOKEN = {'gonna': 'going to', 'wanna': 'want to', 'gotta': 'got to', 'kinda': 'kind of', 'sorta': 'sort of', "'cause": 'because', 'cause': 'because'}


def spell(n):
    """98 -> 'ninety eight' so a plan written in words matches ASR digits (and the reverse)."""
    if n < 20: return ONES[n]
    if n < 100: return TENS[n // 10] + ('' if n % 10 == 0 else ' ' + ONES[n % 10])
    if n < 1000: return ONES[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' and ' + spell(n % 100))
    return str(n)


def norm(t):
    t = t.lower().replace('’', "'").replace('-', ' ')
    t = re.sub(r'(\d)\.(\d)', r'\1 point \2', t).replace('%', ' ')   # "77.5%" -> seventy seven point five
    t = re.sub(r'(\d+):00\b', r'\1', t); t = re.sub(r'(\d+):(\d\d)', r'\1 \2', t)   # "9:00" -> 9, "9:30" -> 9 30
    t = re.sub(r'\b([ap])\.? ?m\b\.?', r'\1m', t)                         # "a.m." / "a m" -> am
    t = re.sub(r"n't\b", ' not', t); t = re.sub(r"'(ve|re|ll|m)\b", lambda m: ' ' + {'ve': 'have', 're': 'are', 'll': 'will', 'm': 'am'}[m.group(1)], t)
    t = re.sub(r"[^a-z0-9' ]", ' ', t)
    out = []
    for w in t.split():
        w = SPOKEN.get(w, w)
        if w.isdigit():
            w = spell(int(w))
        out.extend(w.split())
    return [w.strip("'") for w in out if w.strip("'")]

def find(words, phrase, lo=0, hi=None):
    q = norm(phrase); n = len(q); hi = len(words) if hi is None else hi
    toks = [norm(w['w']) for w in words]
    flat, owner = [], []
    for i, tk in enumerate(toks):
        for t in tk: flat.append(t); owner.append(i)
    best = (0, None, None)
    for j in range(len(flat) - n + 1):
        if owner[j] < lo or owner[j] >= hi: continue
        r = difflib.SequenceMatcher(None, q, flat[j:j + n]).ratio()
        if r > best[0]: best = (r, owner[j], owner[j + n - 1])
    return best

def main():
    P = Project(sys.argv[1])
    beats = P.beats()
    cache = {}
    for t in P.cfg['tracks']:
        for k, v in P.track(t)['words'].items():
            if pathlib.Path(v).exists():
                cache[k] = json.load(open(v))['words']
    out, flags = {}, []
    for vid, items in beats.items():
        out[vid] = []
        for b in items:
            if 'card' in b: out[vid].append(b); continue
            words = cache.get(b['src'])
            if words is None: flags.append(f"{vid} {b['id']}: no transcript for {b['src']}"); continue
            lo = next((k for k, w in enumerate(words) if w['s'] >= b.get('after', 0)), 0)
            hi = next((k for k, w in enumerate(words) if w['s'] > b['before']), len(words)) if 'before' in b else None
            r1, i1, _ = find(words, b['from'], lo=lo, hi=hi)
            t_lim = next((k for k, w in enumerate(words) if w['s'] > words[i1]['s'] + 420), len(words)) if i1 is not None else None
            r2, _, j2 = find(words, b['to'], lo=i1 or 0, hi=t_lim)
            q0, qz = norm(b['from'])[0], norm(b['to'])[-1]
            # Snap to the phrase's actual first/last word, searching BOTH directions (nearest first). The fuzzy
            # window can land a word early or late; a backward-only end snap once cut the last word off a sentence.
            if i1 is not None:
                for k in sorted(range(max(0, i1 - 3), min(i1 + 4, len(words))), key=lambda k: abs(k - i1)):
                    if norm(words[k]['w']) and norm(words[k]['w'])[0] == q0:
                        i1 = k; break
            if j2 is not None:                     # and its actual last word
                for k in sorted(range(max(0, j2 - 3), min(j2 + 4, len(words))), key=lambda k: abs(k - j2)):
                    if norm(words[k]['w']) and norm(words[k]['w'])[-1] == qz:
                        j2 = k; break
            rec = dict(b, raw_start=words[i1]['s'] if i1 is not None else None, raw_end=words[j2]['e'] if j2 is not None else None,
                       score_from=round(r1, 2), score_to=round(r2, 2),
                       heard_from=' '.join(w['w'] for w in words[i1:i1 + 10]) if i1 is not None else '',
                       heard_to=' '.join(w['w'] for w in words[max(0, j2 - 9):j2 + 1]) if j2 is not None else '')
            if rec['raw_end'] is None or rec['raw_end'] <= rec['raw_start'] or (
                    not b.get('anchors_verified') and (r1 < .72 or r2 < .72 or norm(rec['heard_from'])[:1] != [q0] or norm(rec['heard_to'])[-1:] != [qz])):
                flags.append(f"{vid} {b['id']}: from {r1:.2f} to {r2:.2f}")
            out[vid].append(rec)
    P.write('beats-mapped.json', out)
    for vid, items in out.items():
        tot = sum((b['raw_end'] - b['raw_start']) for b in items if 'raw_start' in b and b['raw_start'] is not None and b['raw_end'])
        print(f'{vid}: {tot/60:.1f} min of content')
        for b in items:
            if 'card' in b: print(f"   [{b['card']} card]"); continue
            if b.get('raw_start') is None or b.get('raw_end') is None:   # an anchor matched nothing: flagged below, not a crash
                print(f"   {b['id']:>4} NOT FOUND from={b['score_from']} to={b['score_to']}"); continue
            print(f"   {b['id']:>4} {b['raw_start']:8.1f}-{b['raw_end']:8.1f} ({b['raw_end']-b['raw_start']:5.1f}s) from={b['score_from']} to={b['score_to']}")
    print('FLAGS:', flags or 'none')
    if flags:
        sys.exit(2)

if __name__ == "__main__":
    main()
