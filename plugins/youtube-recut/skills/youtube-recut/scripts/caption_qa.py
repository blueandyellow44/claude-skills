"""Caption QA: what the render SAYS vs what its captions SHOW.
Transcribes the rendered audio (faster-whisper, filler-prompted), rebuilds the caption word stream from the burned
.ass (one line per caption, karaoke repeats collapsed), and diffs them. Flags words heard but not captioned (a caption
gap) and captioned words not heard. Single-word respellings are reported separately
(they are usually ASR noise, but a real misspelling of a product name shows up there too).
Usage: python caption_qa.py <render.mp4> [captions.ass]   (default: the .ass beside the render)
YR_ASR_PROMPT (set by qa_track.py from the project's "asr_prompt") primes the transcriber: keep the fillers in it
and add the names and jargon your videos use.
"""
import difflib, os, pathlib, re, subprocess, sys, tempfile
from faster_whisper import WhisperModel

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from map_beats import norm as canon  # noqa: E402  numbers/contractions/hyphens normalized like the mapper
FILLERS = {'uh', 'um', 'umm', 'mm', 'hmm', 'mmhmm', 'mhm', 'ah', 'er', 'oh'}
ASR_PROMPT = os.environ.get('YR_ASR_PROMPT') or 'Um, uh, so.'


def norm(t):
    return re.sub(r"[^a-z0-9']", '', t.lower().replace('’', "'"))


def ts(v):
    h, m, s = v.split(':'); return int(h) * 3600 + int(m) * 60 + float(s)


def caption_words(ass):
    """Caption word stream from the burned .ass. Each karaoke line is emitted once per word with that word
    highlighted; a line STARTS where the highlight is on its first word. (Collapsing identical consecutive
    text merged a genuinely repeated sentence into one.)"""
    out = []
    for line in open(ass, encoding='utf-8'):
        if not line.startswith('Dialogue:'):
            continue
        f = line.rstrip('\n').split(',', 9)
        if f[3] != 'Cap':
            continue
        body = re.sub(r'\{\\blur\d+\}', '', f[9])
        if not re.match(r'^\{\\c', body.strip()):
            continue                                  # highlight is not on the first word: same line again
        text = re.sub(r'\{[^}]*\}', '', body).strip()
        start = ts(f[1])
        for w in text.split():
            for t in canon(w):
                if t not in FILLERS:
                    out.append((t, w, start))
    return out


def main():
    render = sys.argv[1]
    cap = caption_words(sys.argv[2] if len(sys.argv) > 2 else str(pathlib.Path(render).with_suffix('.ass')))
    with tempfile.TemporaryDirectory() as d:
        wav = pathlib.Path(d) / 'a.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', render, '-ac', '1', '-ar', '16000', str(wav)], check=True)
        segs, _ = WhisperModel('small.en', device='cpu', compute_type='int8').transcribe(
            str(wav), word_timestamps=True, initial_prompt=ASR_PROMPT)
        heard = [(t, w.word.strip(), w.start) for s in segs for w in s.words for t in canon(w.word) if t not in FILLERS]
    a, b = [x[0] for x in heard], [x[0] for x in cap]
    gaps, extra, respell = [], [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        t = heard[i1][2] if i1 < len(heard) else heard[-1][2]
        mm, ss = divmod(int(t), 60); at = f'{mm}:{ss:02d}'
        def uniq(xs):                                   # one display word per original word (canon splits "I've" in two)
            out = []
            for x in xs:
                if not out or out[-1][1] != x[1] or out[-1][2] != x[2]:
                    out.append(x)
            return ' '.join(x[1] for x in out)
        H = uniq(heard[i1:i2]); C = uniq(cap[j1:j2])
        if ''.join(a[i1:i2]) == ''.join(b[j1:j2]):
            continue                                   # spacing/compound only
        if op == 'delete': gaps.append(f'{at}  heard "{H}" but no caption')
        elif op == 'insert': extra.append(f'{at}  caption "{C}" not heard')
        elif op == 'replace':
            (respell if i2 - i1 == j2 - j1 else gaps).append(f'{at}  heard "{H}" | caption "{C}"')
    print(f'{len(a)} words heard, {len(b)} captioned')
    print(f'== CAPTION GAPS / MISMATCHES ({len(gaps)})'); [print('  ' + g) for g in gaps]
    print(f'== CAPTIONED BUT NOT HEARD ({len(extra)})'); [print('  ' + g) for g in extra]
    print(f'== SAME-LENGTH RESPELLINGS ({len(respell)})'); [print('  ' + g) for g in respell]


if __name__ == '__main__':
    main()
