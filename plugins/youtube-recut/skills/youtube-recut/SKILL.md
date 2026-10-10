---
name: youtube-recut
description: Recut long recorded videos (screen + webcam talks) into tighter, retention-first YouTube edits from the RAW footage, matching a reference edit's filler/pause cuts (e.g. Descript), with branded intro/outro cards, music bed, burned karaoke captions, denoise, punch-in zooms, privacy masks, and a hard QA gate before anything reaches the user. Use when the user asks to recut, re-edit, repurpose, shorten, or re-brand an existing video for YouTube, or says "run the recut workflow" / "next video". Not for Shorts, thumbnails, or titles.
---

# youtube-recut

A gated pipeline. Every stage writes a file, every gate is a script, and **no render runs until the checks that
cost nothing have passed**. The goal is a clean handover on the first real render, with no tokens spent on
avoidable mistakes or uninformed runs.

Scripts live in `scripts/` beside this file (the plugin install is read-only); all state lives in the PROJECT
folder. Run every script with the plugin env: `PY=~/.cache/youtube-recut/venv/bin/python`.

## House rules (each one cost real time before it was a rule)

1. **Reply to every message the user sends, immediately**, even mid-job. Long jobs ALWAYS run in the background.
2. **Ask before every render** (test, full, re-render, phone copy). One closed question, then wait.
3. **The user's tips are instructions.** When they name a source, a file, or a prior fix, switch to it now.
4. **Think; do not copy prior decisions.** A rule from another video (e.g. a redaction) is re-derived for this one.
5. **Measure before diagnosing.** A listening model's report is a lead, never a fact: one produced
   8 of 8 false "clipped word" flags on a real render. Check the waveform or a re-transcription first.
6. **Hand over only after the QA gate passes, as the ONLY open video.** Close every stale player window first
   (on macOS: `osascript -e 'tell application "QuickTime Player" to close every document saving no'`), then open
   the one file, and name it and its length in the message. A stale test window left open once got a test cut
   approved instead of the full render: a wasted render and upload.
   Finals go to YouTube Studio as private drafts; never send videos through chat.
7. **Every output is a new versioned file.** Scripts refuse to overwrite; `work/*.json` keeps `.history/`.
8. **Cut for quality, never for a number.** A cut must fix a flaw (tangent, repetition, fumbling, dead air, a readout).
   The length target is a guide: an over-edited, shorter piece is worse than a better-revised, longer video.
9. Log each correction in `review/revisions-log.md` (note, measured cause, fix, status).

## Stages and gates

| # | Stage | Command(s) | Gate (must pass to continue) |
|---|---|---|---|
| 0 | Env (once per machine) | `scripts/setup_env.sh` | prints `ENV READY` |
| 1 | Intake | write `project.json` from `assets/project.template.json` | the user answered the intake questions (below) |
| 2 | Transcribe (once per source) | `$PY scripts/transcribe.py <proj> <src>` | transcript exists; never redone casually |
| 3 | Plan | draft `plan/edit-plan.md` + `plan/beats.json` | **the user approves the plan** |
| 4 | Map | `$PY scripts/map_beats.py <proj>` | `FLAGS: none` (exit 0) |
| 5 | Align to reference | `$PY scripts/align_reference.py <proj> <track>` | every beat `ok` (exit 0) |
| 6 | Zoom plan | `$PY scripts/zoom_plan.py <proj> <track>` | runs clean |
| 7 | **Preflight** | `$PY scripts/preflight.py <proj> <track> [--only ids]` | `PREFLIGHT PASS` |
| 8 | Test render (ask first) | `$PY scripts/render_track.py <proj> <track> <ver> --only <ids incl. intro>` | then stage 9 |
| 9 | **QA gate** | `$PY scripts/qa_track.py <proj> <track> <render> --ids <ids>` | `QA PASS` + a human read of the caption/text flags |
| 10 | User review | open the render; log the notes | the user's OK |
| 11 | Iterate cheaply | captions-only: `render_track.py ... --captions-only <existing render>`, then `caption_qa.py <render> <new.ass>` | fix verified WITHOUT a render |
| 12 | Full render (ask first) | `render_track.py <proj> <track> <ver>` (~30 min / 12-min track) | stage 9 on the full file |
| 13 | Package + upload | chapters from `renders/<final>.beats.json` (or a `--captions-only` run on the final, which reproduces its timeline); titles/description checked claim-by-claim against the transcript; Studio private draft | the user publishes |

Run stages 2, 5, 6 and 8+ in the background and keep answering the user. A stage that fails twice does not get a
third blind retry: build visibility first (a check that shows what is going on).

## Stage 1: intake (ask ALL of these in ONE AskUserQuestion round, never mid-render)

- Which video(s), which channel, and is there a REFERENCE edit (a Descript/other master with filler cuts, plus its
  transcript/VTT)? Where is the RAW footage (every segment: opening, main, outro; Screen Studio projects are a fallback)?
- Target length and structure. Retention-first means the payoff up front, but **no manufactured wins**: if a video has
  no clear win, ask the user which moment leads. Trim only real dead air ("an over-trimmed video is more noticeable than an
  under-edited one").
- Brand preset (`assets/presets/`; start from `example.json`), series label, track number and title for the card,
  "coming up" line (which tracks). The intro theme and outro music are the user's own files: ask for their paths.
  Names and jargon the videos use go in `asr_prompt` (see `references/project-json.md`).
- Privacy: what must be masked (emails? names?). Re-derive per video; do not inherit another video's redactions.
- Anything to keep or drop by name (tool names, other brands' calls to action).

## Stage 3: the plan

`plan/beats.json` = `{"tracks": {"<track>": [beat, ...]}}`; a beat is
`{"id", "src", "from": "<exact opening words>", "to": "<exact closing words>"}` plus optional `after`/`before`
(seconds, to disambiguate a repeated phrase), `skip: [[from, to], ...]` (approved removals inside a beat), and
`anchors_verified: "<why>"` (a human compared heard_from/heard_to with the plan). Cards are `{"id": "intro", "card": "intro"}`.
Write anchors as the speaker SAYS them; the matcher normalizes gonna/going to and numbers.

## Where things go wrong (read before debugging): `references/failure-catalog.md`

Every defect this pipeline has shipped or nearly shipped, with its detector. When the user reports a problem, find its
class there first; most "new" problems are old ones.

## Files

- `references/project-json.md`: every `project.json` field.
- `references/failure-catalog.md`: defects, causes, detectors, fixes.
- `assets/presets/*.json`: brand presets (cards, music timing, caption style).
- `assets/cards/record-anim.html`, `assets/fonts/`: card template and caption font (SIL Open Font License, `OFL.txt`).
