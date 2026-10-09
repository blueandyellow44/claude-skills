"""Pre-audit checks for a hand-drawn walking map app (the layout of a sister
map project by default; see CFG). Every check here is one an outside audit caught on 2026-10-04 that
nothing caught first. Deterministic: no model, no network.

usage: python3 preflight.py [repo] [--only name,name] [--json]
Exit 1 if any check FAILs. WARN never fails the run; it names something to look at.
"""

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(next((a for a in sys.argv[1:] if not a.startswith("--")), ".")).resolve()
ONLY = next((a.split("=", 1)[1] if "=" in a else sys.argv[sys.argv.index(a) + 1] for a in sys.argv if a.startswith("--only")), None)
CFG = {  # paths, relative to the repo
    "map_bare": "stitch/map-fixed.png",      # the map with no pieces on it
    "map_data": "lib/map-data.json",          # {"loop": [[x, y], ...]} in map px
    "pieces": "lib/pieces.json",              # [{"id", "x", "y", "w", "h", "src"}]
    "headers": "public/_headers",
    "css": "app/globals.css",
    "public": "public",
    "code": ["app", "components", "lib"],
    "next_config": "next.config.mjs",
}
INK = 130         # darker than this (0-255 gray) is an ink line
ROAD = (16, 42)   # a road's width between its two ink edges, map px
SEARCH = 24       # how far either side of the loop to look for the road, px
results = []


def report(name, status, msg, detail=None):
    results.append({"check": name, "status": status, "msg": msg, "detail": detail or []})


def check(fn):
    if ONLY and fn.__name__ not in ONLY.split(","):
        return fn
    try:
        fn()
    except FileNotFoundError as e:
        report(fn.__name__, "SKIP", f"missing {e.filename}")
    return fn


def resample(pts, step):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) // step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return out


def road_offset(img, pts, i):
    """Signed offset from point i to the middle of the nearest road (two ink
    edges ROAD apart with a clean light bed between), or None if no road."""
    h, w = img.shape
    x, y = pts[i]
    (ax, ay), (bx, by) = pts[max(i - 2, 0)], pts[min(i + 2, len(pts) - 1)]
    L = math.hypot(bx - ax, by - ay) or 1
    nx, ny = -(by - ay) / L, (bx - ax) / L
    val = lambda t: img[int(round(y + ny * t)), int(round(x + nx * t))] if 0 <= x + nx * t < w and 0 <= y + ny * t < h else 255
    T = range(-SEARCH - ROAD[1], SEARCH + ROAD[1] + 1)
    edges = []
    for t in T:
        if val(t) < INK:
            if edges and t - edges[-1][-1] <= 2:
                edges[-1].append(t)
            else:
                edges.append([t])
    cs = [sum(e) / len(e) for e in edges]
    best = None
    for p in range(len(cs)):
        for q in range(p + 1, len(cs)):
            if ROAD[0] <= cs[q] - cs[p] <= ROAD[1] and abs((cs[p] + cs[q]) / 2) <= SEARCH:
                bed = [val(t) for t in np.arange(cs[p] + 3, cs[q] - 2)]
                if bed and min(bed) >= INK and np.mean(bed) > 200:
                    mid = (cs[p] + cs[q]) / 2
                    if best is None or abs(mid) < abs(best):
                        best = mid
    return best


def runs(flags, pts, min_len):
    """Stretches of consecutive True flags at least min_len samples long."""
    out, start = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start >= min_len:
                out.append((start, i - 1))
            start = None
    return [(tuple(round(c) for c in pts[a]), tuple(round(c) for c in pts[b]), b - a + 1) for a, b in out]


def accepted(name, x, y):
    """Spots the owner has ruled stay as they are: <repo>/.preflight-accept.json,
    [{"check": name, "box": [x0, y0, x1, y1], "why": "..."}]."""
    f = REPO / ".preflight-accept.json"
    if not f.exists():
        return False
    return any(a["check"] == name and a["box"][0] <= x <= a["box"][2] and a["box"][1] <= y <= a["box"][3] for a in json.loads(f.read_text()))


@check
def loop_on_road():
    """The cart line runs on a road bed: light under it, and clear of ink lines
    (riding an edge or crossing a tree both fail)."""
    import cv2
    img = np.asarray(Image.open(REPO / CFG["map_bare"]).convert("L"))
    ink = (img < 115).astype(np.uint8)
    clear = cv2.distanceTransform(1 - ink, cv2.DIST_L2, 3)   # px to the nearest ink
    loop = json.loads((REPO / CFG["map_data"]).read_text())["loop"]
    pts = resample([tuple(p) for p in loop] + [tuple(loop[0])], 10)
    off = []
    for x, y in pts:
        xi, yi = int(round(x)), int(round(y))
        bed = np.median(img[yi - 2:yi + 3, xi - 2:xi + 3])
        off.append((bed < 205 or clear[yi, xi] < 4) and not accepted("loop_on_road", x, y))
    bad = runs(off, pts, 4)                                      # 40 px or more
    share = 1 - sum(off) / len(off)
    # 100 px or more off the road fails; shorter is usually the cart passing
    # under a drawn tree or drifting to an edge: look, then accept or fix.
    long = [r for r in bad if r[2] >= 10]
    report("loop_on_road", "FAIL" if long else ("WARN" if bad else "PASS"), f"{share:.0%} of the loop on a clear road bed; {len(bad)} stretch(es) off it",
           [f"{a} -> {b} ({n * 10} px)" for a, b, n in bad])


@check
def road_continuity_colour():
    """The road bed under the loop is one color; a dark stretch is road under canopy or a seam."""
    img = np.asarray(Image.open(REPO / CFG["map_bare"]).convert("RGB")).astype(float)
    loop = json.loads((REPO / CFG["map_data"]).read_text())["loop"]
    pts = resample([tuple(p) for p in loop] + [tuple(loop[0])], 20)
    cols = np.array([np.median(img[int(y) - 3:int(y) + 4, int(x) - 3:int(x) + 4].reshape(-1, 3), axis=0) for x, y in pts])
    med = np.median(cols, axis=0)
    d = np.linalg.norm(cols - med, axis=1)
    flags = [v > 60 and not accepted("road_continuity_colour", *pts[i]) for i, v in enumerate(d)]
    bad = runs(flags, pts, 5)                                  # 100 px of clearly different bed
    report("road_continuity_colour", "WARN" if bad else "PASS", f"road bed median RGB {med.round().astype(int).tolist()}; {len(bad)} long off-color stretch(es)",
           [f"{a} -> {b} ({n * 20} px)" for a, b, n in bad])


@check
def ghost_strokes():
    """Faint strokes on a road bed: erased roads, half-erased lines, edits that left a trace."""
    img = np.asarray(Image.open(REPO / CFG["map_bare"]).convert("L")).astype(int)
    loop = json.loads((REPO / CFG["map_data"]).read_text())["loop"]
    pts = resample([tuple(p) for p in loop] + [tuple(loop[0])], 10)
    import cv2
    bg = cv2.medianBlur(img.astype(np.uint8), 21).astype(int)
    faint = ((bg - img) > 14) & (img > INK)    # darker than the wash, lighter than ink
    hits = []
    for i in range(len(pts)):
        off = road_offset(img.astype(float), pts, i)
        if off is None:
            continue
        x, y = pts[i]
        (ax, ay), (bx, by) = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        L = math.hypot(bx - ax, by - ay) or 1
        nx, ny = -(by - ay) / L, (bx - ax) / L
        cx, cy = x + nx * off, y + ny * off
        bed = faint[int(cy) - 4:int(cy) + 5, int(cx) - 4:int(cx) + 5]
        hits.append(bed.mean() > 0.12 and not accepted("ghost_strokes", cx, cy))
    found = runs(hits, pts, 3)
    report("ghost_strokes", "WARN" if found else "PASS", f"{len(found)} road-bed stretch(es) with faint stray strokes",
           [f"near {a} -> {b}" for a, b, _ in found])


@check
def piece_scale():
    """Pieces against their real size: small animals over ~3 m read as stickers."""
    pieces = json.loads((REPO / CFG["pieces"]).read_text())
    px_m = 7.0759  # map px per meter of the sister project; set per project
    small = {"quail", "owls"}   # small-animal piece ids, and any id that starts "<one of these>-"
    is_small = lambda i: i in small or i.split("-", 1)[0] in small
    big = [f"{p['id']}: {max(p['w'], p['h']) / px_m:.1f} m" for p in pieces if is_small(p["id"]) and max(p["w"], p["h"]) / px_m > 3]
    report("piece_scale", "WARN" if big else "PASS", "small animals within 3 m" if not big else "small animals drawn large", big)


@check
def headers_overlap():
    """No header set by two _headers rules that match one path (Cloudflare joins them)."""
    rules, cur = [], None
    for line in (REPO / CFG["headers"]).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            cur = (line.strip(), {})
            rules.append(cur)
        elif ":" in line and cur and not line.strip().startswith("!"):
            k, v = line.strip().split(":", 1)
            cur[1][k.strip().lower()] = v.strip()

    def overlaps(a, b):
        ra = "^" + re.escape(a).replace(r"\*", ".*") + "$"
        rb = "^" + re.escape(b).replace(r"\*", ".*") + "$"
        sample = lambda p: p.replace("*", "x/y.js")
        return re.match(ra, sample(b)) or re.match(rb, sample(a))
    bad = [f"{a} and {b} both set {k}" for i, (a, ha) in enumerate(rules) for b, hb in rules[i + 1:] for k in ha.keys() & hb.keys() if overlaps(a, b)]
    report("headers_overlap", "FAIL" if bad else "PASS", f"{len(rules)} rules; {len(bad)} overlap(s)", bad)


@check
def public_unreferenced():
    """Everything in public/ is something the app uses; anything else is served for nobody."""
    pub = REPO / CFG["public"]
    code = "\n".join(f.read_text(errors="ignore") for d in CFG["code"] for f in (REPO / d).rglob("*") if f.suffix in {".ts", ".tsx", ".json", ".css", ".mjs"})
    keep = {"_headers", "robots.txt", "favicon.ico"}
    tops = sorted({p.relative_to(pub).parts[0] for p in pub.rglob("*") if p.is_file()} - keep)
    loose = []
    for t in tops:
        if (pub / t).is_dir():
            subs = sorted({p.relative_to(pub / t).parts[0] for p in (pub / t).rglob("*") if p.is_file()})
            # A folder entry counts as used only if its name appears in code or
            # data; a path built from a pattern (/pictures/${id}) proves nothing.
            loose += [f"/{t}/{s}" for s in subs if not re.search(rf"(?<![\w-]){re.escape(Path(s).stem)}(?![\w-])", code)]
        elif t not in code:
            loose.append(f"/{t}")
    size = sum(f.stat().st_size for l in loose for f in ([pub / l.lstrip('/')] if (pub / l.lstrip('/')).is_file() else (pub / l.lstrip('/')).rglob('*')) if f.is_file())
    report("public_unreferenced", "WARN" if loose else "PASS", f"{len(loose)} served path(s) nothing references ({size / 1e6:.1f} MB)", loose[:40])


@check
def text_contrast():
    """Text color tokens reach 4.5:1 on the card color."""
    css = (REPO / CFG["css"]).read_text()
    tok = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", css))

    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    bg = tok.get("card") or tok.get("paper")
    bad = []
    code = "\n".join(f.read_text(errors="ignore") for d in CFG["code"] for f in (REPO / d).rglob("*.tsx")) + css
    for name in tok:
        used = re.search(rf"\btext-{name}\b", code) or re.search(rf"(?<![-\w])color:\s*var\(--{name}\)", code)
        if used and bg and name not in ("card", "paper"):
            a, b = sorted((lum(tok[name]), lum(bg)), reverse=True)
            r = (a + 0.05) / (b + 0.05)
            if r < 4.5:
                bad.append(f"--{name} {tok[name]} is {r:.2f}:1 on --card {bg}")
    report("text_contrast", "FAIL" if bad else "PASS", f"{len(bad)} text token(s) under 4.5:1", bad)


@check
def hidden_items_announced():
    """Hunt targets are not in the tab order or announced (that gives the hunt away)."""
    hits = []
    for f in (REPO / "components").rglob("*.tsx"):
        s = f.read_text()
        if re.search(r"hidden|hunt", f.stem, re.I) and "aria-label" in s and "tabIndex" not in s:
            hits.append(f"{f.relative_to(REPO)}: hunt items carry aria-label with no tabIndex/aria-hidden for unfound ones")
        for m in re.finditer(r"aria-label=\{[^}]*\"A hidden", s):
            hits.append(f"{f.relative_to(REPO)}: announces '{m.group(0)[:60]}'")
    report("hidden_items_announced", "FAIL" if hits else "PASS", f"{len(hits)} giveaway(s)", hits)


@check
def tap_targets():
    """Fixed-size buttons are at least 44 px (h-11 / w-11)."""
    hits = []
    for f in (REPO / "components").rglob("*.tsx"):
        for m in re.finditer(r'className="[^"]*\b(h-(\d+))\s+w-(\d+)[^"]*rounded-full[^"]*"', f.read_text()):
            if int(m.group(2)) < 11:
                hits.append(f"{f.relative_to(REPO)}: {m.group(1)} ({int(m.group(2)) * 4} px)")
    report("tap_targets", "FAIL" if hits else "PASS", f"{len(hits)} round button(s) under 44 px", hits)


@check
def dev_origins():
    """The dev server accepts the hosts it will be opened from (localhost, the LAN)."""
    s = (REPO / CFG["next_config"]).read_text()
    m = re.search(r"allowedDevOrigins:\s*\[([^\]]*)\]", s)
    origins = re.findall(r"[\"']([^\"']+)[\"']", m.group(1)) if m else []
    missing = [h for h in ("127.0.0.1",) if h not in origins]
    report("dev_origins", "WARN" if missing else "PASS", f"allowed: {origins or 'none'}; open the dev server at localhost, not {', '.join(missing)}" if missing else f"allowed: {origins}")


if "--json" in sys.argv:
    print(json.dumps(results, indent=1))
else:
    for r in results:
        print(f"{r['status']:5} {r['check']}: {r['msg']}")
        for d in r["detail"][:12]:
            print(f"        {d}")
sys.exit(1 if any(r["status"] == "FAIL" for r in results) else 0)
