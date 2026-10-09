---
name: map-preflight
description: "Catch what an outside audit would catch on a hand-drawn walking-map app, BEFORE the audit or a deploy: the cart loop off the painted road, road color breaks, ghost strokes, small animals drawn large, overlapping _headers rules, files in public/ nothing uses, text contrast, hunt targets that give themselves away, small tap targets, dev-server origins; then the browser checks a script cannot do (focus under the bar, desktop blank paper, true 390 px viewport, pieces sharp at full zoom). Use when the owner says 'preflight', 'check it before the audit', 'is it ready to deploy', 'catch these before an audit', 'run the checks', or before any deploy of a City Walks map. Not the repairs themselves (map-repair) and not a piece's art review (piece-review)."
allowed-tools:
  - Bash
  - Read
---

# map-preflight

## Goal

Every finding an outside audit of a sister map project made on 2026-10-04 is found here first, by a script or by a named look, so an audit only finds new things.

## Why this exists

The audit caught 17 defects nothing in the build had caught: the loop crossing trees, a ghost tree, a duplicate set of gravestones, an empty sign oval, a place landing under the bar, blank paper on desktop, 2.9:1 text, hunt quail announced to screen readers, a contradictory Cache-Control, nine skipped photos still served. The ask that followed: skills that catch these things before an audit. Later the same day, screenshots caught four more: ghost road strokes under trees, ghost tracks across a paddock, a sloppy road junction, a garden angled into a house. The script checks below were each run against the morning's known-bad state (git 44620f5) and seen to FAIL or WARN on it before they were trusted.

## Step 1: run the script

```
python3 <this skill>/scripts/preflight.py <repo>            # all checks
python3 <this skill>/scripts/preflight.py <repo> --only loop_on_road,headers_overlap
```

Exit 1 on any FAIL. Paths are in `CFG` at the top of the script (the sister project's layout); `piece_scale` has the project's px-per-meter. Spots the owner has ruled stay as they are go in `<repo>/.preflight-accept.json` with the ruling quoted in `why`; never accept a spot to make the run pass. Check names are identifiers: `road_continuity_colour` keeps its spelling so existing accept files still match.

| check | catches | proven on |
|---|---|---|
| loop_on_road | cart line off the road bed (crossing trees, riding an edge); FAIL at 100 px, WARN shorter (often a tree drawn over the road: look) | Google loop of 44620f5: 54% on road, FAIL |
| road_continuity_colour | a long stretch of road bed in another color (canopy, a seam) | top lane under the tree row |
| ghost_strokes | faint stray strokes on the road bed (erasure traces) | bend ghost on the pre-repaint map |
| piece_scale | small animals over 3 m (read as stickers) | owls at 4.9 m |
| headers_overlap | one header set by two matching `_headers` rules (Cloudflare joins them) | 44620f5 `/*` + `/_next/static/*` |
| public_unreferenced | files in public/ that no code or data names | the nine skipped photos and the 6 MB basemap |
| text_contrast | text color tokens under 4.5:1 on the card | --muted 3.56, --sunset 2.88 |
| hidden_items_announced | hunt targets in the tab order or announced | "A hidden quail" |
| tap_targets | round buttons under 44 px | h-10 zoom buttons |
| dev_origins | dev server not reachable from the address it will be opened at | 127.0.0.1 not allowed |

## Step 2: look, because no script sees these

Run the app (`npm run dev`, open http://localhost:<port>, never 127.0.0.1 unless it is allowed) in the user's own Chrome, one tab (shared-chrome).

1. **True phone width.** Window resizes lie. Load the app in an iframe of exactly 390x844 from a same-origin page and read `innerWidth` from inside the frame; it must say 390. Delete the harness page after.
2. **Focus lands in the open area.** With the bar collapsed, tap three places (one near each map edge) and measure: the place's center must sit between the title strip and the bar's top AFTER the bar opens. Same on desktop with a place near the bottom-right edge.
3. **No blank paper.** Desktop with a card open, and at minimum zoom: the map covers the viewport.
4. **Sheet fully open:** zoom buttons hidden; the bar's words say what the next tap does.
5. **Full zoom, by eye, at every piece and every road join:** pieces sharp and in proportion (quail are birds, not stickers), nothing painted twice near a piece (the script's twin check could not see a twin drawn in another style, so this is a look), every road joins cleanly, no road lines showing through trees, no tracks across open ground, pieces square to the buildings they sit beside.
6. **Loading:** throttle to Slow 4G once: the map area says it is loading, never blank paper.

Report each check as PASS / WARN / FAIL with what was looked at, then the WARNs that need the owner's ruling as yes/no questions.

## Notes

- A FAIL that cannot be fixed without changing a ruling goes to the owner as a question, never into the accept file.
- After any map art change, re-run `loop_on_road` and `ghost_strokes`: repaints move roads by a few pixels.
- `_headers` values can only be confirmed with `curl -sI` after a deploy; state the expected values before it.
