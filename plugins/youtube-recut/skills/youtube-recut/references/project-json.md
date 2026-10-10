# project.json

One file per project folder. Paths may use `~`. Start from `assets/project.template.json`.

| Field | Meaning |
|---|---|
| `sources` | key -> raw footage file. Keys are what beats use as `src` (e.g. `v1`, `v3o` for a separate opening segment). Use RAW footage (no music, no captions), every segment. |
| `brand.preset` | a file in `assets/presets/` (copy `example.json` and fill it in); any key set beside it overrides the preset (e.g. `"series": "..."`). `theme_wav` and `outro_wav` are your own music files and must exist: the intro card plays the first seconds of the theme, the bed continues it under the voice per `music` (seconds after the card starts: duck from `duck_start` to `duck_end` by `duck_db`, fade out from `fade_start` to `fade_end`), and the outro card plays `outro_wav`. Tune `cards` frame counts and `music` times to your music. |
| `asr_prompt` | optional top-level string that primes the QA transcriber, e.g. `"Um, uh, so, <product names and jargon you say>."`. Keep the fillers in it. |
| `audio` | `target_lufs` (YouTube: -14), `true_peak`, `limit_dbfs` (voice limiter before normalize), `denoise_atten_db` (DeepFilterNet attenuation cap). |
| `tracks.<t>.n` / `title` | card label "<series> · Track n" and the intro card title. |
| `tracks.<t>.target_min` | [min, max] minutes; preflight warns outside it. |
| `tracks.<t>.words` | source key -> transcript file in `transcripts/` (made by transcribe.py). |
| `tracks.<t>.reference` | the edit to match: `src` (which source it was cut from), `master` (the edited video, for cut alignment), `vtt` (its hand-corrected transcript, for caption spelling, repeat removal and the text diff). Omit when there is no reference edit (then no filler/pause cuts are recovered; plan tightly). |
| `tracks.<t>.coming_up` / `promise` | optional on-screen "Coming up: ..." line, shown 3 s into beat `promise`. |
| `tracks.<t>.privacy` | `{"boxes": [[[m_lo, m_hi], [[x, y, w, h], ...]], ...], "name": null}`: black boxes (3840x2160 px) during reference-master time windows. Pieces there never zoom. `name` = a word to mute and recaption (rarely; ask). |
| `tracks.<t>.ocr_scan` | run the email OCR gate even without privacy boxes (default on when privacy is set). |
| `tracks.<t>.corrections` | optional `transcripts/<file>.json` of caption fixes keyed by raw word start: `{"corrections": [{"raw_s", "correct", "merge_next"}]}`. |
