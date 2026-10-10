"""Cut-edge leak check, from the plan alone (no render needed).

For every cut edge, compares MY final edge (pads + handles, as render_track computes them) with the reference
edit's edge (work/pieces.json). A leak = the extra span I keep beyond the reference edge contains the ONSET of a
sound (level rising 6 dB off its running minimum, above -40 dBFS): the start of a word the reference removed.
A decay of the kept word is not a leak (that is what handles are for).
On the first project it was run on, 16 of 186 edges leaked under fixed pads and 0 after safe_extend.

Usage: python edge_qa.py <project> <track>     exit 1 if any edge leaks
"""
import json, pathlib, subprocess, sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_track as R  # noqa: E402


def levels(path, a, z):
    o = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, a):.3f}', '-i', path, '-map', '0:a:0', '-t', f'{max(z - a, 0.01):.3f}',
                        '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True).stdout
    x = np.frombuffer(o, np.int16).astype(float) / 32768
    return [20 * np.log10(np.sqrt(np.mean(x[i:i + 160] ** 2)) + 1e-9) for i in range(0, len(x) - 159, 160)]


def main():
    P = R.init(sys.argv[1]); side = sys.argv[2]
    cfg = dict(R.SIDE[side], side=side)
    mapped = P.read('beats-mapped.json')[side]
    spec = {b['id']: b for b in P.beats()[side] if 'id' in b}
    for b in mapped:
        if 'id' in b and spec.get(b['id'], {}).get('skip'):
            b['skip'] = spec[b['id']]['skip']
    words = {k: json.load(open(v))['words'] for k, v in cfg['words'].items()}
    pieces = P.read('pieces.json', {}).get(side, {})
    leaks = n = 0
    for b in mapped:
        if 'card' in b or b['id'] not in pieces:
            continue
        path = P.sources[b['src']]
        bare = [x for pr in pieces[b['id']]['pieces'] for x in pr]
        for s, e, ws, m in R.pieces_for(b, words[b['src']], side):
            sh = s if (path, round(s, 3)) in R._BEAT_EDGE else R.safe_extend(path, s, -1, min(R.HANDLE_IN, s))
            eh = e if (path, round(e, 3)) in R._BEAT_EDGE else R.safe_extend(path, e, 1, R.HANDLE_OUT)
            for tag, mine in (('START', sh), ('END', eh)):
                n += 1
                ref = min(bare, key=lambda x: abs(x - mine))
                if abs(ref - mine) > 0.4:
                    continue                      # my own skip/repeat cut: no reference edge nearby
                if (tag == 'START' and mine >= ref) or (tag == 'END' and mine <= ref):
                    continue                      # I keep less than the reference here: cannot add sound
                extra = levels(path, min(ref, mine), max(ref, mine))
                if tag == 'START':
                    extra = extra[::-1]           # walk outward from the reference edge
                low, rise = 0, False
                for i, L in enumerate(extra):
                    low = L if i == 0 else min(low, L)
                    if i and L >= low + 6 and L > -40:
                        rise = True
                if rise:
                    leaks += 1
                    print(f"  LEAK {b['id']:>4} {tag:5s} reference {ref:9.2f}  mine {mine:9.2f}  (keeps the start of a sound the reference cut)")
    print(f'edge_qa {side}: {leaks} of {n} cut edges pull in removed sound')
    sys.exit(1 if leaks else 0)


if __name__ == '__main__':
    main()
