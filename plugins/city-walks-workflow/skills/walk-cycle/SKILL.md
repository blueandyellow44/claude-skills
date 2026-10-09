---
name: walk-cycle
description: "Make or remake an animated sprite sheet for a map character on SF City Walks / wallywalks.app from one approved drawing: walk-cycle frames by image EDITS of the approved pose, thresholded to ink, aligned on one baseline, indexed with a frames count. Use when the owner wants a character animated, a new facing (back view, side view), or says the cycle looks wrong. Built from the walker's silhouette on 2026-10-06; for a new person's likeness use map-character first."
allowed-tools:
  - Bash
  - Read
  - Write
---

# walk-cycle

## Goal

A sheet of N frames in one row, same height, feet on one line, one flat ink color, that reads as walking at 44 px, built in one round and shown to the owner as a contact sheet before it is wired.

## Method

1. Object record first (README, "Object records"): the piece_gate blocks sprite scripts without it, and the record says what the owner approved.
2. Reference: the approved drawing on cream at 4x (`.agents/<work>/ref.png`), never the raw transparent PNG (the model misreads alpha).
3. Frames by EDITING the reference with `scripts/_gemini-gen.mjs` (`gemini-2.5-flash-image`), three tries per phase in parallel, prompt shape: "Edit IMAGE 1 ... Keep everything identical: ... Change ONLY the figure's legs and arms to this phase of the walking stride: <phase>." A flat silhouette needs only three new side phases (closing, passing, opening) plus the approved pose as frame 0; the back view needs two (apart, together) plus their mirrors. Phases the model copies instead of changing are dropped, not re-prompted more than once.
4. `python3 scripts/sprites/walk-cycle.py walker check <frames>` rejects a frame with more than one ink blob or an aspect far from the approved pose; `... walker build <frame0> <frame1> ... --out <dir>` thresholds to the ink color, scales to 192 px, pads to a common box, pastes feet on one baseline, writes the sheet and a 2x contact sheet with the approved drawing first.
5. LOOK at the contact sheet (Read tool). Then copy the sheet to `public/images/sprites/sf/<slug>.png` and write the index entry in `data/board/sf-sprites.json` with `w` = frame width, `frames` = N, `sha256`, and a `note` naming the source and the frames in order. Sheets of one character share one height.
6. Playback is distance-driven (lib/walkerCycle.ts); see `walker-motion` before changing how frames advance.

## Rules

1. Edits, never compositions, for every frame after the approved one (map-character's lesson: the model copies the reference's angle and ignores angle words).
2. The approved drawing is frame 0 byte-derived; it is never redrawn.
3. The first positional argument of `walk-cycle.py` is the slug, so the piece_gate can match the record.
4. When the owner rules out something this skill does, add it here in the same turn.
