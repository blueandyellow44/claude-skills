"""The map slide: the Telegraph Hill walk drawn from its real route over
OpenStreetMap streets, south-up like the app, in the carousel's paper and ink."""
import json, math, os, sys
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.environ.get("CAROUSEL_WORK") or os.path.dirname(os.path.abspath(__file__))  # data, fonts, map band
# The app repo (sprites, stop drawings). CAROUSEL_APP, or the current folder when it is the repo root.
APP = os.environ.get("CAROUSEL_APP") or os.getcwd()
if not os.path.isfile(os.path.join(APP, "data", "routes.ts")):
    sys.exit(f"{APP} is not the app repo (no data/routes.ts): set CAROUSEL_APP to the repo root, or run from it")
route = json.load(open(os.path.join(HERE, "route.json")))
osm = json.load(open(os.path.join(HERE, "osm.json")))["elements"]

S = 2                       # supersample, downsized at the end
BW, BH = 1080, 640          # the map band on the slide
W, H = BW * S, BH * S
PAPER, PARK, STREET, MAJOR, CASING = "#F3EAD8", "#CFD8B4", "#FFFDF7", "#F1DEB0", "#DDD0B6"
INK, ROUTE = "#2B2622", "#8C7B9A"

pts = route["path"] + [s["gps"] for s in route["stops"]]
lat0 = sum(p[0] for p in pts) / len(pts)
kx = math.cos(math.radians(lat0))


def raw(lat, lon):
    # South-up (the app's default, bearing 180): east is left, north is down.
    return (-(lon * kx), lat)


xs, ys = zip(*[raw(*p) for p in pts])
pad = 0.22
spanx, spany = max(xs) - min(xs), max(ys) - min(ys)
scale = min(W / (spanx * (1 + 2 * pad)), H / (spany * (1 + 2 * pad)))
cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2


def P(lat, lon):
    x, y = raw(lat, lon)
    return (W / 2 + (x - cx) * scale, H / 2 + (y - cy) * scale)


im = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(im)

for e in osm:
    if e["tags"].get("leisure") == "park" and e.get("geometry"):
        poly = [P(g["lat"], g["lon"]) for g in e["geometry"]]
        if len(poly) > 2:
            d.polygon(poly, fill=PARK)

WIDTH = {"primary": 15, "secondary": 13, "tertiary": 12, "residential": 10,
         "unclassified": 10, "pedestrian": 8, "living_street": 9}
order = ["residential", "unclassified", "living_street", "pedestrian", "tertiary", "secondary", "primary"]
ways = [e for e in osm if e["tags"].get("highway") in WIDTH and e.get("geometry")]
ways.sort(key=lambda e: order.index(e["tags"]["highway"]))
for pass_ in ("casing", "fill"):
    for e in ways:
        h = e["tags"]["highway"]
        line = [P(g["lat"], g["lon"]) for g in e["geometry"]]
        w = WIDTH[h] * S // 2
        if pass_ == "casing":
            d.line(line, fill=CASING, width=w + 4 * S // 2, joint="curve")
        else:
            d.line(line, fill=MAJOR if h in ("primary", "secondary") else STREET, width=w, joint="curve")
for e in osm:
    if e["tags"].get("highway") == "steps" and e.get("geometry"):
        line = [P(g["lat"], g["lon"]) for g in e["geometry"]]
        d.line(line, fill="#CDBFA6", width=3 * S, joint="curve")

# The walk.
path = [P(*p) for p in route["path"]]
d.line(path, fill="#FFFFFF", width=17 * S // 2 + 6, joint="curve")
d.line(path, fill=ROUTE, width=17 * S // 2, joint="curve")

# Street names, drawn upright at each street's own angle.
from make import sans  # noqa: E402  (the carousel's own fonts)
LABELS = {"Union Street", "Filbert Street", "Greenwich Street",
          "Telegraph Hill Boulevard", "Columbus Avenue", "Kearny Street", "Stockton Street"}
done = set()
for e in ways:
    n = e["tags"].get("name")
    if n not in LABELS or n in done or len(e["geometry"]) < 2:
        continue
    g = e["geometry"]
    a, b = P(g[0]["lat"], g[0]["lon"]), P(g[-1]["lat"], g[-1]["lon"])
    if math.dist(a, b) < 260 * S:
        continue
    done.add(n)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    f = sans(15 * S, 500)
    tw = int(d.textlength(n, font=f)) + 8
    t = Image.new("RGBA", (tw, 22 * S), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((4, 0), n, font=f, fill="#7A6E60")
    t = t.rotate(-ang, expand=True, resample=Image.BICUBIC)
    x0, y0 = int(mx - t.width / 2), int(my - t.height / 2)
    if x0 < 10 * S or y0 < 10 * S or x0 + t.width > W - 10 * S or y0 + t.height > H - 10 * S:
        done.discard(n)
        continue
    im.paste(t, (int(mx - t.width / 2), int(my - t.height / 2)), t)

# Coit Tower, the app's own piece, standing on its spot.
coit = next(s for s in route["stops"] if s["id"] == "coit-tower")
spr = Image.open(os.path.join(APP, "public/images/sprites/sf/coit-tower.png")).convert("RGBA")
sh = 210 * S
spr = spr.resize((round(spr.width * sh / spr.height), sh), Image.LANCZOS)
cxp, cyp = P(*coit["gps"])
im.paste(spr, (int(cxp - spr.width / 2), int(cyp - spr.height * 0.92)), spr)

# Numbered stops.
for i, s in enumerate(route["stops"], 1):
    x, y = P(*s["gps"])
    r = 19 * S
    d.ellipse([x - r - 3 * S, y - r - 3 * S, x + r + 3 * S, y + r + 3 * S], fill="#FFFFFF")
    d.ellipse([x - r, y - r, x + r, y + r], fill=ROUTE)
    f = sans(20 * S, 700)
    t = str(i)
    d.text((x - d.textlength(t, font=f) / 2, y - 13 * S), t, font=f, fill="#FFFFFF")

d.line([(0, H - 2 * S), (W, H - 2 * S)], fill="#D8CBB2", width=3 * S)
im = im.resize((BW, BH), Image.LANCZOS)
im.save(os.path.join(HERE, "map-band.png"))
print("map band", im.size)
