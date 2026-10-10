# youtube-recut

One skill and a gated pipeline for recutting a long recorded talk (screen plus webcam) into a tighter YouTube edit, working from the raw footage. It matches the filler and pause cuts of a reference edit, adds intro and outro cards, a music bed, burned karaoke captions, denoise, punch-in zooms and privacy masks, and refuses to hand over a render until its checks pass.

Every stage writes a file into your project folder and every gate is a script. `skills/youtube-recut/SKILL.md` has the stage table; `references/failure-catalog.md` lists each defect the pipeline has shipped or nearly shipped and the detector that now catches it.

## What it needs

- macOS for the whole pipeline. The privacy gate reads frames with Apple Vision through `swift`; everything else is ffmpeg and Python.
- `ffmpeg` and `ffprobe` on PATH, and `uv`.
- `scripts/setup_env.sh` builds one Python 3.11 environment in `~/.cache/youtube-recut/venv` (override with `YR_ENV`): numpy, scipy, torch, torchaudio, DeepFilterNet, faster-whisper, soundfile, OpenCV 4, Playwright, imageio-ffmpeg. It is a large install. The first transcription also downloads the `small.en` speech model.
- Google Chrome, for the cards. The card page loads its typeface from Google Fonts, so card rendering needs a network connection.
- Your own music: a theme file and an outro file. None ships here.
- In practice, a reference edit of the same recording (an edited master and its transcript as a `.vtt`). See the limits below.

## Setup

1. Run `scripts/setup_env.sh` and wait for `ENV READY`.
2. Copy `assets/presets/example.json` to a preset of your own and fill in the card text, the two music paths and the timings.
3. Make a project folder, copy `assets/project.template.json` into it as `project.json`, and follow the stages in the skill.

## What was removed from the private version

- The channel's brand preset: series name, card text, web addresses, and the paths to its music package. `example.json` replaces it with placeholders.
- A hardcoded speech-recognition prompt of that channel's product names. It is now the optional `asr_prompt` setting.
- Names, dates and quoted lines from the recordings the pipeline was built on, in comments and in the failure catalog. The mechanics and the numbers are unchanged.

The caption typeface in `assets/fonts/` is Manrope Bold, renamed "Manrope Cap" so the caption renderer cannot pick a lighter weight. It is under the SIL Open Font License; the license is beside it in `OFL.txt`.

## Known limits

- Built on a handful of recuts for one channel. The card design, the caption style and the default timings are that channel's and are yours to change.
- Output is fixed at 3840x2160. Narrower sources are pillarboxed; other shapes are not handled.
- English only (`small.en`).
- The renderer reads cut pieces from the alignment against a reference edit. A track with no reference edit can be transcribed, planned and mapped, but the later stages expect those pieces.
- The music bed is not optional: the renderer always opens the theme file.
- Caption and text checks compare speech recognition against a transcript. They report flags a person has to read; `QA PASS` alone is not a handover.
- The text gate can pass a dropped word. It re-listens to a missing word with the expected words as a prompt, and the transcriber can then report a word that is not in the audio. In the check below, a render with one word removed passed the text gate while the caption check listed the mismatch. Read the caption flags as part of the gate.
- Nothing here uploads anything. Packaging and the YouTube Studio draft are done by you or by other tools.

## What was checked for this export

One run, on a 14-second synthetic clip: speech from the macOS `say` voice over a test pattern, with a reference edit made by cutting one pause and one filler word out of it. From this folder: `setup_env.sh` built a fresh environment; transcribe, map, align, zoom plan and preflight ran clean; the aligner found the reference cut within 0.01 s; a full render with both cards finished; and the QA gate passed it. On files made bad on purpose, the sync gate and the email gate failed as they should, preflight failed on a missing music file, the mapper flagged an anchor that matched nothing, and the text gate did not fail (see the limits above). Real footage, zooms that actually trigger, privacy boxes, the "coming up" line and long renders were not exercised here.
