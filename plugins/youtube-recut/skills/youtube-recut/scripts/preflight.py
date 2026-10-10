"""PREFLIGHT: everything that can be checked before spending a render. Run it before EVERY test or full render.

Usage: python preflight.py <project> <track> [--only ids]
Checks (FAIL blocks the render, WARN is reported):
  tools     ffmpeg/ffprobe on PATH, an ffmpeg with libass, deepFilter, Playwright's Chrome channel
  config    sources, transcripts, reference master/VTT, brand audio, caption font all exist
  plan      every beat of the track is mapped with anchor scores >= 0.72 (work/beats-mapped.json)
  align     every beat has reference pieces with check "ok" (work/pieces.json), when a reference exists
  zoom      work/zoom-plan.json covers every piece start (a moved edge silently drops its zoom otherwise)
  edges     edge_qa: no cut edge pulls in the start of a sound the reference removed
  length    planned output length vs the track's target_min range
Exit 1 on any FAIL.
"""
import json, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_track as R  # noqa: E402
from yr import ENV, SKILL  # noqa: E402

fails, warns = [], []


def check(ok, msg, warn=False):
    tag = 'ok  ' if ok else ('WARN' if warn else 'FAIL')
    print(f'  {tag} {msg}')
    if not ok:
        (warns if warn else fails).append(msg)


def main():
    P = R.init(sys.argv[1]); side = sys.argv[2]
    only = sys.argv[sys.argv.index('--only') + 1].split(',') if '--only' in sys.argv else None
    tr = R.SIDE[side]; b = R.BRAND
    print('tools')
    for t in ('ffmpeg', 'ffprobe'):
        check(shutil.which(t), f'{t} on PATH')
    check(bool(R.FF), f'ffmpeg with libass: {R.FF}')
    import tempfile
    with tempfile.TemporaryDirectory() as d:     # prove the denoiser runs (existing is not the same as working)
        subprocess.run([R.FF, '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=440:d=1', '-ar', '48000', f'{d}/t.wav'], check=True)
        r = subprocess.run([str(ENV / 'bin' / 'deepFilter'), '--atten-lim', '12', '-o', f'{d}/o', f'{d}/t.wav'], capture_output=True, text=True)
        check(r.returncode == 0 and any(pathlib.Path(d, 'o').glob('*.wav')), 'deepFilter processes a test file' + ('' if r.returncode == 0 else f': {r.stderr.strip().splitlines()[-1][:120]}'))
    pw = subprocess.run([sys.executable, '-c', 'from playwright.sync_api import sync_playwright as s\nwith s() as p: p.chromium.launch(channel="chrome").close()'],
                        capture_output=True, text=True)
    check(pw.returncode == 0, 'Playwright can launch Chrome (cards)', warn=True)
    print('config')
    for k, v in P.sources.items():
        check(pathlib.Path(v).exists(), f'source {k}: {v}')
    for k, v in tr['words'].items():
        check(pathlib.Path(v).exists(), f'transcript {k} (run transcribe.py)')
    if tr.get('reference'):
        check(bool(tr['master']) and pathlib.Path(tr['master']).exists(), f"reference master {tr['master']}")
        check(not tr['vtt'] or pathlib.Path(tr['vtt']).exists(), f"reference transcript {tr['vtt']}")
    for k in ('theme_wav', 'outro_wav'):
        check(bool(b.get(k)) and pathlib.Path(b[k]).exists(), f'brand {k}: {b.get(k)} (your own music file; set it in the brand preset or project.json)')
    check((SKILL / 'assets' / 'fonts' / 'Manrope-Bold.ttf').exists(), 'caption font')
    print('plan')
    mapped = P.read('beats-mapped.json', {}).get(side)
    check(mapped is not None, 'work/beats-mapped.json has this track (run map_beats.py)')
    if not mapped:
        return finish()
    beats = [x for x in mapped if 'id' in x and 'card' not in x and (not only or x['id'] in only)]
    from map_beats import norm
    for x in beats:
        if x.get('raw_start') is None or not x.get('raw_end') or x['raw_end'] <= x['raw_start']:
            check(False, f"beat {x['id']}: not mapped"); continue
        if x.get('anchors_verified'):
            continue                                  # a human read heard_from/heard_to against the plan
        h0 = (norm(x['heard_from']) or [''])[0]; hz = (norm(x['heard_to']) or [''])[-1]
        if min(x['score_from'], x['score_to']) < 0.72 or h0 != norm(x['from'])[0] or hz != norm(x['to'])[-1]:
            check(False, f"beat {x['id']}: anchors {x['score_from']}/{x['score_to']}, heard {x['heard_from'][:40]!r} ... {x['heard_to'][-40:]!r} "
                         f"(read it; if right, add \"anchors_verified\": \"<why>\" to the beat in plan/beats.json)")
    check(all(x.get('raw_start') is not None for x in beats), f'{len(beats)} beats mapped')
    pieces = P.read('pieces.json', {}).get(side, {})
    if tr.get('reference'):
        print('align')
        ref_src = (tr.get('reference') or {}).get('src')
        need = [x for x in beats if not ref_src or x['src'] == ref_src]
        bad = [x['id'] for x in need if pieces.get(x['id'], {}).get('check') != 'ok']
        check(not bad, f'reference pieces ok for {len(need)} beats' + (f' (bad: {bad})' if bad else ''))
        # Every beat's pieces must reach its planned first and last words (a false cut once dropped a beat's last word).
        short = [f"{x['id']}(ends {pieces[x['id']]['pieces'][-1][1]:.2f} < word end {x['raw_end']:.2f})" for x in need
                 if x['id'] in pieces and pieces[x['id']]['pieces'] and pieces[x['id']]['pieces'][-1][1] < x['raw_end'] - 0.15]
        late = [f"{x['id']}(starts {pieces[x['id']]['pieces'][0][0]:.2f} > word start {x['raw_start']:.2f})" for x in need
                if x['id'] in pieces and pieces[x['id']]['pieces'] and pieces[x['id']]['pieces'][0][0] > x['raw_start'] + 0.15]
        check(not short and not late, 'pieces cover every beat\'s first and last planned word' + (f': {short + late}' if short or late else ''))
    print('zoom + length')
    words = {k: json.load(open(v))['words'] for k, v in tr['words'].items() if pathlib.Path(v).exists()}
    zoom = R.ZOOM.get(side, {})
    spec = {x['id']: x for x in P.beats()[side] if 'id' in x}
    total, missing, npieces = 0.0, 0, 0
    for x in beats:
        if spec.get(x['id'], {}).get('skip'):
            x['skip'] = spec[x['id']]['skip']
        if x['id'] not in pieces and tr.get('reference'):
            continue
        for s, e, ws, m in R.pieces_for(x, words[x['src']], side):
            npieces += 1; total += e - s
            if f"{x['src']}|{s:.3f}" not in zoom:
                missing += 1
    check(missing == 0, f'zoom plan covers {npieces - missing}/{npieces} pieces (run zoom_plan.py)', warn=bool(only))
    cards = sum((b['cards']['intro_frames'] if c['card'] == 'intro' else b['cards']['outro_frames']) / b['cards']['fps']
                for c in mapped if 'card' in c and (not only or c['card'] in only))
    mins = (total + cards) / 60
    lo, hi = tr.get('target_min', [0, 999])
    check(only or lo <= mins <= hi, f'planned length {mins:.1f} min (target {lo}-{hi}; long pauses at 4x shorten it slightly)', warn=True)
    print('edges')
    r = subprocess.run([sys.executable, str(HERE / 'edge_qa.py'), str(P.root), side], capture_output=True, text=True)
    print('    ' + (r.stdout.strip().splitlines() or ['(no output)'])[-1])
    check(r.returncode == 0, 'no cut edge pulls in removed sound')
    return finish()


def finish():
    print(f"\nPREFLIGHT {'FAIL' if fails else 'PASS'}: {len(fails)} fail, {len(warns)} warn")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
