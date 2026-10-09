#!/usr/bin/env python3
"""
Is the review of <slug> complete, for the sprite as it is on disk NOW? One
definition, used by the skill and by the hook.

Evidence lives in <repo>/review-<YYYYMMDD>/<slug>/ and is BOUND to the sprite's
bytes: each machine-written file records the sha256 of
public/images/sprites/sf/<slug>.png at capture time. If the sprite changes, the
evidence is stale, same day or not.

  rendered-zoomout.json  DOM dump at full zoom-out (visibility must be "visible")
  zoomout-table.md       written by weight_table.py from that dump (carries
                         candidate-sha256 and dump-sha256 lines)
  zoomout.(png|jpg)      a real image, full zoom-out beside the neighbours
  close-outline.(png|jpg) a real image, z16 to 17 against the OSM outline
  zoom-motion.json       written by `review_gate.py stamp` from the measured pass

States: COMPLETE, INCOMPLETE (something is missing, stale or flagged) or
UNKNOWN (evidence is malformed or cannot be checked here). Only COMPLETE passes.

WHAT THIS DOES NOT PROVE: that anyone looked. A session can still write these
files without looking. The gate makes skipping the review an explicit act with
bound, checkable artifacts; it does not make the review happen.

Usage:
  review_gate.py <slug> [--repo DIR]                 exit 0 complete, 1 incomplete, 3 unknown
  review_gate.py stamp <slug> --motion '<json from the browser snippet>' [--repo DIR]
"""
import argparse, datetime, glob, hashlib, json, os, sys

# The map app's repo: CITY_WALKS_REPO, or --repo on the command line.
REPO = os.path.expanduser(os.environ.get("CITY_WALKS_REPO", ""))
WINDOW_H = 12            # evidence older than this is stale even if the sprite is unchanged
MIN_IMAGE = (300, 200)   # px; a capture smaller than this is not a map capture


def sha_file(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError:
        return None


def sprite_path(slug, repo=REPO):
    return os.path.join(repo, "public", "images", "sprites", "sf", slug + ".png")


def _fresh(iso, now):
    try:
        t = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.astimezone()
    return (now - t).total_seconds() <= WINDOW_H * 3600 and (now - t).total_seconds() > -300


def _image_problem(path):
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return "unknown", "Pillow is not installed, so the image cannot be checked"
    try:
        im = Image.open(path); im.load()
    except Exception as e:  # noqa: BLE001 - any decode failure is the finding
        return "incomplete", f"is not a readable image ({type(e).__name__})"
    if im.width < MIN_IMAGE[0] or im.height < MIN_IMAGE[1]:
        return "incomplete", f"is {im.width}x{im.height} px, too small to be a map capture"
    if max(ImageStat.Stat(im.convert("L")).stddev) < 1.0:
        return "incomplete", "is a blank image"
    return None, None


def check(slug, repo=REPO, now=None):
    """-> (state, folder, problems). state is 'complete', 'incomplete' or 'unknown'."""
    now = now or datetime.datetime.now().astimezone()
    cur = sha_file(sprite_path(slug, repo))
    # Today's folder, or yesterday's: a review that straddles midnight is still one review.
    days = [(now - datetime.timedelta(days=d)).strftime("%Y%m%d") for d in (0, 1)]
    folders = [os.path.join(repo, f"review-{d}", slug) for d in days]
    d = next((f for f in folders if os.path.isdir(f)), folders[0])
    miss, unknown = [], []
    if cur is None:
        return "unknown", d, [f"the sprite {sprite_path(slug, repo)} does not exist, so evidence cannot be bound to it"]
    if not os.path.isdir(d):
        return "incomplete", d, ["no review folder (run city-walks-workflow:piece-review)"]

    # 1. the dump
    dump_p = os.path.join(d, "rendered-zoomout.json")
    dump_sha = sha_file(dump_p)
    if dump_sha is None:
        miss.append("rendered-zoomout.json (the DOM dump taken at full zoom-out)")
    else:
        try:
            dump = json.load(open(dump_p))
            rows = {r["slug"]: r for r in dump["rows"]}
            if dump.get("visibility") != "visible":
                miss.append(f"rendered-zoomout.json was taken while the page was '{dump.get('visibility')}'; not evidence")
            if slug not in rows:
                miss.append(f"rendered-zoomout.json has no row for {slug}")
            elif not rows[slug].get("shown") or not rows[slug].get("longest"):
                miss.append(f"{slug} is HIDDEN at full zoom-out in the dump: there is no full zoom-out size to review (a finding for the owner, not a pass)")
            if len(rows) < 2:
                miss.append("rendered-zoomout.json holds fewer than two pieces; there are no neighbours to judge against")
        except (ValueError, KeyError, TypeError) as e:
            unknown.append(f"rendered-zoomout.json is malformed ({type(e).__name__})")

    # 2. the table, bound to the dump and the sprite
    table_p = os.path.join(d, "zoomout-table.md")
    if not os.path.isfile(table_p):
        miss.append("zoomout-table.md (weight_table.py --out)")
    else:
        t = open(table_p, errors="replace").read()
        meta = dict(ln.split(": ", 1) for ln in t.splitlines() if ln.startswith(("candidate-sha256: ", "dump-sha256: ", "generated: ")))
        if "| piece |" not in t or f"| {slug}" not in t:
            miss.append("zoomout-table.md is not a weight_table.py table for this piece")
        if meta.get("candidate-sha256") != cur:
            miss.append("zoomout-table.md was made for a DIFFERENT version of the sprite; the sprite has changed since (or the table was not written by weight_table.py)")
        if dump_sha and meta.get("dump-sha256") != dump_sha:
            miss.append("zoomout-table.md was not computed from this rendered-zoomout.json")
        if _fresh(meta.get("generated"), now) is not True:
            miss.append(f"zoomout-table.md is older than {WINDOW_H} h or undated")
        for marker, why in (("FLAG:", "carries an unresolved FLAG"), ("NOT REVIEWED:", "says the comparison could not be made")):
            if marker in t:
                miss.append(f"zoomout-table.md {why}")

    # 3. the two captures
    for stem, what in (("zoomout", "full zoom-out capture beside its neighbours"), ("close-outline", "z16 to 17 capture against its OSM outline")):
        found = [f for ext in (".png", ".jpg", ".jpeg") for f in glob.glob(os.path.join(d, stem + ext))]
        if not found:
            miss.append(f"{stem}.png|jpg ({what})")
            continue
        state, why = _image_problem(found[0])
        if state == "unknown":
            unknown.append(f"{os.path.basename(found[0])}: {why}")
        elif state:
            miss.append(f"{os.path.basename(found[0])} {why}")
        elif datetime.datetime.fromtimestamp(os.path.getmtime(found[0])).astimezone() < now - datetime.timedelta(hours=WINDOW_H):
            miss.append(f"{os.path.basename(found[0])} is older than {WINDOW_H} h")
        elif os.path.getmtime(found[0]) < os.path.getmtime(sprite_path(slug, repo)) - 1:
            miss.append(f"{os.path.basename(found[0])} was captured BEFORE the sprite last changed")

    # 4. motion
    motion_p = os.path.join(d, "zoom-motion.json")
    if not os.path.isfile(motion_p):
        miss.append("zoom-motion.json (z13 to 16 and back; write it with `review_gate.py stamp`)")
    else:
        try:
            m = json.load(open(motion_p))
            if m.get("sprite_sha256") != cur:
                miss.append("zoom-motion.json is bound to a different version of the sprite (or was not written by `stamp`)")
            if _fresh(m.get("captured_at"), now) is not True:
                miss.append(f"zoom-motion.json is older than {WINDOW_H} h or undated")
            if m.get("visibility") != "visible":
                miss.append(f"zoom-motion.json: the page was '{m.get('visibility')}'; motion in a hidden tab is not evidence")
            for leg, lo, hi in (("in", 15.9, 99), ("out", 0, 13.1)):
                fr, ez = m[leg]["frames"], m[leg]["end_zoom"]
                if not isinstance(fr, (int, float)) or fr < 30:
                    miss.append(f"zoom-motion.json: '{leg}' counted {fr} frames; a real-time pass needs 30 or more")
                if not isinstance(ez, (int, float)) or not (lo <= ez <= hi):
                    miss.append(f"zoom-motion.json: '{leg}' ended at z{ez}; the pass was interrupted")
        except (ValueError, KeyError, TypeError) as e:
            unknown.append(f"zoom-motion.json is malformed ({type(e).__name__})")

    if miss:
        return "incomplete", d, miss + [f"(could not check: {u})" for u in unknown]
    if unknown:
        return "unknown", d, unknown
    return "complete", d, []


def missing(slug, repo=REPO):
    """Back-compatible helper for the hook: (folder, problems); empty problems only when complete."""
    state, d, problems = check(slug, repo)
    return d, ([] if state == "complete" else [f"[{state.upper()}] " + p for p in problems])


def stamp(slug, motion_json, repo=REPO):
    m = json.loads(motion_json)
    for leg in ("in", "out"):
        if not {"frames", "end_zoom"} <= set(m.get(leg, {})):
            raise SystemExit(f"motion JSON lacks {leg}.frames / {leg}.end_zoom; paste what the browser snippet returned")
    if "visibility" not in m:
        raise SystemExit("motion JSON lacks 'visibility'; paste what the browser snippet returned")
    cur = sha_file(sprite_path(slug, repo))
    if cur is None:
        raise SystemExit(f"no sprite for {slug}")
    now = datetime.datetime.now().astimezone()
    d = os.path.join(repo, f"review-{now.strftime('%Y%m%d')}", slug)
    os.makedirs(d, exist_ok=True)
    m.update(sprite_sha256=cur, captured_at=now.isoformat(timespec="seconds"), slug=slug)
    json.dump(m, open(os.path.join(d, "zoom-motion.json"), "w"), indent=1)
    print(os.path.join(d, "zoom-motion.json"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stamp":
        ap = argparse.ArgumentParser(); ap.add_argument("_"); ap.add_argument("slug")
        ap.add_argument("--motion", required=True); ap.add_argument("--repo", default=REPO)
        a = ap.parse_args()
        if not a.repo:
            sys.exit("set CITY_WALKS_REPO to the map repo, or pass --repo")
        stamp(a.slug, a.motion, a.repo); sys.exit(0)
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--repo", default=REPO)
    a = ap.parse_args()
    if not a.repo:
        sys.exit("set CITY_WALKS_REPO to the map repo, or pass --repo")
    state, d, problems = check(a.slug, a.repo)
    if state == "complete":
        print(f"review COMPLETE for {a.slug}, bound to the sprite on disk: {d}")
        print("This shows the evidence exists and matches the sprite. It does not show that anyone looked.")
        sys.exit(0)
    print(f"REVIEW {state.upper()} for {a.slug} in {d}:")
    for p in problems:
        print("  - " + p)
    sys.exit(1 if state == "incomplete" else 3)
