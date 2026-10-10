"""Transcript diff QA: what my render says vs what the reference master says for the same beats.

Transcribes the rendered file (faster-whisper small.en), builds the expected text from the reference edit's
hand-corrected VTT over each included beat's master span, and diffs the two word sequences.
Reports runs of EXTRA words (leaks) and MISSING words (clipped or dropped),
with the render time of each, ignoring single-word ASR spelling noise.
Usage: python text_diff_qa.py <project> <track> <render.mp4> <beat ids comma-separated | all>
"""
import difflib, json, pathlib, re, subprocess, sys, tempfile
from faster_whisper import WhisperModel

FILLERS = {'uh', 'um', 'umm', 'mm', 'hmm', 'mmhmm', 'mhm', 'ah', 'er', 'oh'}

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yr import Project  # noqa: E402


def norm(t):
    return re.sub(r"[^a-z0-9']", '', t.lower().replace('’', "'"))


def vtt_words(path):
    out = []
    for h, m, s, h2, m2, s2, txt in re.findall(r'(\d\d):(\d\d):(\d\d\.\d+) --> (\d\d):(\d\d):(\d\d\.\d+)\n(.+?)(?:\n\n|\Z)', open(path).read(), re.S):
        a = int(h) * 3600 + int(m) * 60 + float(s); z = int(h2) * 3600 + int(m2) * 60 + float(s2)
        toks = txt.split()
        for i, t in enumerate(toks):
            out.append((norm(t), a + (z - a) * (i + .5) / len(toks), t))   # keep the raw token for canon()
    return [w for w in out if w[0]]


def main():
    P = Project(sys.argv[1]); side, render = sys.argv[2], sys.argv[3]
    tr = P.track(side)
    if not tr['vtt']:
        print('no reference transcript for this track: text diff skipped'); return
    pieces = P.read('pieces.json')[side]
    ids = list(pieces) if sys.argv[4] == 'all' else sys.argv[4].split(',')
    ref = vtt_words(tr['vtt'])
    # Expected text comes from the PLAN's anchor phrases found in the reference's own transcript, never from
    # my beat mapping (a mapping error would otherwise appear on both sides of the diff and hide).
    beats = {b['id']: b for b in P.beats()[side] if 'id' in b}
    from map_beats import norm as canon
    flat, owner = [], []                               # canonical tokens ("read-only" -> read only) + owning ref index
    for i, (_, _, raw) in enumerate(ref):
        for t in canon(raw):
            flat.append(t); owner.append(i)
    import bisect

    def locate(phrase, lo, hi):
        """Best fuzzy match of the anchor phrase between ref indices lo..hi -> (ratio, first ref idx, last ref idx)."""
        q = canon(phrase); n = len(q)
        f0, f1 = bisect.bisect_left(owner, max(0, lo)), bisect.bisect_right(owner, hi)
        best = (0, None, None)
        for j in range(f0, max(f0, min(len(flat) - n, f1)) + 1):
            r = difflib.SequenceMatcher(None, q, flat[j:j + n]).ratio()
            if r > best[0]:
                best = (r, owner[j], owner[min(j + n - 1, len(owner) - 1)])
        return best
    expected, unchecked = [], []
    for bid in ids:
        if bid not in beats or bid not in pieces:
            continue
        b = beats[bid]
        mid = next(i for i, (_, t, _) in enumerate(ref) if t >= pieces[bid]['master_start'])   # search near, not from, my mapping
        r1, j1, _ = locate(b['from'], mid - 60, mid + 60)
        r2, _, jz = locate(b['to'], j1 or 0, (j1 or 0) + 700)
        if min(r1, r2) < 0.6:
            print(f'  beat {bid}: anchor not found in reference text ({r1:.2f}, {r2:.2f}): NOT CHECKED'); unchecked.append(bid); continue
        span = list(range(j1, jz + 1))
        for sa, sz in b.get('skip', []):             # approved removals are not expected in the render
            ra, ka, _ = locate(sa, j1, jz); rz, _, kz = locate(sz, ka or j1, jz)
            if min(ra, rz) >= 0.6:
                span = [k for k in span if not (ka <= k <= kz)]
            else:
                print(f'  beat {bid}: skip {sa!r} not found in reference text ({ra:.2f}, {rz:.2f})')
        expected += [ref[k][2] for k in span]
    from map_beats import norm as canon            # numbers, contractions, hyphens: same normalization as the mapper
    # A reference token ending in "-" is a marked false start ("diff-"): not a word the render must contain.
    exp, src = [], []                                  # canonical tokens + index of the raw reference token each came from
    for k, w in enumerate(expected):
        if w.rstrip('",.?!').endswith('-'):
            continue
        for t in canon(w):
            if t not in FILLERS:
                exp.append(t); src.append(k)
    acc_p = P.plan / 'qa-accepted.json'          # human-verified "not a drop" rulings, so they are checked once, not every run
    accepted = [x for x in (json.load(open(acc_p)) if acc_p.exists() else []) if x['track'] == side]
    model = WhisperModel('small.en', device='cpu', compute_type='int8')
    with tempfile.TemporaryDirectory() as d:
        wav = pathlib.Path(d) / 'a.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', render, '-ac', '1', '-ar', '16000', str(wav)], check=True)
        segs, _ = model.transcribe(str(wav), word_timestamps=True)
        got = [(t, w.start, w.end) for s in segs for w in s.words for t in canon(w.word) if t not in FILLERS]
        a = [t for t, _, _ in got]
        extras, real, resolved = [], [], []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, exp, autojunk=False).get_opcodes():
            if op == 'equal':
                continue
            extra, missing = a[i1:i2], exp[j1:j2]
            if ''.join(extra) == ''.join(missing):
                continue                                  # spacing/compound only ("multi pane" vs "multipane")
            if op == 'replace' and len(extra) == len(missing) == 1:
                continue                                  # one-word respelling (ASR or reference spelling)
            t0 = got[i1 - 1][2] if i1 else 0.0
            t1 = got[i2][1] if i2 < len(got) else t0 + 3
            at = f'{int(t0) // 60}:{int(t0) % 60:02d}'
            if not missing:
                extras.append(f'{at}  heard, not in reference: {" ".join(extra)}'); continue
            # A reference word the render transcript lacks: re-listen to just this window, prompted with the
            # expected words. Found -> ASR miss (resolved). Not found -> a real drop: FAIL.
            before = ' '.join(exp[max(0, j1 - 4):j1])
            acc = next((x for x in accepted if canon(x['words']) == missing and ' '.join(canon(x['after'])) == before), None)
            if acc:
                resolved.append(f'{at}  "{" ".join(missing)}" (accepted: {acc["why"]})'); continue
            ctx = ' '.join(expected[src[max(0, j1 - 8)]:src[min(len(src) - 1, j2 + 8)] + 1])   # the reference's own wording
            seg = pathlib.Path(d) / 'w.wav'
            heard = []
            # plain + prompted over a wide window, then prompted over a tight one: whisper's output varies with window
            # length (one word was heard only in the tight window). Any pass hearing the words resolves them.
            for pad, kw in ((4, {}), (4, {'initial_prompt': ctx}), (1.5, {'initial_prompt': ctx})):
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t0 - pad):.2f}', '-t', f'{t1 - t0 + 2 * pad:.2f}', '-i', str(wav), str(seg)], check=True)
                ws, _ = model.transcribe(str(seg), **kw)
                heard += [t for x in ws for t in canon(x.text)]
                if all(m in heard for m in missing):
                    break
            if all(m in heard for m in missing):
                resolved.append(f'{at}  "{" ".join(missing)}" (ASR miss; present on re-listen)')
            else:
                real.append(f'{at}  after "{before}"  MISSING "{" ".join(missing)}"' + (f' (render has "{" ".join(extra)}")' if extra else '') +
                            f' | re-listen heard: "{" ".join(heard)[:120]}"')
    print(f'{len(a)} words heard, {len(exp)} expected | {len(real)} unresolved drop(s), {len(resolved)} ASR misses resolved, {len(extras)} extra run(s)')
    for tag, rows in (('UNRESOLVED (real drops: fix before handover)', real), ('extra words heard (report only)', extras),
                      ('resolved', resolved)):
        if rows:
            print(f'== {tag}')
            for r in rows:
                print('  ' + r)
    if unchecked:
        print(f'== COVERAGE: beats not checked (fix their anchors): {unchecked}')
    sys.exit(1 if real or unchecked else 0)


if __name__ == '__main__':
    main()
