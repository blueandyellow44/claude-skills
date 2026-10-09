---
name: linkedin-carousel
description: Build a LinkedIn carousel (a 1080x1350 PDF document post) for wallywalks.app from the app's own pencil drawings, fonts, story text and real route, drawn in code rather than screenshotted, then stage it in the owner's LinkedIn composer for the owner to post. Use when the owner asks for a carousel, slides, "compelling screenshots", a map image, or images for a LinkedIn post about the walks. Never posts.
---

# linkedin-carousel

## Goal

Six full-resolution slides that look like one object, every word taken from the app, staged in the composer beside the owner's post text, with the owner's click as the only way it goes live.

## Why this exists

2026-10-06, the first wallywalks.app post. Browser screenshots came out about 312 px wide in a phone frame and a backgrounded tab would not draw the map at all. Drawing the slides in code fixed both, and when the session later went back to the browser for the map, that was a step backward. The code-built set is what was posted.

## Steps

1. **Text first, from the app.** Pick the walk (default: one sample walk, all its stops) and one stop whose `wallyStory` gives the app's own story quote. Export from the repo root:
   `npx tsx ${CLAUDE_PLUGIN_ROOT}/skills/linkedin-carousel/scripts/export_walk.mts <walk-slug> "<stop name>" <workdir>`
   Re-export right before building: other sessions rewrite stop text (on 2026-10-06 every stop was retold mid-session).
2. **Fonts.** The app's own: Newsreader (roman and italic) and Inter, variable TTFs from github.com/google/fonts (`ofl/newsreader`, `ofl/inter`), saved into the workdir as `Newsreader.ttf`, `NewsreaderItalic.ttf`, `Inter.ttf`.
3. **Streets.** Overpass for the walk's bbox plus margin (`way["highway"]` and `way["leisure"="park"]`, `out geom`) into `<workdir>/osm.json`. overpass-api.de answered 406; overpass.kumi.systems worked with a User-Agent.
4. **Build.** `CAROUSEL_APP=<repo root> CAROUSEL_WORK=<workdir> CAROUSEL_OUT=<out> python3 .../scripts/mapslide.py`, then the same env with `make.py` (`CAROUSEL_APP` may be left out when run from the repo root). Output: `slide-1..6.png` and one PDF. The stop slides are chosen by stop id inside `make.py` `main()`; change them for another walk.
5. **Look at it before the owner does.** Contact sheet, then read every slide against the one before it. The check that caught a real problem: a quote that argues with the neighboring picture (a line saying a place is not its door and window, right after a drawing of the door and the window). Quotes keep their context or get swapped.
6. **Stage, never post.** In the owner's composer tab: `+` (Expand content types), Document, then set an `aria-label` on the hidden `input[type=file]` with JS, `find` it, `file_upload` the PDF, type a title without a colon, Done. To replace a PDF: the document's Edit link, the X on the file, upload again, Done. Verify the post text survived (length and a phrase) after every change.

## Rules

1. Every word on a slide is the app's own text, verbatim, with the app's attribution. No new copy under the owner's name.
2. One aesthetic: paper `#F3EAD8`, ink, the walk's own color, the app's fonts. The map is drawn south-up like the app, with the app's own piece standing on its stop.
3. No browser screenshots in the set. If one is unavoidable, the tab must be visible (a hidden tab does not render the map) and nothing is upscaled.
4. Never press Post. "It's ready" is not "post it".
5. A cut feature leaves the slides and the post text in the same pass (the postcard style, cut 2026-10-06).

## Verified

2026-10-06: the scripts, run end to end in a fresh folder from the export step, reproduced all six posted slides byte for byte. The `CAROUSEL_APP` setting was added after that run; it changes where the scripts find the app, not what they draw.
