---
name: map-repair
description: "The methods that fixed a sister map project's map on 2026-10-04, for any tile-stitched storybook map: erase an invented feature or ghost, draw a missing road or a clean junction in the map's own hand, put the cart loop on the painted road, move/rotate/resize a piece, sharpen the whole map without redrawing it, and keep pieces as sharp overlays. Use when the owner says 'ghost', 'glitch', 'smudge', 'erase the X', 'road lines show under trees', 'sloppy connection', 'missing road', 'the loop is off the road', 'the cart drives through trees', 'the map is fuzzy', 'sharper', 'pieces are fuzzy', 'too big', 'at an angle', or reports a map defect with a screenshot. Run map-preflight after. Not for drawing a new piece (landmark-piece) or a person (map-character)."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# map-repair

## Goal

Each map defect fixed by the cheapest method that cannot drift: code where the edit is mechanical, a mask-only Gemini repaint where it needs the map's hand, never a whole-map redraw. Every pixel outside the fix stays byte-identical, and the fix is seen at full size before and after.

The scripts named below (repair.py, roads.py, surgery.py, place-pieces.py, superres.py, trace-loop.py and the rest) are that project's own pipeline and are not shipped with this plugin; the methods are what carries over.

## Before any edit

- Snapshot every image you will change to `.backups/<timestamp>/` (nothing that existed is ever unrecoverable).
- Confirm the chain reproduces today's map byte-for-byte from its caches before changing a step (for example: `map.png -> repair.py -> roads.py -> surgery.py -> place-pieces.py -> export-map-data.py -> compose-frame.py`; compare md5 of map-pieces.png).
- Locate the reported screenshot on the map by template matching against a downsized copy of the map (scales 0.08-0.6); do not guess coordinates.

## Methods (pick by the defect)

| defect | method | why |
|---|---|---|
| invented feature among trees (ghost tree, extra gravestones, smudge) | repair.py region: blank the mask in red, Gemini fills it, copy back only the feathered mask; crop from the image as it stands so earlier regions stay identical | a clone from beside it pasted a second ghost (surgery.py BOXES) |
| ghost strokes on OPEN ground (paddock tracks) | inpaint in code (surgery.py `deghost`: strokes darker than the local median wash inside a polygon, then cv2.inpaint) | Gemini planted trees there under both a woodland and a grass-only prompt |
| missing road, bad junction, faint strokes in a road bed | roads.py band along a polyline in red, Gemini draws the road in the map's hand, copy back only the band; magenta patches for ground | a road inked by code read as discolored and sloppy |
| loop off the road | tools/trace-loop.py: exact band centerlines where roads.py drew, hand guides where not (row-scan the ink edges to find the middle), then nudge each point to the middle of the NEAREST ink edge on each side when that gap is road width | Google's line rode edges and crossed trees; "move to the clearest ground" jumps off the road |
| piece too big, angled, wrong spot | place-pieces.py SIZES (meters), POSITION_OVERRIDES, ROTATE (measure the drawing's angle with cv2.minAreaRect), FLIP | deterministic; quail coveys 2.6 m, hunt quail 10 map px |
| piece fuzzy at zoom | pieces are overlays: place-pieces.py writes public/map/pieces/*.webp at 6 px per map px plus lib/pieces.json; the app lays them on the exact baked rectangle | baked at 7 px/m they blur at 2.5x zoom |
| whole map soft at zoom | superres.py: fal aura-sr per 512 px tile with 64 px context, content-keyed cache, feathered cores; drift check (phase correlation per 256 px, worst must be under 0.5 px) and sharpness vs bicubic; compose-frame ships 2x tiles that load only in view | a Gemini redraw re-invents everything repair.py removed |

Rules that bit:
- Re-roll a Gemini region at most once; keep rejects in `<cache>/rejected/` and say why in the code.
- No color boost on small gray animals: it turned quail rust red.
- Python from python.org has no CA store: pass `ssl.create_default_context(cafile=certifi.where())`.
- Never `sed` a line holding `#` with `#` as the delimiter; use a Python replace.

## Verify (every fix)

1. Before/after crops at 2-4x of every changed spot, side by side, looked at.
2. "Pixels changed outside the masks: 0" from each script.
3. The loop overlaid on the map at each changed road, and `map-preflight` loop_on_road / ghost_strokes.
4. In the running app at full zoom, in the user's own Chrome, one tab.
5. One commit per concern; deploy only on the owner's word, then poll the live content and curl the headers.
