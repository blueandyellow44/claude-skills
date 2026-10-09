---
name: walker-motion
description: "Diagnose and fix how the walker (the map's avatar) moves on the SF City Walks / wallywalks.app map: moonwalking (drifting against the street), walking in place, facing the wrong way, treading too fast, flickering between sheets. Use when the owner says 'moonwalking', 'walks in place', 'faces sideways', 'it does not rush', or anything about the avatar's motion. Built from the 2026-10-06 session that fixed all five; not for drawing the walker (map-character) or sizing pieces (pieceScale rules)."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
---

# walker-motion

## Goal

The walker moves the way a person walks: along the street, facing where it goes, legs moving only when it moves, at a stroll. The owner judges it by eye on the mock walk; the numbers below are how to find the cause before changing anything.

## The model (lib/walkerCycle.ts, components/LiveMap.tsx)

- **Position**: `glidePosition(prev, cur, sinceMs)` slides the marker from the previous GPS fix to the newest over the gap between them (400 to 3000 ms; a relock jumps). The following camera eases to the fix over `glideGapMs(prev, cur)`, THE SAME NUMBER, linearly. Two durations for one object is the moonwalk.
- **Legs**: `advanceStride` moves one frame per `METRES_PER_FRAME` (0.4 m) of glided distance, never sooner than `MIN_FRAME_MS` (400 ms). Time-driven legs walk in place between fixes.
- **Facing**: `facingFor(heading, mapBearing, previous)`: screen angle = heading minus the MAP's bearing (south-up means west is screen right). Side sheet (`walker`, drawn walking right, mirrored for left) for across-screen headings; back sheet (`walker-away`) within 35 degrees of straight up, held until 55 degrees (hysteresis). A parallel commit (`bca1fb5`) keeps the back to the viewer through turns; read it before changing facing.
- **Sheets**: `data/board/sf-sprites.json` entries `walker` and `walker-away`, `frames` per row, same height.

## Diagnose first (one minute, in the user's own Chrome on the mock walk)

`?mockgps=walk&mockwalk=<slug>&speed=2`, select the walk, Walk this. Then sample in the tab, with the tab VISIBLE (hidden tabs throttle timers and stall rAF; sampling there measures nothing):

```js
const f = document.querySelector('.walker-figure'); const m = window.__wwMap; const s = [];
for (let i = 0; i < 8; i++) { const r = f.getBoundingClientRect(); s.push({x: Math.round(r.left), y: Math.round(r.top), frame: f.style.backgroundPosition, facing: f.dataset.facing, mirror: f.style.transform, bearing: Math.round(m.getBearing())}); await new Promise(r => setTimeout(r, 500)); }
JSON.stringify(s)
```

Read it as a table:
- x/y drifting DOWN the screen while frames advance, then jumping up: camera and marker on different durations (moonwalk). Check `glideGapMs` is what `easeTo` receives.
- frames advancing while x/y hold: time-driven legs; the stride must read distance.
- `facing` flipping between `right`/`left`/`away` on a straight street: hysteresis gone, or the bearing sign is wrong (`map.getBearing()` returns -180..180; normalize).
- `mirror` set while x increases: the facing math is against north instead of the map (the original 2026-10-05 moonwalk).

## Rules

1. Never change a constant without the sample above before and after; the owner's eye is the verdict, the sample is the cause.
2. Any new animated thing that follows the walker (camera, halo, prints) takes its duration from `glideGapMs`, not its own constant.
3. Hidden tab = stills only; say "motion not checked" rather than reading a throttled sample.
4. Before touching the sheets or facing, write the object record for `walker` (README, "Object records"; the piece_gate requires it).
5. When the owner rules out something this skill does, add it here in the same turn.

## Done when

The owner has watched the mock walk with the tab in front and said it looks right; the sample shows x/y monotonic along the street, frames advancing only with distance, one facing per straight stretch.
