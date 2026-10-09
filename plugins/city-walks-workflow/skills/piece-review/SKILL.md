---
name: piece-review
description: "Review one landmark piece on the live local SF City Walks map in the states people see it, and save the evidence: full zoom-out with a px size table beside its neighbors, close zoom against its OSM outline, and zoom motion both ways through z13 to 16 with frames counted. Use after any piece is drawn, keyed, moved, sheared or re-anchored, before saying it is fixed, and when the owner says 'it's huge', 'too big at zoom out', 'floaty', 'did you look at it', 'check it zoomed out', 'review the piece'. A Stop hook checks replies that call a piece fixed against this review's evidence; it is a tripwire that can be missed or misfire, not a guarantee."
allowed-tools:
  - Bash
  - Read
  - Write
---

# piece-review

## Goal

A dated folder that proves the piece was looked at where people look: full zoom-out, close zoom, and in motion. A piece checked at one end only is not reviewed.

## Why this exists

On 2026-10-03 a de Young render was checked only at close zoom and shipped far heavier than its neighbors at full zoom-out ("disproportionately huge on full zoom out"). The rule already existed (size is judged at full zoom-out AND in zoom motion); nothing enforced it. The lesson: a visual change is verified by looking at it in use.

## Tools

claude-in-chrome in the user's own Chrome (follow `shared-chrome` first), Bash, the local preview. The repo's own runtime is fixed to `http://127.0.0.1:3777` (`npm run demo`; `scripts/local-runtime.mjs` refuses port overrides). The 2026-10-03 sign-in work used an ad hoc server on `http://localhost:3881`; use that only when sign-in is under test, and confirm the origin in the Google console first. Never chrome-devtools, never a headless browser, never `screencapture`.

## Steps

All files go in `$CITY_WALKS_REPO/review-<YYYYMMDD>/<slug>/`.

1. **Read** `references/browser-snippets.md`. Obligatory.
2. **Outlines on.** Add the OSM footprint outlines to the live map (snippet 1).
3. **Full zoom-out.** Zoom to the floor. Take the DOM dump (snippet 2) and save it as `rendered-zoomout.json`. Screenshot with the outlines on: `zoomout.jpg`.
4. **Size table.** `python3 "${CLAUDE_PLUGIN_ROOT}/skills/piece-review/scripts/weight_table.py" --dump review-<date>/<slug>/rendered-zoomout.json --slug <slug> --baseline git:<rev> --out review-<date>/<slug>/zoomout-table.md`
   It sizes each version by the map's own contract (`components/LiveMap.tsx`, `lib/pieceScale.ts`) and reports three things apart: DISPLAYED SIZE, DISPLAYED INK, SHAPE ONLY, plus a DUMP CHECK (is the piece drawn at the size the contract gives). Exit 1 is a flag (a change to look at), exit 3 is NOT REVIEWED (span, hidden piece, empty dump, no sizeM). Name the baseline honestly: the script does not know which revision the owner approved. Then LOOK at `zoomout.jpg` beside the neighbors and say in chat what is seen.
5. **Close zoom.** Jump to z16 to 17 on the piece (snippet 3) and screenshot against its outline: `close-outline.jpg`.
6. **Zoom motion.** Only when the page reports `visible`: z13 to 16 and back, 3 s each way, frames counted and end zooms read (snippet 4). Write the file with `python3 "${CLAUDE_PLUGIN_ROOT}/skills/piece-review/scripts/review_gate.py" stamp <slug> --motion '<the JSON the snippet returned>'`, which binds it to the sprite's sha256 and the time. Watch the piece through the cap band.
7. **Gate.** `python3 "${CLAUDE_PLUGIN_ROOT}/skills/piece-review/scripts/review_gate.py" <slug>`. It answers COMPLETE, INCOMPLETE or UNKNOWN. Evidence is bound to the sprite's bytes: change the sprite and the review is stale, same day or not. Evidence older than 12 hours is stale.
8. **Report** what was looked at, at which viewport and zooms, and what was not. Then, and only then, the word "fixed" may be used, and it stays the owner's call whether it is done.

## Rules

1. Reading `references/browser-snippets.md` is obligatory at step 1.
2. The table is a detector, not a sizing rule. Area and visual-weight SIZING stay rejected (`lib/pieceScale.ts`). Never use the table to set a size.
3. The table prints the spread of ink per real square meter across the shown ground pieces of the dump it was given. On the 2026-10-03 opening dump that spread was several-fold, so one piece cannot be judged against its neighbors by that number; the flags compare a version with the version it replaces. The neighbors are judged by eye on the capture; say what is seen. A flag is never a verdict on the art: the approved Ferry Building restoration measures about half the ink of the HEAD piece it replaced and 1.00x against the approved `c3b44f7`.
4. A passing number is a floor, never the verdict. The owner's eyes are ground truth; if the owner says it is huge, it is huge.
5. Motion measured in a hidden tab is not evidence. If the window cannot be made visible, write that the motion check is NOT done; do not write the file.
6. A piece hidden at full zoom-out (below the 14 px threshold) has no full zoom-out size. Say it is hidden; that is a finding for the owner, not a pass.
7. Never create a review file without doing the look. The gate checks that the evidence exists, is well formed, is recent and matches the sprite's bytes. It cannot check that anyone looked; an invented file is a false record.
8. When the owner rules out something this skill does, add it here in the same turn.

## Output

`review-<YYYYMMDD>/<slug>/` with `rendered-zoomout.json`, `zoomout-table.md`, `zoomout.jpg`, `close-outline.jpg`, `zoom-motion.json`, and a chat report naming the click path: local preview, zoom all the way out, find the piece beside its neighbors.
