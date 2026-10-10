"""Recover a reference edit's filler/pause cuts by aligning raw beat audio against the edited master.

The reference master for each video is the raw recording with the editor's removals (filler words,
repeats, shortened pauses). For each approved beat [raw_start, raw_end] this walks the master and
raw in step: while consecutive windows match at the same offset, the raw span is kept; when they
stop matching, the reference cut something, and the next raw position is found by searching ahead in
raw for the master's next window. Output: a list of raw (start, end) pieces per beat, plus the
fraction of the beat the reference removed. Written to <project>/work/pieces.json.
Every beat gets check ok/FAIL (kept length vs master span, anchor scores); exit code 2 on any FAIL.
Usage: python align_reference.py <project> <track> [--redo id,id]   (unchanged beats keep their approved pieces)
"""
import json, pathlib, subprocess, sys
import numpy as np
from scipy.signal import fftconvolve

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yr import Project  # noqa: E402
SR = 4000
WIN = 0.30            # seconds per comparison window
STEP = 0.10           # walk step
MATCH = 0.55          # normalized correlation that counts as "same audio"
RESYNC = 0.80         # a re-sync after a cut must match this well, and be confirmed by the next window


def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return x - x.mean()


def ncc_search(needle, hay):
    """Best normalized correlation of needle inside hay; returns (score, offset_samples)."""
    n = len(needle)
    if len(hay) < n or not np.any(needle):
        return 0.0, 0
    nd = (needle - needle.mean()) / (np.linalg.norm(needle - needle.mean()) + 1e-9)
    c = fftconvolve(hay, nd[::-1], mode='valid')
    e = np.sqrt(np.maximum(fftconvolve(hay ** 2, np.ones(n), mode='valid') - fftconvolve(hay, np.ones(n), mode='valid') ** 2 / n, 1e-12))
    r = c / e
    k = int(np.argmax(r))
    return float(r[k]), k


def seg(x, t, d):
    a = int(t * SR); return x[a:a + int(d * SR)]


def locate(raw, master, t_raw, m_lo, m_hi, dur=1.5):
    s, k = ncc_search(seg(raw, t_raw, dur), master[int(m_lo * SR):int(m_hi * SR)])
    return s, m_lo + k / SR


def refine_cut(raw, master, t_m, o1, o2, back=0.55, fwd=0.12, step=0.01, win=0.04):
    """The cut was detected at master time t_m, up to WIN+STEP late. Find the master time c where the
    old alignment (raw = master + o1) stops matching and the new one (raw = master + o2) starts."""
    cs = np.arange(max(0.0, t_m - back), t_m + fwd, step)
    def score(o, c):
        a = seg(master, c, win); b = seg(raw, c + o, win)
        if len(a) != len(b) or np.sqrt(np.mean(a ** 2)) < 2e-3:
            return 0.0                                   # silence is neutral
        a = a - a.mean(); b = b - b.mean()
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    old = np.array([score(o1, c) for c in cs]); new = np.array([score(o2, c) for c in cs])
    tot = np.array([old[:k].sum() + new[k:].sum() for k in range(len(cs) + 1)])
    k = int(np.argmax(tot))
    return float(cs[k]) if k < len(cs) else float(t_m + fwd)


def snap_to_silence(raw, master, pieces, offs, reach=0.5, lead=0.25, thr_db=-45.0, hop=0.01):
    """Put every internal cut on real silence. offs[i] = raw - master offset of piece i.
    A piece that ends mid-sound is extended forward to the next silence when the reference master kept
    that sound (it matches at the same offset), otherwise trimmed back to the last silence (a fragment
    the reference removed). A piece that starts mid-sound backs up to its onset."""
    def db(x, t):
        a = seg(x, t, hop)
        return 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9) if len(a) else -120
    def match(t0, t1, off):
        a = seg(raw, t0, t1 - t0); b = seg(master, t0 - off, t1 - t0)
        if len(a) != len(b) or len(a) < 10:
            return 0.0
        a = a - a.mean(); b = b - b.mean()
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    out = [list(p) for p in pieces]
    for i in range(len(out) - 1):
        # ends stay where refine_cut put them: they match the reference's own cut
        s0 = out[i + 1][0]
        if db(raw, s0) > thr_db:                             # starts mid-sound: back up to the onset
            t = s0
            while t > s0 - lead and db(raw, t - hop) > thr_db:
                t -= hop
            if t > out[i][1]:
                out[i + 1][0] = round(t, 3)
    return [tuple(p) for p in out]


def align_beat(raw, master, rs, re, m_hint):
    # anchor the beat's start and end in the master
    s0, m0 = locate(raw, master, rs, max(0, m_hint - 400), m_hint + 900)
    s1, m1 = locate(raw, master, re - 1.5, m0, m0 + (re - rs) + 5)
    m1 += 1.5
    pieces, offs, t_raw, t_m, start = [], [], rs, m0, rs
    while t_m < m1 - WIN and t_raw < re + 2:
        a = seg(raw, t_raw, WIN); b = seg(master, t_m, WIN)
        same = np.dot(a - a.mean(), b - b.mean()) / (np.linalg.norm(a - a.mean()) * np.linalg.norm(b - b.mean()) + 1e-9)
        quiet = np.sqrt(np.mean(b ** 2)) < 2e-3 and np.sqrt(np.mean(a ** 2)) < 2e-3
        if same >= MATCH or quiet:
            t_raw += STEP; t_m += STEP; continue
        # The reference cut here: find where raw resumes the master's next window (search up to 12 s ahead)
        s, off = ncc_search(seg(master, t_m, 0.8), raw[int(t_raw * SR):int((t_raw + 12) * SR)])
        jump = off / SR
        if s >= RESYNC:        # confirm with the following window at the same offset
            c = seg(raw, t_raw + jump + 0.8, 0.5); d = seg(master, t_m + 0.8, 0.5)
            conf = np.dot(c - c.mean(), d - d.mean()) / (np.linalg.norm(c - c.mean()) * np.linalg.norm(d - d.mean()) + 1e-9)
            quiet_next = np.sqrt(np.mean(d ** 2)) < 2e-3
            if conf < 0.6 and not quiet_next:
                s = 0
        if s < RESYNC:         # could not re-sync: step both and keep going
            t_raw += STEP; t_m += STEP; continue
        if jump < 0.05:
            t_raw += STEP; t_m += STEP; continue
        o1, o2 = t_raw - t_m, t_raw + jump - t_m          # raw = master + offset, before and after the cut
        c_star = refine_cut(raw, master, t_m, o1, o2)
        pieces.append((round(start, 3), round(c_star + o1, 3))); offs.append(o1)
        start = c_star + o2
        t_raw += jump
    # Final piece: run until the kept total matches the master span, not to a fixed cap at the mapped end. ASR word
    # times can run early; a fixed cap once cut the last two words off a beat (and produced an inverted piece).
    if pieces and start >= re - 0.05:
        # The last "cut" re-synced AFTER the beat's planned last word: the reference only shortened the trailing
        # pause, it did not cut the word. Extend the last piece through the word instead (a beat once lost its
        # last word to a false cut inside its final two words).
        s_, e_ = pieces[-1]
        pieces[-1] = (s_, round(max(e_, re + 0.3), 3))
    else:
        so_far = sum(e - s for s, e in pieces)
        end = max(min(t_raw + WIN, re + 0.3), start + (m1 - m0) - so_far)
        pieces.append((round(start, 3), round(min(end, re + 2.0), 3))); offs.append(t_raw - t_m)
    pieces = snap_to_silence(raw, master, pieces, offs)
    # A cut detected at the very end of a beat can leave a final piece that starts after it ends
    # (start after end); an inverted piece crashes the renderer. Drop empty/inverted pieces.
    pieces = [(s, e) for s, e in pieces if e - s > 0.02]
    kept = sum(e - s for s, e in pieces)
    return {'master_start': round(m0, 2), 'master_end': round(m1, 2), 'anchor_scores': [round(s0, 2), round(s1, 2)],
            'pieces': pieces, 'kept_s': round(kept, 2), 'raw_s': round(re - rs, 2)}


def main():
    P = Project(sys.argv[1]); side = sys.argv[2]; tr = P.track(side)
    if not tr['master']:
        sys.exit(f'track {side} has no reference master in project.json')
    mapped = P.read('beats-mapped.json')[side]
    src_key = (tr.get('reference') or {}).get('src') or next(b['src'] for b in mapped if 'src' in b)
    raw = load(P.sources[src_key])
    master = load(tr['master'])
    ratio = len(master) / len(raw)
    # Approved pieces are FROZEN: alignment is numerically sensitive (a different numpy/scipy moved cuts 10-60 ms,
    # one of them the exact spot the user had flagged). Only beats whose mapped span changed, or --redo ids, are re-aligned.
    prev = P.read('pieces.json', {}).get(side, {})
    redo = sys.argv[sys.argv.index('--redo') + 1].split(',') if '--redo' in sys.argv else []
    out = {}
    for b in mapped:
        if 'card' in b or b['src'] != src_key:   # beats from other sources (e.g. a separate opening) have no reference
            continue
        span = [b['raw_start'], b['raw_end']]
        old = prev.get(b['id'])
        if old and old.get('raw_span') == span and b['id'] not in redo:
            out[b['id']] = old
            print(f"keep {b['id']:>4} (span unchanged; approved pieces frozen)", flush=True)
            continue
        r = align_beat(raw, master, b['raw_start'], b['raw_end'], b['raw_start'] * ratio)
        r['raw_span'] = span
        r['check'] = 'ok' if abs(r['kept_s'] - (r['master_end'] - r['master_start'])) < max(0.6, 0.15 * len(r['pieces'])) and min(r['anchor_scores']) >= 0.4 else 'FAIL'
        out[b['id']] = r
        print(f"{r['check']:4} {b['id']:>4} raw {r['raw_s']:6.1f}s -> kept {r['kept_s']:6.1f}s  pieces {len(r['pieces']):3d}  anchors {r['anchor_scores']}  master {r['master_start']}-{r['master_end']}", flush=True)
    allp = P.read('pieces.json', {})
    allp[side] = out
    P.write('pieces.json', allp)
    if any(r['check'] != 'ok' for r in out.values()):
        sys.exit(2)


if __name__ == '__main__':
    main()
