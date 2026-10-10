"""Render one track of a recut from raw footage per the approved plan (youtube-recut plugin).

Pipeline (all inputs read-only, every output a new versioned file under <project>/renders):
  1. work/beats-mapped.json gives each beat's raw start/end; work/pieces.json gives the raw spans the
     reference edit (e.g. Descript) kept inside it; approved skips (plan/beats.json) are removed.
     Pads and handles extend a cut only through a real gap (safe_extend). Adjacent repeats the
     reference transcript does not have are dropped (drop_repeats).
  2. Each piece is cut with an accurate seek into an exact-length intermediate (H.264 CRF 12 + PCM);
     narrower sources are pillarboxed to 3840x2160; zooms from work/zoom-plan.json; long silences at 4x.
  3. Cards (brand preset): intro where the plan puts it, outro at the end.
  4. Captions: ASR word timings re-based to the output timeline, respelled from the reference
     transcript, missing words restored where the cut audio has speech, burned with libass.
  5. Audio: DeepFilterNet on the joined voice, gained to target LUFS with a transient limiter in a FLOAT
     intermediate (an integer one hard-clips), music bed per brand timing, two-pass linear loudnorm.

Usage: python render_track.py <project> <track> <version> [--only ids] [--proof SECONDS] [--captions-only RENDER]
"""
import json, math, os, pathlib, re, struct, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_captions import build  # noqa: E402
from yr import Project, SKILL, ffmpeg_libass, deepfilter_bin  # noqa: E402
P_FONTS = SKILL / 'assets' / 'fonts'

# Filled by init(project) from project.json; module-level so zoom_plan / QA scripts can reuse pieces_for().
P = ROOT = FF = THEME = None
SIDE, VTT, PRIVACY, CORRECTIONS, BRAND, AUDIO, ZOOM = {}, {}, {}, {}, {}, {}, {}


def init(root):
    global P, ROOT, FF, THEME, SIDE, VTT, PRIVACY, CORRECTIONS, BRAND, AUDIO, ZOOM
    P = Project(root); ROOT = P.root; FF = ffmpeg_libass(); BRAND = P.brand; AUDIO = P.audio
    THEME = BRAND['theme_wav']
    SIDE = {t: P.track(t) for t in P.cfg['tracks']}
    VTT = {t: tr['vtt'] for t, tr in SIDE.items() if tr['vtt']}
    PRIVACY = {t: {'boxes': [(tuple(win), [tuple(bx) for bx in boxes]) for win, boxes in tr['privacy']['boxes']],
                   'name': tr['privacy'].get('name')} for t, tr in SIDE.items() if tr.get('privacy')}
    CORRECTIONS = {t: P.transcripts / tr['corrections'] for t, tr in SIDE.items() if tr.get('corrections')}
    ZOOM = P.read('zoom-plan.json', {})
    return P


DRY = None   # --captions-only <render.mp4>: plan the same cut, rebuild captions against that render's audio, encode nothing


def run(cmd):
    if DRY:
        return
    subprocess.run(cmd, check=True)


def probe(path, entries):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', f'stream={entries}',
                          '-of', 'csv=p=0', path], capture_output=True, text=True, check=True).stdout.strip()
    return out.splitlines()[0].split(',')


def drop_repeats(kept, words, side, bid):
    """Where the reference transcript has one copy of a phrase and the kept raw audio has it twice in a
    row ("that are, that are"), cut the first copy. Exact adjacent repeats only (1-3 words)."""
    vtt = VTT.get(side)
    if not vtt:
        return kept
    lines = [l for l in open(vtt).read().splitlines() if l and '-->' not in l and not l.startswith(('WEBVTT', 'NOTE', 'This file'))]
    refs = ' ' + ' '.join(_norm(t) for l in lines for t in l.split() if _norm(t)) + ' '
    inside = [w for w in words if any(a <= (w['s'] + w['e']) / 2 <= b for a, b in kept)]
    toks = [_norm(w['w']) for w in inside]
    cuts = []
    for n in (3, 2, 1):
        for i in range(len(toks) - 2 * n + 1):
            a, b = toks[i:i + n], toks[i + n:i + 2 * n]
            if a == b and all(a) and (' ' + ' '.join(a + b) + ' ') not in refs:
                cuts.append((inside[i]['s'] - 0.02, inside[i + n]['s'] - 0.02))
    for c0, c1 in cuts:
        nxt = []
        for a, b in kept:
            if c1 <= a or c0 >= b:
                nxt.append([a, b])
            else:
                if c0 > a: nxt.append([a, c0])
                if c1 < b: nxt.append([c1, b])
        kept = nxt
    if cuts:
        print(f'  beat {bid}: removed {len(cuts)} repeat(s): ' + '; '.join(f'{c0:.2f}-{c1:.2f}' for c0, c1 in cuts), flush=True)
    return kept


_PCM = {}
_BEAT_EDGE = set()   # edges pieces_for already extended; main() must not add a handle on top


def safe_extend(path, t, d, amt):
    """Move a cut edge outward (d=-1 earlier, d=+1 later) by up to amt seconds, but only through a gap:
    - if nothing within reach beyond the reference's edge falls 18 dB under the kept side's peak, there is no gap:
      the reference cut mid-sound on purpose (e.g. a removed false start running into the kept word), so do not extend;
    - otherwise stop two frames before the level rises 6 dB off its running minimum (the next or previous word).
    Fixed pads once pushed a cold open into the words on both sides of it."""
    IN = 0.3                                            # kept-side context for the speech reference level
    a = t - amt - 0.05 if d < 0 else t - IN
    key = (path, round(a, 3), round(amt, 3), d)
    if key not in _PCM:
        o = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0.0, a):.3f}', '-i', path, '-map', '0:a:0',
                            '-t', f'{amt + IN + 0.05:.3f}', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
        _PCM[key] = [20 * math.log10(math.sqrt(sum(v * v for v in fr) / len(fr)) / 32768 + 1e-9)
                     for fr in (struct.unpack('<160h', o[i:i + 320]) for i in range(0, len(o) - 319, 320))]
    lv = _PCM[key]
    edge = round((t - max(0.0, a)) / 0.01)             # frame index of the edge inside the read window
    n = round(amt / 0.01)
    kept = lv[edge:edge + round(IN / 0.01)] if d < 0 else lv[max(0, edge - round(IN / 0.01)):edge]
    out_frames = [lv[edge - 1 - i] for i in range(n) if 0 <= edge - 1 - i < len(lv)] if d < 0 else \
                 [lv[edge + i] for i in range(n) if edge + i < len(lv)]
    if not kept or not out_frames or min(out_frames) > max(kept) - 18:   # no real gap in reach: continuous sound
        return t
    low = out_frames[0]
    for i, L in enumerate(out_frames):     # a word boundary is a dip, not always silence: stop where sound rises off it
        low = min(low, L)
        if L >= low + 6 and L >= -50:
            return t + d * max(0.0, (i - 2) * 0.01)
    return t + d * amt


def beat_start(path, t, reach=0.35):
    """Where a beat's first word really starts. ASR word times land inside consonants: "Today" was timed after its
    "T" burst, so the cut played "-day". Walking back from the ASR time:
    - a SHORT sound (<= 60 ms) with silence before it is the word's own onset (a plosive burst): include it and cut
      at the silence;
    - a LONGER sound is a separate syllable (a removed "uh", the previous word): cut at the dip nearest the word,
      which is where the reference edit cuts (an "uh" before "Okay")."""
    a = max(0.0, t - reach)
    o = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a:.3f}', '-i', path, '-map', '0:a:0', '-t', f'{t - a + 0.03:.3f}',
                        '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
    lv = [20 * math.log10(math.sqrt(sum(v * v for v in fr) / len(fr)) / 32768 + 1e-9)
          for fr in (struct.unpack('<160h', o[i:i + 320]) for i in range(0, len(o) - 319, 320))]
    k = min(len(lv) - 1, round((t - a) / 0.01))
    if k < 4:
        return t
    floor = min(lv[:k + 1]); quiet = floor + 8
    i = k
    while i >= 0 and lv[i] > quiet:                 # the non-silent run the ASR time sits in
        i -= 1
    run = k - i
    if run <= 6 and i >= 2 and lv[i] <= quiet and lv[i - 1] <= quiet and lv[i - 2] <= quiet:
        return a + (i + 1) * 0.01                   # short onset burst with silence before it: start at the silence
    # Otherwise the word runs straight on from another sound. Cut where the level first drops >= 5 dB below the
    # preceding 30 ms (the previous sound ending), nearest the ASR time and allowed up to 120 ms AFTER it: in
    # "right now 98", ASR put the boundary inside "now", so cutting there played "-ow 98".
    o2 = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-map', '0:a:0', '-t', '0.13',
                         '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
    lv = lv[:k + 1] + [20 * math.log10(math.sqrt(sum(v * v for v in fr) / len(fr)) / 32768 + 1e-9)
                       for fr in (struct.unpack('<160h', o2[i:i + 320]) for i in range(320, len(o2) - 319, 320))]
    cands = [n for n in range(max(3, k - 12), len(lv)) if lv[n] <= min(lv[n - 3:n]) - 5]
    if cands:
        j = min(cands, key=lambda n: abs(n - k))
        return a + j * 0.01
    lo = max(0, k - 12)
    j = min(range(lo, k + 1), key=lambda n: lv[n])
    return a + (j + 1) * 0.01


def pieces_for(beat, words, side):
    """Raw pieces for a beat = the reference edit's kept spans (work/pieces.json) minus any approved skips.
    Returns (start, end, words-inside) per piece."""
    from map_beats import find
    rec = P.read('pieces.json')[side][beat['id']]
    kept, mcum = rec['pieces'], rec['master_start']
    mstart = []
    for a, z in kept:
        mstart.append(mcum); mcum += z - a
    skips = []
    lo = next((k for k, w in enumerate(words) if w['s'] >= beat['raw_start'] - 1), 0)
    hi = next((k for k, w in enumerate(words) if w['s'] > beat['raw_end'] + 1), len(words))
    for a, z in beat.get('skip', []):
        r1, i1, _ = find(words, a, lo=lo, hi=hi); r2, _, j2 = find(words, z, lo=i1 or lo, hi=hi)
        if min(r1, r2) < 0.7:
            sys.exit(f"skip anchor not found in beat {beat['id']}: {a!r} / {z!r} ({r1:.2f}, {r2:.2f})")
        skips.append((words[i1]['s'] - 0.05, words[j2]['e'] + 0.1))
    out = []
    kept = [list(k) for k in kept]
    orig = [(a, b, m0) for (a, b), m0 in zip(kept, mstart)]
    kept = drop_repeats(kept, words, side, beat['id'])
    mstart = [next(m0 + (a - oa) for oa, ob, m0 in orig if oa - 1e-6 <= a <= ob) for a, b in kept]
    src_path = P.sources[beat['src']]
    s0 = kept[0][0]
    # beat edges: lead/tail pad and the editor's handle as ONE silence-bounded extension (two chained calls let
    # the handle slip past where the pad had correctly stopped, into a removed "so,")
    # Beat edges snap to the silence around the first/last word, bounded by the neighboring words' ASR times so a
    # removed word next door can never be pulled back in.
    prev_end = max([w['e'] for w in words if w['e'] <= s0 + 0.02] or [0.0])
    e0 = kept[-1][1]
    next_start = min([w['s'] for w in words if w['s'] >= e0 - 0.02] or [e0 + 1.0])
    fixed = (json.load(open(P.plan / 'beat-starts.json')).get(side, {}) if (P.plan / 'beat-starts.json').exists() else {}).get(beat['id'])
    # plan/beat-starts.json: per-beat start cut points decided from the waveform (they win over any heuristic)
    kept[0][0] = fixed[0] if fixed else max(beat_start(src_path, s0), prev_end)
    mstart[0] -= s0 - kept[0][0]
    kept[-1][1] = safe_extend(src_path, e0, 1, 0.18 + HANDLE_OUT)       # ends: the proven rule (0 leaks)
    _BEAT_EDGE.update({(src_path, round(kept[0][0], 3)), (src_path, round(kept[-1][1], 3))})
    for (s, e), m0 in zip(kept, mstart):
        segs = [(s, e)]
        for a, z in skips:
            nxt = []
            for x, y in segs:
                if z <= x or a >= y:
                    nxt.append((x, y))
                else:
                    if a > x: nxt.append((x, a))
                    if z < y: nxt.append((z, y))
            segs = nxt
        for x, y in segs:
            if y - x > 0.12:
                ws = [w for w in words if x <= (w['s'] + w['e']) / 2 <= y]
                out.append((x, y, ws, m0 + (x - s)))
    return out




def _norm(t):
    import re
    return re.sub(r"[^a-z0-9']", '', t.lower().replace('’', "'"))


_AUD = {}
_CONTRACT = {('going to', 'gonna'), ('want to', 'wanna'), ('got to', 'gotta'), ('kind of', 'kinda'), ('sort of', 'sorta')}


def _speech_span(audio, a, z):
    """(start, end) of speech-level sound in the cut voice between output times a and z, or None.
    Speech-level = within 20 dB of the loudest 10 ms frame in the 2 s around the gap."""
    import numpy as np
    if not audio or z - a < 0.08:
        return None
    if audio not in _AUD:
        o = subprocess.run([FF, '-v', 'error', '-i', audio, '-map', '0:a', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
        x = np.frombuffer(o, np.int16).astype(float) / 32768
        n = len(x) // 160
        _AUD[audio] = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) + 1e-9)
    lv = _AUD[audio]
    fa, fz = int(a * 100), int(z * 100)
    ctx = lv[max(0, fa - 100):fz + 100]
    if not len(ctx) or fz <= fa:
        return None
    hot = np.flatnonzero(lv[fa:fz] > ctx.max() - 20)
    return (a + hot[0] / 100, a + (hot[-1] + 1) / 100) if len(hot) else None


def _canon(t):
    from map_beats import norm
    return norm(t)


def _across_cut(out, k1, k2):
    """True if any adjacent caption words between indices k1..k2 straddle a cut: master time jumps more than output
    time. Restoring reference words there would caption audio we removed."""
    for k in range(max(1, k1), min(k2, len(out) - 1) + 1):
        a, b = out[k - 1], out[k]
        if (b['m'] - (a['m'] + (a['e'] - a['s']))) - (b['s'] - a['e']) > 0.4:
            return True
    return False


def fix_words(ws, cfg):
    """Join ASR hyphen fragments; take hand-corrected reference spelling where the master captions exist;
    replace the private name in captions."""
    import re, difflib
    out = []
    for w in ws:
        if out and w['w'].startswith('-'):
            out[-1] = dict(out[-1], w=out[-1]['w'] + w['w'], e=w['e']); continue
        out.append(dict(w))
    vtt = VTT.get(cfg['side'])
    if vtt:
        cues = re.findall(r'(\d\d):(\d\d):(\d\d\.\d+) --> (\d\d):(\d\d):(\d\d\.\d+)\n(.+?)(?:\n\n|\Z)', open(vtt).read(), re.S)
        ref = []
        for h, m, sec, h2, m2, s2, txt in cues:
            a = int(h) * 3600 + int(m) * 60 + float(sec); z = int(h2) * 3600 + int(m2) * 60 + float(s2)
            toks = txt.split()
            for i, tk in enumerate(toks):
                tk = tk.strip('"')                 # keep a false start's hyphen ("audit-") so it reads as one, not a typo
                if tk:
                    ref.append((tk, a + (z - a) * i / max(1, len(toks))))
        i = 0
        while i < len(out):                 # align runs of words that are contiguous in master time
            j = i + 1
            while j < len(out) and 0 <= out[j]['m'] - out[j - 1]['m'] < 3:   # a backwards jump (reordered beat) starts a new run
                j += 1
            lo, hi = out[i]['m'] - 1.5, out[j - 1]['m'] + 1.5
            rr = [r for r in ref if lo <= r[1] <= hi]
            a_t = [_norm(x['w']) for x in out[i:j]]; b_t = [_norm(r[0]) for r in rr]
            if os.environ.get('CAPDEBUG') and any(x in a_t for x in os.environ['CAPDEBUG'].lower().split(',')):   # CAPDEBUG=word,word
                print('RUN', out[i]['m'], out[j - 1]['m'], '\n  ASR:', ' '.join(a_t), '\n  REF:', ' '.join(b_t))
            inserts = []
            for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, a_t, b_t, autojunk=False).get_opcodes():
                if op == 'replace' and any(ch.isdigit() for x in out[i + a1:i + a2] for ch in x['w']) and \
                        ''.join(t for x in out[i + a1:i + a2] for t in _canon(x['w'])) == ''.join(t for q in range(b1, b2) for t in _canon(rr[q][0])):
                    continue                        # same number, ASR has digits: keep "98 out of 120", not a mix of digits and words
                if op == 'equal' or (op == 'replace' and a2 - a1 == b2 - b1):
                    for k in range(a2 - a1):
                        out[i + a1 + k]['w'] = rr[b1 + k][0]
                elif op == 'replace' and any((a_t[k] + ' ' + a_t[k + 1], b_t[q]) in _CONTRACT for k in range(a1, a2 - 1) for q in range(b1, b2)):
                    # ASR "going to" where the reference (and the speaker) say "gonna": merge the pair into one caption word
                    nb, k = b1, a1
                    while k < a2:
                        q = next((q for q in range(nb, b2) if k + 1 < a2 and (a_t[k] + ' ' + a_t[k + 1], b_t[q]) in _CONTRACT), None)
                        if q is not None:
                            out[i + k]['w'] = rr[q][0]; out[i + k]['e'] = out[i + k + 1]['e']; out[i + k + 1]['drop'] = True
                            nb = q + 1; k += 2
                        else:
                            k += 1
                elif op == 'replace' and a2 - a1 > b2 - b1 and any(
                        ''.join(a_t[k:k + n]) == b_t[q] for q in range(b1, b2) for k in range(a1, a2) for n in (2, 3)):
                    # ASR split one written token into fragments ("77" ".5" "%" for "77.5%"): merge them into it.
                    # Pairing alone captioned "77.5% .5 % C.".
                    k, q = a1, b1
                    while k < a2 and q < b2:
                        n = next((n for n in (3, 2, 1) if ''.join(a_t[k:k + n]) == b_t[q]), None)
                        if n is None:
                            k += 1; continue
                        out[i + k]['w'] = rr[q][0]; out[i + k]['e'] = out[i + k + n - 1]['e']
                        for z in range(1, n):
                            out[i + k + z]['drop'] = True
                        k += n; q += 1
                elif op == 'replace' and a2 - a1 <= 6 and b2 - b1 <= 6 and not _across_cut(out, i + a1, i + a2) and not any(
                        difflib.SequenceMatcher(None, a_t[k], b_t[q]).ratio() >= 0.6 for k in range(a1, a2) for q in range(b1, b2)):
                    # A small local block where no word pairs up (an ASR garble of a short sentence): the reference is
                    # hand-corrected, so its words replace the ASR's across the same span, timed in proportion to their length.
                    t0, t1 = out[i + a1]['s'], out[i + a2 - 1]['e']
                    toks_ = [rr[q][0] for q in range(b1, b2)]
                    wts = [max(1, len(x)) for x in toks_]; tot = sum(wts); acc = t0
                    for k in range(a1, a2):
                        out[i + k]['drop'] = True
                    for x, wt in zip(toks_, wts):
                        d = (t1 - t0) * wt / tot
                        inserts.append((i + a1, [x], (acc, acc + d)) ); acc += d
                elif op == 'replace':
                    # unequal block ("codecs read-only" vs "Codex Read only"): pair each ASR word, in order, with
                    # its closest reference spelling. Skipping these blocks once left one misspelling in 22 captions.
                    nb = b1
                    for k in range(a1, a2):
                        best = max(range(nb, b2), key=lambda q: difflib.SequenceMatcher(None, a_t[k], b_t[q]).ratio(), default=None)
                        if best is not None and difflib.SequenceMatcher(None, a_t[k], b_t[best]).ratio() >= 0.6:
                            out[i + k]['w'] = rr[best][0]; nb = best + 1
                elif op == 'insert' and 0 < a1 < j - i and b2 - b1 <= 3 and not _across_cut(out, i + a1, i + a1):
                    inserts.append((i + a1, [rr[q][0] for q in range(b1, b2)]))
            for ins in reversed(inserts):
                if len(ins) == 3:                   # local-block rewrite: reference words over a known span
                    pos, toks, (a_, z_) = ins
                    out[pos:pos] = [dict(out[pos], w=toks[0], s=a_, e=z_, inserted=True, drop=False)]; j += 1
                    continue
                pos, toks = ins                     # a reference word the ASR missed: add it only if the cut audio has speech there
                span = _speech_span(cfg.get('_audio'), out[pos - 1]['e'], out[pos]['s'])
                if span and (span[1] - span[0]) >= 0.08 * len(toks):
                    d = (span[1] - span[0]) / len(toks)
                    new = [dict(out[pos - 1], w=tk, s=span[0] + q * d, e=span[0] + (q + 1) * d, m=out[pos - 1]['m'], inserted=True)
                           for q, tk in enumerate(toks)]
                    out[pos:pos] = new; j += len(new)
            i = j
    out = [w for w in out if not w.get('drop')]
    name = PRIVACY.get(cfg['side'], {}).get('name')
    if name:
        for k, w in enumerate(out):
            if _norm(w['w']).startswith(name):
                prev = _norm(out[k - 1]['w']) if k else ''
                tail = re.sub(r'(?i)^' + name, '', w['w'])
                out[k]['w'] = ('there' if prev in ('hi', 'hey') else 'them') + tail
                out[k]['private'] = True
    return out


def privacy(cfg, spans, cap_words):
    """drawbox masks for output spans whose master time falls in a private window, and audio mutes on the
    private name. Returns (video filter prefix, audio filter suffix)."""
    pv = PRIVACY.get(cfg['side'])
    if not pv:
        return '', ''
    vf = []
    for (m_lo, m_hi), boxes in pv['boxes']:
        for o0, o1, m in spans:
            a = max(o0, o0 + (m_lo - m)); z = min(o1, o0 + (m_hi - m))
            if z > a:
                for x, y, w, h in boxes:
                    vf.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black:t=fill:enable='between(t,{a:.3f},{z:.3f})'")
    mutes = ''.join(f",volume=0:enable='between(t,{w['s'] - 0.06:.3f},{w['e'] + 0.06:.3f})'" for w in cap_words if w.get('private'))
    return (','.join(vf) + ',') if vf else '', mutes





def apply_corrections(ws, cfg):
    """Proofread fixes keyed by the word's exact raw start time; every key inside the cut must be hit."""
    path = CORRECTIONS.get(cfg['side'])
    if not path:
        return ws
    fixes = {round(c['raw_s'], 2): c for c in json.load(open(path))['corrections']}
    hit, out, skip = set(), [], 0
    for k, w in enumerate(ws):
        if skip:
            skip -= 1; continue
        c = fixes.get(round(w.get('r', -1), 2))
        if c:
            hit.add(round(c['raw_s'], 2))
            if c['correct'] == '':
                continue                            # a captioned word that is not in the cut audio: remove it
            n = c.get('merge_next', 0)
            end = ws[min(k + n, len(ws) - 1)]['e']
            tail = re.sub(r"^[A-Za-z'-]+", '', ws[min(k + n, len(ws) - 1)]['w'])
            out.append(dict(w, w=c['correct'] + tail, e=end)); skip = n; continue
        out.append(w)
    kept_raw = {round(w.get('r', -1), 2) for w in ws}
    missed = [k for k in fixes if k in kept_raw and k not in hit]
    if missed:
        sys.exit(f'corrections not applied: {missed}')
    return out


_UNITS = {w: i for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split())}
_TENS = {w: 10 * i for i, w in enumerate('x x twenty thirty forty fifty sixty seventy eighty ninety'.split()) if w != 'x'}


def number_pass(ws):
    """Captions show numbers one way: digits. Spelled multi-word numbers ("one hundred and two", "eighty-five") become
    102 / 85, "percent" after a number becomes %, split decimals ("54" ".41") join, "9:00 AM" becomes "9 AM".
    Single number words ("one more run", "a hundred") stay words. (A caption once read "98 out of one hundred and twenty".)"""
    out, i = [], 0
    def core(w):
        m = re.match(r"^([A-Za-z-]+)([.,!?;:]*)$", w)
        return (m.group(1).lower(), m.group(2)) if m else (None, '')
    while i < len(ws):
        w = ws[i]['w']
        if out and re.match(r"^\.\d+[.,!?;:%]*$", w) and re.match(r"^\d+$", out[-1]['w']):
            out[-1] = dict(out[-1], w=out[-1]['w'] + w, e=ws[i]['e']); i += 1; continue
        w2 = re.sub(r"^(\d{1,2}):00\b", r"\1", w)
        # try to read a spelled number starting here
        j, total, cur, used, words_used, tail = i, 0, 0, False, 0, ''
        while j < len(ws):
            c, t = core(ws[j]['w'])
            if c is None:
                break
            parts = c.split('-')
            if all(x in _UNITS or x in _TENS for x in parts) and len(parts) <= 2:
                cur += sum(_TENS.get(x, _UNITS.get(x, 0)) for x in parts); used = True
            elif c == 'hundred' and used:
                cur = (cur or 1) * 100
            elif c == 'and' and used and j + 1 < len(ws) and (core(ws[j + 1]['w'])[0] or '').split('-')[0] in {**_UNITS, **_TENS}:
                pass
            else:
                break
            words_used += 1; tail = t; j += 1
            if t:
                break
        multi = words_used >= 2 or (words_used == 1 and '-' in (core(ws[i]['w'])[0] or ''))
        if used and multi:
            txt = str(cur + total)
            nxt = core(ws[j]['w'])[0] if j < len(ws) else None
            if not tail and nxt == 'percent':
                txt += '%' + core(ws[j]['w'])[1]; j += 1
            else:
                txt += tail
            out.append(dict(ws[i], w=txt, e=ws[j - 1]['e'])); i = j; continue
        if re.match(r"^\d+(\.\d+)?$", w) and i + 1 < len(ws) and core(ws[i + 1]['w'])[0] == 'percent':
            out.append(dict(ws[i], w=w + '%' + core(ws[i + 1]['w'])[1], e=ws[i + 1]['e'])); i += 2; continue
        out.append(dict(ws[i], w=w2)); i += 1
    return out


def caption_fixes(ws):
    """Whole-word replacements from plan/caption-fixes.json ({"Vois": "Voice", ...}), keeping trailing punctuation.
    The reference transcript's typos otherwise reach the screen, because captions take its spelling."""
    p = P.plan / 'caption-fixes.json'
    if not p.exists():
        return ws
    fixes = {k.lower(): v for k, v in json.load(open(p)).items() if not k.startswith('_')}
    out = []
    for w in ws:
        m = re.match(r"^(.*?)([.,!?;:\"]*)$", w['w'])
        core, tail = m.group(1), m.group(2)
        out.append(dict(w, w=fixes[core.lower()] + tail) if core.lower() in fixes else w)
    return out


SLOW_GAP, FAST = 3.0, 4


def cut_piece(path, w, src, zkey_s, a, b, speed, rate, out, side):
    """Cut raw [a, b] at `speed` into an exact-length piece (silent when sped up). Returns its duration."""
    fr = eval(rate)
    n = max(1, round((b - a) / speed * fr)); L = n / fr
    pre = min(1.0, a)
    pad = '' if w == 3840 else f',pad=3840:2160:{(3840 - w) // 2}:0:black'
    zbox = ZOOM.get(side, {}).get(f'{src}|{zkey_s:.3f}')
    if zbox:
        zx, zy, zw, zh = zbox
        pad += f',crop={zw}:{zh}:{zx}:{zy},scale=3840:2160:flags=lanczos'
    vchain = (f"[0:v:0]trim=start={pre:.3f},setpts=(PTS-STARTPTS)/{speed},fps={rate},trim=end_frame={n},format=yuv420p{pad}[v]")
    achain = ("anullsrc=r=48000:cl=stereo" if speed != 1 else
              f"[0:a:0]atrim=start={pre:.3f},asetpts=PTS-STARTPTS,aresample=48000")
    achain += f",atrim=duration={L:.6f},apad=whole_dur={L:.6f},afade=t=in:d={FADE},afade=t=out:st={max(0, L - FADE):.6f}:d={FADE}[a]"
    run([FF, '-v', 'error', '-ss', f'{a - pre:.3f}', '-i', path, '-filter_complex', vchain + ';' + achain,
         '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '12', '-preset', 'veryfast', '-c:a', 'pcm_s16le', '-ac', '2', str(out)])
    return L


HANDLE_IN, HANDLE_OUT, FADE = 0.04, 0.03, 0.02



def main():
    init(sys.argv[1])
    side, version = sys.argv[2], sys.argv[3]
    proof = float(sys.argv[sys.argv.index('--proof') + 1]) if '--proof' in sys.argv else None
    cfg = dict(SIDE[side], side=side)
    mapped = P.read('beats-mapped.json')[side]
    spec = {b['id']: b for b in P.beats()[side] if 'id' in b}
    for b in mapped:
        if 'id' in b and spec.get(b['id'], {}).get('skip'):
            b['skip'] = spec[b['id']]['skip']
    if '--only' in sys.argv:
        keep = sys.argv[sys.argv.index('--only') + 1].split(',')
        mapped = [b for b in mapped if b.get('id') in keep or b.get('card') in keep]
    sources = P.sources
    words = {k: json.load(open(v))['words'] for k, v in cfg['words'].items()}
    # File names use the viewer-facing label ("track2"), never the internal key ("side2").
    label = f"track{cfg['n']}"
    out = ROOT / 'renders' / f"{label}-{'proof-' if (proof or '--only' in sys.argv) else ''}{version}.mp4"
    global DRY
    if '--captions-only' in sys.argv:
        DRY = sys.argv[sys.argv.index('--captions-only') + 1]
        out = ROOT / 'renders' / f'{label}-captest-{version}.mp4'   # only its .ass is written
    out.parent.mkdir(exist_ok=True)
    if out.exists() or out.with_suffix('.ass').exists():
        sys.exit(f'Refusing to overwrite {out} or its .ass')

    first_src = sources[next(b['src'] for b in mapped if 'src' in b)]
    rate = probe(first_src, 'r_frame_rate')[0]

    with tempfile.TemporaryDirectory(dir=ROOT) as tmpd:
        tmp = pathlib.Path(tmpd)
        # 1-2. cut pieces; collect caption words on the output timeline
        parts, cap_words, t, card_at, plan, spans, beat_at = [], [], 0.0, None, [], [], {}
        for b in mapped:
            if 'card' in b:
                plan.append(('card', b['card'])); continue
            for s, e, ws, m in pieces_for(b, words[b['src']], side):
                plan.append(('piece', b['src'], s, e, ws, m, b['id']))
        idx = 0
        for item in plan:
            if proof and t >= proof:
                break
            if item[0] == 'card':
                kind = item[1]
                card = P.cards / f"{kind}-{side}.mp4"
                if DRY and not card.exists():
                    die_dry = f'captions-only needs the rendered card {card}'; sys.exit(die_dry)
                if not card.exists():
                    subprocess.run([sys.executable, str(HERE / 'render_card.py'), str(ROOT), side, kind, str(card)], check=True)
                p = tmp / f'{idx:04d}.mkv'
                cdur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(card)],
                                            capture_output=True, text=True).stdout)
                fr = eval(rate.replace('/', '/'))  # frames per second as float
                n = round(cdur * fr); L = n / fr
                asrc = ('anullsrc=r=48000:cl=stereo[s];[s]' if kind == 'intro' else '[0:a]')
                run([FF, '-v', 'error', '-i', str(card), '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-filter_complex',
                     f"[0:v]fps={rate},trim=end_frame={n},setpts=PTS-STARTPTS,format=yuv420p[v];"
                     f"{'[1:a]' if kind == 'intro' else '[0:a]'}aresample=48000,apad,atrim=duration={L:.6f},asetpts=PTS-STARTPTS"
                     f"{',afade=t=in:d=0.35,volume=-3dB' if kind == 'outro' else ''}[a]",
                     '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '12', '-preset', 'veryfast',
                     '-c:a', 'pcm_s16le', '-ac', '2', str(p)])
                if kind == 'intro':
                    card_at = t
                t += L
                parts.append(p); idx += 1
                continue
            _, src, s, e, ws, m, bid = item
            beat_at.setdefault(bid, t)
            zkey = s                                  # zoom plan is keyed by the un-padded piece start
            path = sources[src]
            s2 = s if (path, round(s, 3)) in _BEAT_EDGE else safe_extend(path, s, -1, min(HANDLE_IN, s))  # handles, through gaps only
            e2 = e if (path, round(e, 3)) in _BEAT_EDGE else safe_extend(path, e, 1, HANDLE_OUT)
            s, e, m = s2, e2, m - (s - s2)
            w, h = map(int, probe(path, 'width,height'))
            fr = eval(rate)
            private = PRIVACY.get(side) and any(m < hi and m + (e - s) > lo for (lo, hi), _ in PRIVACY[side]['boxes'])
            subs, cur = [], s                      # (start, end, speed) sub-segments on the raw timeline
            for a_w, b_w in zip(ws, ws[1:]):
                ga, gb = a_w['e'] + 0.35, b_w['s'] - 0.35
                if not private and gb - ga > SLOW_GAP:
                    subs.append((cur, ga, 1)); subs.append((ga, gb, FAST)); cur = gb
            subs.append((cur, e, 1))
            if len(subs) > 1:
                t_before = t
                for k, (a2, b2, sp) in enumerate(subs):
                    L2 = cut_piece(path, w, src, zkey, a2, b2, sp, rate, tmp / f'{idx:04d}.mkv', side)
                    for x in ws:
                        if a2 <= x['s'] < b2 and sp == 1:
                            cap_words.append({'w': x['w'], 's': t + (x['s'] - a2), 'e': t + (x['e'] - a2), 'm': m + (x['s'] - s), 'r': x['s']})
                    spans.append((t, t + L2, m + (a2 - s)))
                    parts.append(tmp / f'{idx:04d}.mkv'); t += L2; idx += 1
                continue
            n = max(1, round((e - s) * fr)); L = n / fr
            pre = min(1.0, s)             # seek a little early, then trim both streams from the same instant
            pad = '' if w == 3840 else f',pad=3840:2160:{(3840 - w) // 2}:0:black'
            zbox = ZOOM.get(side, {}).get(f'{src}|{zkey:.3f}')
            if zbox:
                zx, zy, zw, zh = zbox
                pad += f',crop={zw}:{zh}:{zx}:{zy},scale=3840:2160:flags=lanczos'
            p = tmp / f'{idx:04d}.mkv'
            run([FF, '-v', 'error', '-ss', f'{s - pre:.3f}', '-i', path, '-filter_complex',
                 f"[0:v:0]fps={rate},trim=start={pre:.3f}:end_frame={n + round(pre * fr) + 2},setpts=PTS-STARTPTS,trim=end_frame={n},format=yuv420p{pad}[v];"
                 f"[0:a:0]atrim=start={pre:.3f},asetpts=PTS-STARTPTS,aresample=48000,atrim=duration={L:.6f},apad=whole_dur={L:.6f},"
                 f"afade=t=in:d={FADE},afade=t=out:st={max(0, L - FADE):.6f}:d={FADE}[a]",
                 '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '12', '-preset', 'veryfast',
                 '-c:a', 'pcm_s16le', '-ac', '2', str(p)])
            dur = L
            for x in ws:
                cap_words.append({'w': x['w'], 's': t + (x['s'] - s), 'e': t + (x['e'] - s), 'm': m + (x['s'] - s), 'r': x['s']})
            spans.append((t, t + dur, m))       # output start/end and master time at output start
            t += dur; parts.append(p); idx += 1

        # 3. concat
        lst = tmp / 'list.txt'
        lst.write_text(''.join(f"file '{p}'\n" for p in parts))
        joined = tmp / 'joined.mkv'
        run([FF, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(joined)])

        # 4. captions (+ coming-up line)
        cfg['_audio'] = DRY or str(joined)                # the cut voice: lets fix_words confirm a missing word is audible
        cap_words = fix_words(cap_words, cfg)
        cap_words = apply_corrections(cap_words, cfg)
        cap_words = caption_fixes(cap_words)       # plan/caption-fixes.json: the reference transcript's own typos
        cap_words = number_pass(cap_words)
        ass = build(cap_words, BRAND['caption'])
        if cfg['coming_up'] and cfg.get('promise') in beat_at:
            cu_s = beat_at[cfg['promise']] + 3.0
            ass = ass.replace('[Events]', f"Style: Next,{BRAND['caption']['font']},84,{BRAND['caption']['text']},{BRAND['caption']['text']},&H000F0E0E&,&H260F0E0E&,-1,0,0,0,100,100,0,0,3,26,0,2,120,120,300,1\n\n[Events]")
            def ts(v):
                return f'{int(v // 3600)}:{int(v % 3600 // 60):02d}:{v % 60:05.2f}'
            ass += f"Dialogue: 1,{ts(cu_s)},{ts(cu_s + 4)},Next,,0,0,0,,{{\\fad(250,250)}}{{\\c{BRAND['caption']['active']}}}COMING UP  {{\\c{BRAND['caption']['text']}}}{cfg['coming_up'].split(': ', 1)[1]}\n"
        ass_path = tmp / 'captions.ass'
        ass_path.write_text(ass)
        ass_keep = out.with_suffix('.ass')
        if ass_keep.exists():
            sys.exit(f'Refusing to overwrite {ass_keep}')
        ass_keep.write_text(ass)
        # Beat start times on the OUTPUT timeline: chapters and descriptions are built from this, never estimated.
        json.dump({'track': side, 'duration_s': round(t, 3), 'card_at': card_at, 'beats': {k: round(v, 3) for k, v in beat_at.items()}},
                  open(out.with_suffix('.beats.json'), 'w'), indent=1)
        if DRY:
            print('CAPTIONS', ass_keep, f'{t:.1f}s', f"{sum(1 for w in cap_words if w.get('inserted'))} word(s) inserted")
            return

        # 5. music (default handoff: theme at full level from the card start, duck -20 dB over 4.5-5.3 s,
        #    fade out 22.8-24.8 s) + final encode
        c = card_at
        if c is not None:
            mu = BRAND['music']            # duck_start, duck_end, duck_db, fade_start, fade_end (s after card start)
            d0, d1, ddb, f0, f1 = mu['duck_start'], mu['duck_end'], mu['duck_db'], mu['fade_start'], mu['fade_end']
            vol = f"if(lt(t,{c + d0}),1,if(lt(t,{c + d1}),pow(10,({ddb}*(t-{c + d0})/{d1 - d0})/20),{10 ** (ddb / 20):.4f}))"
            bed = (f"[1:a]aresample=48000,adelay={int(c * 1000)}|{int(c * 1000)},atrim=end={c + f1},volume='{vol}':eval=frame,"
                   f"afade=t=out:st={c + f0}:d={f1 - f0},apad[m];")
            mix = "[a0][m]amix=inputs=2:duration=first:normalize=0[a]"
        else:
            bed, mix = '', '[a0]anull[a]'
        masks, mutes = privacy(cfg, spans, cap_words)
        voice_wav = tmp / 'voice.wav'
        run([FF, '-v', 'error', '-i', str(joined), '-map', '0:a', '-ar', '48000', '-ac', '1', str(voice_wav)])
        run([deepfilter_bin(), '--atten-lim', str(AUDIO['denoise_atten_db']), '-o', str(tmp / 'df'), str(voice_wav)])
        clean = next((tmp / 'df').glob('*.wav'))
        vm = subprocess.run([FF, '-hide_banner', '-nostats', '-i', str(clean), '-af', 'ebur128', '-f', 'null', '-'],
                            capture_output=True, text=True).stderr
        voice_i = float([l for l in vm.splitlines() if l.strip().startswith('I:')][-1].split()[1])
        # voice at -14 LUFS; theme (mastered -14) at -20 dB sits 20 dB under. The raw voice needs ~+13 dB, which puts its
        # peaks ~+3 dBFS: a float intermediate plus a transient limiter at -2 dBFS, never an integer file that hard-clips
        # (an integer intermediate clipped ~11 times a second and sounded blown out).
        mutes = f",volume={AUDIO['target_lufs'] - voice_i:.2f}dB,alimiter=limit={10 ** (AUDIO['limit_dbfs'] / 20):.4f}:attack=5:release=80:level=0" + mutes
        fc = (f"[0:v]{masks}subtitles={ass_path}:fontsdir={P_FONTS}[v];" + bed +
              f"[0:a]aresample=48000{mutes}[a0];" + mix)
        run([FF, '-v', 'error', '-i', str(joined), '-i', THEME, '-i', str(clean), '-filter_complex', fc.replace('[0:a]aresample=48000', '[2:a]aresample=48000,pan=stereo|c0=c0|c1=c0'), '-map', '[v]', '-map', '[a]',
             '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-profile:v', 'high', '-r', rate,
             '-c:a', 'pcm_f32le', '-ar', '48000', '-ac', '2', str(tmp / 'pre.mov')])
        m1 = subprocess.run([FF, '-hide_banner', '-nostats', '-i', str(tmp / 'pre.mov'), '-af',
                             f"loudnorm=I={AUDIO['target_lufs']}:TP={AUDIO['true_peak']}:LRA=11:print_format=json", '-f', 'null', '-'], capture_output=True, text=True).stderr
        js = json.loads(m1[m1.rindex('{'):m1.rindex('}') + 1])
        ln = (f"loudnorm=I={AUDIO['target_lufs']}:TP={AUDIO['true_peak']}:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
              f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
        run([FF, '-v', 'error', '-i', str(tmp / 'pre.mov'), '-map', '0:v', '-map', '0:a', '-c:v', 'copy', '-af', ln + ',aresample=48000',
             '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', str(out)])
        integ = js['input_i']
        vd = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', str(out)], capture_output=True, text=True).stdout)
        ad = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', str(out)], capture_output=True, text=True).stdout)
        if abs(vd - ad) > 1 / eval(rate) + 0.03:
            sys.exit(f'A/V length mismatch: video {vd:.3f}s audio {ad:.3f}s')
    print('DONE', out, f'{t:.1f}s', f'pre-gain {integ} LUFS')


if __name__ == '__main__':
    main()
