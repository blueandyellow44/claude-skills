"""weight_table cases. Read-only on the repo; fixtures in a temp dir. Arg 1: script path. Arg 2 (optional): --legacy."""
import io, json, os, subprocess, sys, tempfile
from PIL import Image
script = sys.argv[1]; legacy = "--legacy" in sys.argv
R = os.environ.get("CITY_WALKS_REPO") or sys.exit("set CITY_WALKS_REPO to the map repo")
D = os.path.join(R, ".agents/continuation-20261003/evidence/rendered-opening-1352x792.json")
E = os.path.join(R, ".agents/city-walks-workflow-20261003/evidence")
B = os.path.join(R, ".agents/continuation-20261003/backups/de-young-keyed-before-survey.png")
d = tempfile.mkdtemp(); dump = json.load(open(D))
def run(*args):
    p = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, cwd=R)
    return p.returncode, p.stdout + p.stderr
def last(out, key):
    return next((ln for ln in out.splitlines() if key in ln), "")[:150]
def write(name, obj):
    p = os.path.join(d, name); json.dump(obj, open(p, "w")); return p
doubled = json.loads(json.dumps(dump))
for r in doubled["rows"]:
    if r["slug"] == "de-young": r["longest"] *= 2; r["width"] *= 2
dd = write("doubled.json", doubled)
if legacy:
    for label, cand in (("bad plan-view", "de-young-PLAN-VIEW-known-bad.png"), ("good one-camera", "de-young-one-camera.png")):
        rc, out = run("--dump", D, "--slug", "de-young", "--candidate", os.path.join(E, cand), "--baseline", B)
        print(f"LEGACY {label}: exit {rc}; {last(out, 'the ink')}")
    rc, out = run("--dump", dd, "--slug", "de-young")
    print(f"LEGACY de Young drawn 2x in the dump (4x the ink on screen): exit {rc}; {last(out, 'the ink')}  <- the miss")
    rc, out = run("--dump", write("empty.json", {"rows": []}), "--slug", "de-young"); print("LEGACY empty dump: exit", rc, "|", out.strip().splitlines()[-1][:110])
    sys.exit(0)
bad = 0
def case(label, got, want):
    global bad; ok = got == want; bad += not ok; print(f"{'ok  ' if ok else 'FAIL'} {label}: exit {got}, want {want}")
rc, out = run("--dump", D, "--slug", "de-young", "--candidate", os.path.join(E, "de-young-PLAN-VIEW-known-bad.png"), "--baseline", B)
case("plan-view de Young vs the piece it replaced -> flag", rc, 1); print("     ", last(out, "DISPLAYED INK"))
rc, out = run("--dump", dd, "--slug", "de-young")
case("dump draws de Young 2x its contract size -> flag", rc, 1); print("     ", last(out, "DUMP CHECK"))
# padding: same art inside a larger transparent canvas, measured from the image -> same drawn ink
src = Image.open(os.path.join(R, "public/images/sprites/sf/city-hall.png")).convert("RGBA")
plain = os.path.join(d, "plain.png"); src.save(plain)
pad = Image.new("RGBA", (src.width + 200, src.height + 200), (0, 0, 0, 0)); pad.alpha_composite(src, (100, 100)); padp = os.path.join(d, "padded.png"); pad.save(padp)
rc, out = run("--dump", D, "--slug", "city-hall", "--candidate", padp, "--baseline", plain)
case("extra transparent padding only -> clear (ink unchanged)", rc, 0); print("     ", last(out, "DISPLAYED INK"))
big = src.resize((src.width * 2, src.height * 2)); bigp = os.path.join(d, "big.png"); big.save(bigp)
rc, out = run("--dump", D, "--slug", "city-hall", "--candidate", bigp, "--baseline", plain)
case("same art at twice the pixel resolution -> clear (resolution is not size)", rc, 0)
tall = src.rotate(90, expand=True); tallp = os.path.join(d, "tall.png"); tall.save(tallp)
rc, out = run("--dump", D, "--slug", "city-hall", "--candidate", tallp, "--baseline", plain)
case("ground piece redrawn upright -> flag (class change)", rc, 1); print("     ", last(out, "FLAG"))
rc, out = run("--dump", D, "--slug", "golden-gate-bridge"); case("bridge (span) -> not reviewed, said plainly", rc, 3)
rc, out = run("--dump", D, "--slug", "coit-tower"); case("piece hidden at full zoom-out -> flag, said plainly", rc, 1); print("     ", last(out, "HIDDEN"))
rc, out = run("--dump", write("empty.json", {"rows": []}), "--slug", "de-young"); case("empty dump -> not reviewed, no crash", rc, 3)
rc, out = run("--dump", write("single.json", {"rows": [r for r in dump["rows"] if r["slug"] == "de-young"]}), "--slug", "de-young"); case("single-target dump -> not reviewed", rc, 3)
rc, out = run("--dump", write("garbage.json", {"nope": 1}), "--slug", "de-young"); case("malformed dump -> bad input", rc, 2)
blank = os.path.join(d, "blank.png"); Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(blank)
rc, out = run("--dump", D, "--slug", "city-hall", "--candidate", blank); case("transparent candidate -> not reviewed", rc, 3)
rc, out = run("--dump", D, "--slug", "ferry-building", "--baseline", "git:c3b44f7")
print("      ferry-building working tree vs the approved c3b44f7:", last(out, "DISPLAYED INK"), "| exit", rc)
print(f"\n11 cases, {bad} wrong"); sys.exit(1 if bad else 0)
