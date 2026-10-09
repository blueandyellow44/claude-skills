"""Evidence, re-entry and clock cases for the gates. Uses a throwaway fixture repo; touches nothing real."""
import datetime, hashlib, importlib.util, json, os, subprocess, sys, tempfile, types
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
spec = lambda name, rel: importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
rg = importlib.util.module_from_spec(spec("review_gate", "skills/piece-review/scripts/review_gate.py")); spec("review_gate", "skills/piece-review/scripts/review_gate.py").loader.exec_module(rg)
sys.modules["review_gate"] = rg
pg = importlib.util.module_from_spec(spec("piece_gate", "hooks/piece_gate.py")); spec("piece_gate", "hooks/piece_gate.py").loader.exec_module(pg)
from PIL import Image
import random

results = []
def case(label, got, want):
    results.append((label, got == want)); print(f"{'ok  ' if got == want else 'FAIL'} {label}: got {got!r}, want {want!r}")

fx = tempfile.mkdtemp(prefix="cw-fixture-")
slug = "de-young"
sd = os.path.join(fx, "public/images/sprites/sf"); os.makedirs(sd)
def sprite(seed):
    random.seed(seed); im = Image.new("RGBA", (60, 40), (0, 0, 0, 0))
    for _ in range(300): im.putpixel((random.randrange(60), random.randrange(40)), (120, 60, 40, 255))
    im.save(os.path.join(sd, slug + ".png"))
sprite(1)
now = datetime.datetime.now().astimezone()
def folder(day=0):
    d = os.path.join(fx, "review-" + (now - datetime.timedelta(days=day)).strftime("%Y%m%d"), slug); os.makedirs(d, exist_ok=True); return d
def noise(path):
    random.seed(7); im = Image.new("RGB", (640, 400)); im.putdata([(random.randrange(255),) * 3 for _ in range(640 * 400)]); im.save(path)
def full(d, when=None, sha=None):
    when = when or now
    sha = sha or rg.sha_file(rg.sprite_path(slug, fx))
    json.dump({"visibility": "visible", "innerWidth": 1352, "rows": [{"slug": slug, "longest": 36, "width": 36, "shown": True}, {"slug": "city-hall", "longest": 32, "width": 32, "shown": True}]}, open(os.path.join(d, "rendered-zoomout.json"), "w"))
    dsha = rg.sha_file(os.path.join(d, "rendered-zoomout.json"))
    open(os.path.join(d, "zoomout-table.md"), "w").write(f"# Full zoom-out size table\n\n| piece | shown |\n|---|---|\n| {slug} | yes |\n\ncandidate-sha256: {sha}\ndump-sha256: {dsha}\ngenerated: {when.isoformat(timespec='seconds')}\n\nclear\n")
    noise(os.path.join(d, "zoomout.png")); noise(os.path.join(d, "close-outline.png"))
    json.dump({"in": {"frames": 180, "end_zoom": 16}, "out": {"frames": 180, "end_zoom": 13}, "visibility": "visible", "sprite_sha256": sha, "captured_at": when.isoformat(timespec="seconds")}, open(os.path.join(d, "zoom-motion.json"), "w"))
st = lambda **k: rg.check(slug, fx, **k)[0]

# --- the known-bad the audit reproduced: zero-byte images/table + hand-written motion JSON
d = folder()
for f in ("zoomout-table.md", "zoomout.jpg", "close-outline.jpg"): open(os.path.join(d, f), "w").close()
json.dump({"in": {"frames": 361, "end_zoom": 16}, "out": {"frames": 361, "end_zoom": 13}, "visibility": "visible"}, open(os.path.join(d, "zoom-motion.json"), "w"))
case("zero-byte images + empty table + hand-typed motion JSON", st(), "incomplete")
for f in os.listdir(d): os.remove(os.path.join(d, f))
case("no evidence at all", st(), "incomplete")
full(d); case("complete, bound evidence", st(), "complete")
sprite(2); case("sprite changed after the evidence (same day)", st(), "incomplete")
sprite(1); full(d)
open(os.path.join(d, "zoom-motion.json"), "w").write("{not json"); case("malformed motion JSON", st(), "unknown")
full(d); j = json.load(open(os.path.join(d, "rendered-zoomout.json"))); j["visibility"] = "hidden"; json.dump(j, open(os.path.join(d, "rendered-zoomout.json"), "w"))
case("dump taken while hidden (and table no longer matches the dump)", st(), "incomplete")
full(d); j = json.load(open(os.path.join(d, "rendered-zoomout.json"))); j["rows"][0].update(shown=False, longest=0); json.dump(j, open(os.path.join(d, "rendered-zoomout.json"), "w"))
case("piece hidden at full zoom-out", st(), "incomplete")
full(d); Image.new("RGB", (640, 400), (255, 255, 255)).save(os.path.join(d, "zoomout.png")); case("blank capture", st(), "incomplete")
full(d, when=now - datetime.timedelta(hours=13)); case("evidence 13 h old", st(), "incomplete")
# --- midnight: evidence written at 23:50 yesterday, checked at 00:10 today
import shutil; shutil.rmtree(os.path.join(fx, "review-" + now.strftime("%Y%m%d")))
midnight = now.replace(hour=0, minute=10, second=0, microsecond=0)
before = midnight - datetime.timedelta(minutes=20)
d1 = os.path.join(fx, "review-" + before.strftime("%Y%m%d"), slug); os.makedirs(d1); full(d1, when=before)
for f in os.listdir(d1): os.utime(os.path.join(d1, f), (before.timestamp(), before.timestamp()))
os.utime(rg.sprite_path(slug, fx), (before.timestamp() - 600,) * 2)
case("review finished 23:50, checked 00:10 next day", rg.check(slug, fx, now=midnight)[0], "complete")

# --- object record: empty / blank brief / hand-made / good / stale
pg.REPO = fx; rec_dir = os.path.join(fx, ".agents/object-records"); os.makedirs(rec_dir)
rp = os.path.join(rec_dir, f"{slug}-{now.strftime('%Y%m%d')}.md")
body = lambda gen, brief: f"# Object record\ngenerated: {gen}\n## 1. git history\n## 4. written rulings\n## 5. Owner's own words\n## 6. Brief\n{brief}"
blank = "- Decided, by whom, when:\n- Rejected (do not repeat):\n- Approved version (sha, date, the owner's words):\n- What my planned change touches, and which ruling covers it:\n"
good = "- Decided, by whom, when: off the map, the owner, 2026-10-04\n- Rejected (do not repeat): plan-view render, image-model redraws\n- Approved version (sha, date, the owner's words): none; the owner removed it\n- What my planned change touches, and which ruling covers it: nothing without the owner's word\n"
open(rp, "w").close(); case("empty object record", pg.record_ok(slug)[0], False)
open(rp, "w").write(body(now.isoformat(timespec="seconds"), blank)); case("record with blank brief", pg.record_ok(slug)[0], False)
open(rp, "w").write(body(now.isoformat(timespec="seconds"), blank.replace(":\n", ": x\n"))); case("brief filled with one character each", pg.record_ok(slug)[0], False)
open(rp, "w").write("## 6. Brief\n" + good); case("hand-made record without generated/evidence sections", pg.record_ok(slug)[0], False)
open(rp, "w").write(body((now - datetime.timedelta(hours=14)).isoformat(timespec="seconds"), good)); case("record 14 h old", pg.record_ok(slug)[0], False)
open(rp, "w").write(body(now.isoformat(timespec="seconds"), good)); case("generated record, brief written", pg.record_ok(slug)[0], True)

# --- git stash pop when the stash DOES hold a sprite (git is mocked; nothing runs)
real_run = pg.subprocess.run
pg.subprocess.run = lambda *a, **k: types.SimpleNamespace(stdout="public/images/sprites/sf/coit-tower.png\ncomponents/LiveMap.tsx\n")
case("git stash pop, stash holds coit-tower sprite", pg.analyse("git stash pop", fx)[0], {"coit-tower"})
case("git apply patch (cannot tell what it rewrites)", bool(pg.analyse("git apply /tmp/x.patch", fx)[2]), True)
pg.subprocess.run = real_run

# --- stop re-entry is bounded, and a retraction releases it
hook = os.path.join(ROOT, "hooks/piece_gate.py"); R = os.environ.get("CITY_WALKS_REPO") or sys.exit("set CITY_WALKS_REPO to the map repo")
def fire(msg, active, sid):
    p = subprocess.run([sys.executable, hook, "stop"], input=json.dumps({"cwd": R, "last_assistant_message": msg, "stop_hook_active": active, "session_id": sid}), capture_output=True, text=True)
    return p.returncode, p.stdout
sid = "reentry-test-%d" % os.getpid()
codes = [fire("The Coit Tower piece is fixed.", i > 0, sid)[0] for i in range(4)]
case("stubborn claim: blocked at most twice, then released with a warning", codes, [2, 2, 0, 0])
case("...and the release carries an explicit NOT RESOLVED message", "NOT RESOLVED" in fire("The Coit Tower piece is fixed.", True, sid)[1], True)
case("retraction releases at once", fire("The Coit Tower piece is not yet verified; I have not looked at full zoom-out.", True, "retract-%d" % os.getpid())[0], 0)
os.remove(os.path.join(tempfile.gettempdir(), f"piece-gate-stop-{sid}.count"))
shutil.rmtree(fx)
bad = sum(not ok for _, ok in results); print(f"\n{len(results)} cases, {bad} wrong"); sys.exit(1 if bad else 0)
