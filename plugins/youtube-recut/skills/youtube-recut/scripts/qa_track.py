"""QA GATE for a render. Run after every render, BEFORE the user sees it. Writes review/<render>-qa.md.

Usage: python qa_track.py <project> <track> <render.mp4> [--ids a,b,c]   (--ids = the beats a proof rendered)
Gates (FAIL = fix before handing over):
  sync        audio and video durations within one frame
  loudness    integrated within 0.5 LU of target, true peak <= -1.0 dBTP
  captions    caption_qa: words heard but not captioned / captioned but not heard (REPORTED; judge each:
              the reference edit's own spellings and its own omissions are fine, see failure catalog)
  text        text_diff_qa vs the reference transcript: every missing reference word is re-listened (window re-transcribed,
              prompted with the expected words); a word still absent is a real drop -> FAIL. Checked against a
              known-bad render (three clipped words): it fails that one and passes the fixed one.
  privacy     OCR every 2 s of frames for email addresses (tracks with a privacy block or "ocr_scan": true): FAIL on any hit
Not a gate: a listening model's "listen" pass. One reported 8 clipped endings; all 8 were false (silence at every cut).
Use such a pass only as a lead, and verify each claim in the waveform before acting.
"""
import json, os, pathlib, re, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from yr import Project  # noqa: E402

lines, fails = [], []


def say(s=''):
    print(s); lines.append(s)


def gate(ok, msg):
    say(f"- {'PASS' if ok else 'FAIL'}: {msg}")
    if not ok:
        fails.append(msg)


def dur(f, sel):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', sel, '-show_entries', 'stream=duration', '-of', 'csv=p=0', f],
                                capture_output=True, text=True).stdout.strip() or 0)


def main():
    P = Project(sys.argv[1]); side, render = sys.argv[2], str(pathlib.Path(sys.argv[3]).resolve())
    ids = sys.argv[sys.argv.index('--ids') + 1] if '--ids' in sys.argv else 'all'
    tr = P.track(side); au = P.audio
    say(f'# QA: {pathlib.Path(render).name}\n')
    v, a = dur(render, 'v:0'), dur(render, 'a:0')
    rate = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', render],
                          capture_output=True, text=True).stdout.strip()
    fr = eval(rate) if rate else 30
    gate(abs(v - a) <= 1 / fr + 0.01, f'sync: video {v:.3f}s audio {a:.3f}s ({v / 60:.1f} min)')
    eb = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', render, '-map', '0:a', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                        capture_output=True, text=True).stderr
    summ = eb[eb.rfind('Summary:'):]
    I = float(re.search(r'I:\s+(-?[\d.]+) LUFS', summ).group(1)); tp = float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', summ).group(1))
    gate(abs(I - au['target_lufs']) <= 0.5 and tp <= -1.0, f'loudness: {I} LUFS (target {au["target_lufs"]}), true peak {tp} dBTP')
    say('\n## Captions (heard vs captioned)\n```')
    env = dict(os.environ, YR_ASR_PROMPT=P.cfg['asr_prompt']) if P.cfg.get('asr_prompt') else None   # names and jargon to prime the ASR
    r = subprocess.run([sys.executable, str(HERE / 'caption_qa.py'), render], capture_output=True, text=True, env=env)
    say(r.stdout.strip()); say('```')
    if tr['vtt']:
        say('\n## Text vs reference transcript\n```')
        r = subprocess.run([sys.executable, str(HERE / 'text_diff_qa.py'), str(P.root), side, render, ids], capture_output=True, text=True)
        say(r.stdout.strip()); say('```')
        gate(r.returncode == 0, 'text: every reference word is in the render (misses re-listened; see UNRESOLVED above)')
    if tr.get('privacy') or tr.get('ocr_scan'):
        say('\n## Privacy OCR')
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['ffmpeg', '-v', 'error', '-i', render, '-vf', 'fps=0.5,scale=1920:-1', f'{d}/%05d.png'], check=True)
            o = subprocess.run(['swift', str(HERE / 'ocr_emails.swift'), d], capture_output=True, text=True)
            hits = [json.loads(x) for x in o.stdout.splitlines() if x.startswith('{')]
            n = len(list(pathlib.Path(d).glob('*.png')))
        for h in hits[:20]:
            say(f"  - frame {h['file']} (~{(int(h['file'][:5]) - 1) * 2}s): {h['text']}")
        gate(o.returncode == 0 and not hits, f'OCR email scan: {len(hits)} hit(s) in {n} frames' + ('' if o.returncode == 0 else f' (OCR error: {o.stderr[-200:]})'))
    say(f"\n**QA {'FAIL' if fails else 'PASS'}** ({len(fails)} gate failure(s)); caption/text flags above need a human read before handover.")
    out = P.review / f'{pathlib.Path(render).stem}-qa.md'
    out.write_text('\n'.join(lines) + '\n')
    print(f'report: {out}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
