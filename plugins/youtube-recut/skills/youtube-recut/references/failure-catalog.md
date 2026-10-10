# Failure catalog

Every defect the pipeline shipped or nearly shipped on the recuts it was built on. Each row names the
detector that now catches it. When the user reports something, match it here before investigating from scratch.

## Audio

| Symptom (as heard) | Measured cause | Fix in code | Detector |
|---|---|---|---|
| Voice sounds blown out | Raw voice ~-27 LUFS needs +13 dB; peaks went to +2.7 dBFS inside a 24-bit INTEGER intermediate and hard-clipped. Final file peaked at -2 dB, hiding it | Float intermediate (pcm_f32le) + alimiter at `limit_dbfs` before linear loudnorm | By construction; qa_track checks true peak. Rule: after any gain > 6 dB, compute peak + gain before writing a file |
| Music too loud under the voice | Raw voice is quieter than the finished master the music was balanced against | Voice is leveled to target LUFS BEFORE the mix | Listen at the card handoff |
| Word clipped at a cut ("to, put" sounded like "t-") | The cut landed 0.09 s before the reference's | `refine_cut` to ~10 ms against the reference master | text_diff_qa, caption_qa |
| Tail of the previous sentence audible after the card | Beat anchor started two words early | Anchors snap to the exact first/last planned word | preflight word check |
| Cold open starts mid-word / ends with a flash of the next word | Fixed-length pads (+0.12 s / +0.18 s) and handles ran into neighboring words | `safe_extend`: extend only through a real gap, stop at the next onset; never extend where the reference cut mid-sound; pad+handle as ONE extension | `edge_qa.py` (16 of 186 edges leaked before, 0 after) |
| Sentence ends one word early | Anchor end-snap searched backward only; the fuzzy match landed one word short | Snap searches both directions | preflight: first/last heard word must equal the plan's |
| "Clipped trailing s" (reported by a listening model) | NOT a defect: silence both sides of every flagged cut; sibilant energy matched raw | none | Never act on a listening-model claim without the waveform |
| Stutter "that are, that are" kept | Raw has an adjacent repeat the reference transcript does not | `drop_repeats` | text_diff_qa |

## Captions

| Symptom | Cause | Fix | Detector |
|---|---|---|---|
| A product name misspelled as a sound-alike word (22x) | Respelling pass grouped words while master time moved `< 3 s`; a BACKWARDS jump (reordered beats) is negative and passed, so whole runs got an empty reference window. Unequal-length blocks ("read-only" vs "Read only") were skipped | `0 <= gap < 3`; unequal blocks pair by similarity; spoken contractions merge | caption_qa "same-length respellings" |
| "put" heard but not captioned (and 5 more) | ASR timed the word inside a removed pause, so it was dropped with the pause | Insert a reference word the ASR missed when the cut audio has speech in that gap | caption_qa "heard but no caption" |
| "gonna to" | Respelling took "gonna" for "going" and left "to" | contraction merge | caption_qa |
| Captions too low | Position guessed | Style from the measured box of a reference frame (size 204, margin 56 at 4K) | Frame grab vs reference |
| Wrong caption weight | Variable font's default instance is ExtraLight; libass matched it | Static Bold instance renamed "Manrope Cap" | Frame grab |
| The reference transcript's own typos on screen | Captions take the reference transcript's spelling, typos included | `plan/caption-fixes.json` whole-word fixes | caption_qa respellings list (read it every render) |
| "77.5% .5 % C." | ASR split one written token into fragments; pairing fixed only the first | Fragment merge in unequal blocks | caption_qa |
| Caption for a word the audio does not have ("I've") | Reference cut a false start its transcript kept | `corrections` entry with `"correct": ""` deletes it | caption_qa "captioned but not heard" |
| A short sentence captioned as an ASR garble | ASR garble with no word-level pairs; every respelling rule skipped it | Small local mismatch (<= 6 words): the hand-corrected reference replaces the ASR words over the same span | caption_qa |
| A sentence said three times in a row looked uncaptioned | caption_qa merged identical consecutive lines | Lines split on the karaoke reset (highlight on first word) | caption_qa self-check |
| Text gate demanded words that were cut on purpose | Expected text ignored approved skips | Skips are removed from the expected text | text_diff_qa |
| Beat lost its last word | Aligner saw a "cut" whose resync landed past the beat end (only the trailing pause was shortened) | Extend the last piece through the planned last word | preflight word-coverage check |

## Picture

| Symptom | Cause | Fix | Detector |
|---|---|---|---|
| Zoom framed the webcam / overflowed | Activity included the face bubble | Haar face mask + reject boxes containing a face; clamp; text-density check | Frame grabs of zoomed pieces |
| Zoom silently missing after a cut change | Zoom plan is keyed by piece start; moved edges miss their key | Rebuild zoom plan after any mapping/alignment change | preflight zoom coverage |
| Email visible | | drawbox masks in reference-master time | qa_track OCR scan (FAIL on any hit) |
| Name redacted that should not be | Copied another video's decision | Re-derive privacy per video with the user | intake question |
| A/V drift (0.5 s by the end) | Keyframe-seek cutting | Exact-length pieces: n = round(dur*fps) frames, audio trimmed to n/fps | qa_track sync gate |

## Environment and tooling

| Symptom | Cause | Fix | Detector |
|---|---|---|---|
| Full render died 25 min in at the denoise step | torchaudio had no audio backend (soundfile missing); "deepFilter exists" was true | soundfile in setup_env | setup_env and preflight RUN deepFilter on a 1 s test file |
| Approved cut points moved 10-60 ms after an env change | Alignment is numerically sensitive (numpy/scipy versions flip near-tied correlation peaks) | Approved pieces are frozen; only beats whose span changed re-align (`--redo` to force) | align_reference prints keep/redo per beat |
| Renderer crash (StopIteration) | Aligner emitted an inverted final piece (start > end) | Drop pieces with end <= start | align_reference |
| QA said PASS on a render with 3 clipped words | Text flags were report-only, buried in ~35 spelling-noise flags; one beat silently unchecked | Canonical normalization (numbers, times, contractions, compounds, fillers), 3-pass re-listen of each missing word, accept list for human-verified reference errors (`plan/qa-accepted.json`), unchecked beat = FAIL | Fails the known-bad render it was built against, passes the fixed ones |

## Process

| What went wrong | Rule now |
|---|---|
| Messages unanswered during a long foreground job | Background every long job; reply to every message |
| Re-render started without asking | Ask before every render |
| Used finished masters when raw footage existed; ignored the user's tip about an earlier fix | Intake asks for raw + reference; a tip is an instruction |
| QA detector gave clean results on a known-bad file | Prove every detector fails on a known-bad render first (one detector did not; it was removed) |
| Text diff hid a leak | Its expected text came from the pipeline's own mapping; expected text now comes from the reference transcript's anchors |
| Full render with 5 beats ending a word early | preflight word check (would have blocked it) |
