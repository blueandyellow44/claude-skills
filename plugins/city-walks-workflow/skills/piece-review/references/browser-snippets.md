# Browser snippets for piece-review

Run in the user's own Chrome through claude-in-chrome's `javascript_tool`, in the task tab, on the local candidate. The repo's runtime is fixed to `http://127.0.0.1:3777` (`npm run demo`); the map handle `window.__wwMap` is set only on local hosts (read the condition in `components/LiveMap.tsx` before relying on it). Follow `shared-chrome` first.

## 1. OSM outlines on the live map

The outlines are `.agents/continuation-20261003/evidence/osm-footprints.geojson`. Serve the repo file through the local preview or paste the GeoJSON into the call; then:

```js
const m = window.__wwMap;
if (!m.getSource("osm-fp")) {
  m.addSource("osm-fp", { type: "geojson", data: FOOTPRINTS_GEOJSON });
  m.addLayer({ id: "osm-fp-line", type: "line", source: "osm-fp",
    paint: { "line-color": "#e11", "line-width": 2 } });
}
```

A new piece needs its outline added to that GeoJSON from its OSM way or relation first.

## 2. Full zoom-out dump

Zoom all the way out (the floor), wait for `idle`, then run the `RENDERED_SNIPPET` exported by `scripts/verify-pieces.mjs` (copy the string from the file; do not import the module). Save the returned JSON to `review-<YYYYMMDD>/<slug>/rendered-zoomout.json`. It records `visibility`; a dump taken while `hidden` is not evidence.

## 3. Close zoom against the outline

```js
const m = window.__wwMap;
m.jumpTo({ center: [LON, LAT], zoom: 16.5 });
await new Promise(r => m.once("idle", r));
```

Screenshot. The piece's base must sit inside or along the red outline.

## 4. Zoom motion, frames counted

Only when `document.visibilityState === "visible"`.

```js
const m = window.__wwMap;
const leg = async (to) => {
  let frames = 0, on = true;
  const tick = () => { if (on) { frames++; requestAnimationFrame(tick); } };
  requestAnimationFrame(tick);
  m.easeTo({ zoom: to, duration: 3000 });
  await new Promise(r => m.once("moveend", r));
  on = false;
  return { frames, end_zoom: +m.getZoom().toFixed(2) };
};
m.jumpTo({ center: [LON, LAT], zoom: 13 });
await new Promise(r => m.once("idle", r));
const inn = await leg(16), out = await leg(13);
JSON.stringify({ in: inn, out: out, visibility: document.visibilityState });
```

Write it with `review_gate.py stamp <slug> --motion '<that JSON>'` (it adds the sprite's sha256 and the time; a hand-written file is not bound to the sprite and the gate rejects it). Watch the piece during the pass: it must stay on its streets up to the cap and must not swim. Numbers that end on 16 and 13 prove the pass ran, not that it looked right.
