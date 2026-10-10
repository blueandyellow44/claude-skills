"""Word-timed transcript of a raw source (faster-whisper small.en, CPU int8). Run ONCE per source; cached.

Usage: python transcribe.py <project> <source-key>
Writes <project>/transcripts/<source-key>-raw-words.json: {"source": path, "words": [{"w", "s", "e"}]}.
Refuses to overwrite: a transcript is an input the plan's anchors are written against.
"""
import json, pathlib, subprocess, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from yr import Project  # noqa: E402
from faster_whisper import WhisperModel


def main():
    P = Project(sys.argv[1]); key = sys.argv[2]
    src = P.sources[key]
    out = P.transcripts / f'{key}-raw-words.json'
    if out.exists():
        sys.exit(f'{out} exists (transcripts are cached inputs; delete it deliberately to redo)')
    with tempfile.TemporaryDirectory() as d:
        wav = pathlib.Path(d) / 'a.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-map', '0:a:0', '-ac', '1', '-ar', '16000', str(wav)], check=True)
        segs, info = WhisperModel('small.en', device='cpu', compute_type='int8').transcribe(str(wav), word_timestamps=True)
        words = [{'w': w.word.strip(), 's': round(w.start, 2), 'e': round(w.end, 2)} for s in segs for w in s.words if w.word.strip()]
    json.dump({'source': src, 'words': words}, open(out, 'w'))
    print(f'TRANSCRIPT {out}: {len(words)} words, {info.duration / 60:.1f} min')


if __name__ == '__main__':
    main()
