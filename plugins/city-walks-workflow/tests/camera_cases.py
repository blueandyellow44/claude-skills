"""Tallies for camera_check across all surveyed footprints. Pass the script path. Read-only on the repo."""
import collections, json, math, os, subprocess, sys, tempfile
from PIL import Image
script = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
fp = json.load(open(os.path.join(ROOT, "skills/landmark-piece/references/footprints.json")))
slugs = [k for k in fp if not k.startswith("_")]
REPO = os.environ.get("CITY_WALKS_REPO") or sys.exit("set CITY_WALKS_REPO to the map repo")
d = tempfile.mkdtemp()
def run(slug, png):
    return subprocess.run([sys.executable, script, slug, png, "--allow-protected"], capture_output=True, text=True).returncode
def box(w, h, name):
    im = Image.new("RGBA", (int(w) + 20, int(h) + 20), (0, 0, 0, 0)); im.paste((90, 60, 40, 255), (10, 10, 10 + int(w), 10 + int(h)))
    p = os.path.join(d, name + ".png"); im.save(p); return p
def dims(s):
    f = fp[s]; L, S, H = f["long_m"], f["short_m"], f.get("height_m") or 0; phi = math.radians(abs(90 - f["axis_bearing_deg"]))
    return L * abs(math.cos(phi)) + S * abs(math.sin(phi)), L * abs(math.sin(phi)) + S * abs(math.cos(phi)), H
def K(s, target=600):
    """Scale so the larger side is `target` px: big enough that whole-pixel rounding does not move a ratio."""
    w, dp, _ = dims(s); return target / max(w, dp)
def tally(label, maker):
    c = collections.Counter({0: 0, 1: 0, 2: 0}); who = collections.defaultdict(list)
    for s in slugs:
        rc = run(s, maker(s)); c[rc] += 1; who[rc].append(s)
    print(f"{label}: compatible {c[0]}, refused {c[1]}, abstained {c[2]}" + (f", CRASHED {sum(v for k, v in c.items() if k not in (0, 1, 2))}" if any(k not in (0, 1, 2) for k in c) else ""))
    return c, who
cur, who = tally("current 18 sprites       ", lambda s: os.path.join(REPO, "public/images/sprites/sf", s + ".png"))
print("   refused:", who[1])
plan, pw = tally("synthetic PLAN boxes     ", lambda s: box(dims(s)[0] * K(s), dims(s)[1] * K(s), s + "-plan"))
big, _ = tally("plan boxes, 3x the size  ", lambda s: box(dims(s)[0] * K(s, 1800), dims(s)[1] * K(s, 1800), s + "-big"))
cam, _ = tally("expected-camera boxes    ", lambda s: box(dims(s)[0] * K(s), (dims(s)[1] * 0.5 + dims(s)[2] * 0.866 * 0.5) * K(s), s + "-cam"))
t = os.path.join(d, "transparent.png"); Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(t)
rc = run("city-hall", t); print("fully transparent input: exit", rc)
bad = []
if plan[0]: bad.append(f"{plan[0]} plan-view box(es) called compatible: {pw[0]}")
if cam[1]: bad.append(f"{cam[1]} expected-camera box(es) refused")
if rc != 2: bad.append("transparent input did not abstain")
if plan != big: bad.append("verdict changed with size alone (the check must be, and say it is, blind to size)")
print("\nRESULT:", "; ".join(bad) if bad else "no plan box accepted, no camera box refused, transparent input abstains; size-blind as documented")
sys.exit(1 if bad else 0)
