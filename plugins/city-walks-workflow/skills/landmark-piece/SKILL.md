---
name: landmark-piece
description: "The one pipeline for making or redrawing a landmark piece (sprite) on the SF City Walks / wallywalks.app map: surveyed OSM footprint and building parts, a deterministic render in the set's 30 degree camera, keying, anchoring on the footprint centroid, registration, and verify-pieces. Use when the owner says 'add a piece', 'new landmark', 'redraw the X', 'the X looks wrong', 'fix orientation', 'fill gaps on the walks', 'draw it from the survey', or when a piece has come back wrong in shape twice. Not for piece SIZE rules (lib/pieceScale.ts, the owner's word only) and not for the review that follows (piece-review)."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# landmark-piece

## Goal

One piece, drawn from its survey, in the same camera as every other piece, sitting on its real footprint, registered and verified. The shape comes from the survey, never from the image model's guess.

## Why this exists

The de Young was redrawn by the image model six or seven times (2026-09-22 to 2026-10-03) and came back a thin bar each time. Then its first survey render looked straight down on the plan, against the ONE CAMERA ruling, and drew far too heavy at full zoom-out. The lesson: a landmark the image model keeps misshaping gets drawn from its survey.

## Tools

Bash (python3 with Pillow, numpy, scipy; node; network to the OSM API and Overpass). Run from the map repo (`$CITY_WALKS_REPO`).

## Before step 1 (obligatory)

- Write the piece's object record (README, "Object records") and fill in its brief. The hook checks for it on the sprite scripts and on commands that name the sprite.
- Read the header of `lib/pieceScale.ts`. This pipeline never changes a size rule.
- Check `references/protected.json`. A protected piece (the Ferry Building, `c3b44f7`) is not redrawn or re-keyed without the owner's word in this session.
- The de Young is OFF THE MAP by the owner's ruling (2026-10-04), after the survey render was still too big. Do not redraw, re-key or unhide it without the owner's word.

## Steps

1. **Survey.** Fetch the building's OSM way or relation (outer and inner rings) and every `building:part` slice with `min_height` and `height`. Record long side, short side, axis bearing and height in `references/footprints.json` with the OSM id. Never type a dimension from memory.
2. **Draw from the survey.** Add the piece to `PIECES` in `scripts/sprites/render-footprint-piece.py` (relation, base height, parts radius, palette from the set) and run `python3 scripts/sprites/render-footprint-piece.py <slug>`. The camera is `CAMERA_ELEVATION_DEG = 30`. Do not change it.
   - A guided image-model redraw is allowed only when a survey render is impossible (no footprint in OSM, or the landmark is not a building: a bridge span, a sculpture). State why in chat before generating. After two results wrong in SHAPE, stop prompting and return to the survey.
3. **Camera check.** `python3 "${CLAUDE_PLUGIN_ROOT}/skills/landmark-piece/scripts/camera_check.py" <slug> .tmp/sprites/sf-poster/raw-sf/<slug>.png`. Exit 1 (REFUSED) means the ink box matches a plan view; fix the render, do not key it. Exit 0 (COMPATIBLE) means only that the box could come from the one camera: it is not proof of the camera and says nothing about size, orientation or handedness. Exit 2 (ABSTAIN) means the box cannot tell: measured on 2026-10-04 that is 14 of the 18 surveyed footprints, so for most pieces the camera is judged by eye against the set, and said so.
4. **Key.** `python3 scripts/sprites/key-piece.py <slug> --source <raw> --mirror 0|1`. The mirror flag comes from the landmark's sourced `facing.eastSide` ("right" mirrors). Never run `npm run sprites:key` or `key-poster-pieces.mjs`: they re-key the whole set and overwrite approved pieces.
5. **Anchor.** Set `art.anchor` in `data/boardLandmarks.ts` to the footprint centroid's position in the keyed image (the render prints `centroid_raw_px`; apply the keyer's trim and scale). Set `gps` to the footprint centroid. A piece is pinned at its footprint or ink center, never at the drawing's bottom edge.
6. **Register.** Confirm the entry in `data/board/sf-sprites.json` (the keyer writes it) and the landmark in `data/boardLandmarks.ts`: `sizeM` from the survey, sourced `facing`, the OSM id in a comment. If the piece has a declared axis, add it to `scripts/verify-pieces.mjs`: a survey render expects the foreshortened angle, a flat piece lying along its street (Ferry Building, Legion of Honor) expects the plan angle.
7. **Verify.** `npm run build`, then `node --import tsx scripts/verify-pieces.mjs --rendered <dump.json>` with a dump taken in the user's own Chrome (see `piece-review`). Do not import `verify-pieces.mjs` from another script; importing it launches its own headless browser.
8. **Hand to `piece-review`.** The piece is not fixed until that review's files exist.

## Rejected, do not propose again

From the header of `lib/pieceScale.ts` and the owner's rulings. Naming one of these under a new name is still proposing it.

- Equal box for every piece ("legible and false").
- Area or visual-weight sizing.
- Pure true ground scale (2026-10-02: everything read too small).
- Any zoom growth slower than the map's (the float).
- Runtime rotation of a sprite to its footprint angle (the pieces looked like they were tumbling).
- A plan-view survey render (2026-10-03: disproportionately huge at full zoom-out). The one-camera survey render that replaced it was also rejected by eye on 2026-10-04; a correct camera did not make it the right weight.
- A third image-model attempt at a shape that failed twice.

## Rules

1. Reading the object record, the `pieceScale.ts` header and `protected.json` is obligatory before step 1.
2. Shape wrong twice means stop prompting and draw from the survey.
3. One camera for the art: 30 degrees. Sourced facing stays data, checked by verify-pieces.
4. One piece per run. Snapshot the current sprite and raw to `.agents/<run>/backups/` with a timestamp before overwriting either.
5. When a choice is the owner's (palette, how much tower detail, whether the flat survey style suits the piece), show two to four rendered variations side by side; the owner reacts rather than specifying from scratch.
6. This pipeline changes no sizing constant. If the piece reads too big or too small, that is a ruling for the owner, with the full zoom-out table from `piece-review` in hand.
7. When the owner rules out something this skill does, add it to "Rejected" or Rules in the same turn.

## Output

The keyed sprite, the registered landmark, a passing camera check and verify-pieces run, and the handoff to `piece-review`. Report: what was drawn from which OSM ids, what was checked, what was not.
