#!/usr/bin/env python3
"""
A narrow tripwire for SURVEY RENDERS: is this drawing's ink box the shape a
plan view (straight down) would give, rather than the set's 30 degree camera?

Cause it exists (2026-10-03): the first de Young survey render looked straight
down on the plan, against the project's rule "one camera for the art".

WHAT IT CAN AND CANNOT SAY
  REFUSED     the box matches a plan view and a plan view is distinguishable from
              the camera for this footprint. The one positive finding it makes.
  COMPATIBLE  the box is within what a 30 degree render of this footprint could
              produce. NOT a certificate: a box cannot show the camera, the
              signed orientation, the handedness or the SIZE. A plan view of a
              tall piece and a camera view of it can have the same box.
  ABSTAIN     the evidence cannot distinguish: the two projections give nearly
              the same box, the piece is a documented exception (lies at the
              map's angle; a span), the box fits neither projection, or the
              image has no ink.
Measured 2026-10-04 on the 18 footprints: see tests/camera_cases.py.
It is never a reason to redraw approved art.

Usage: camera_check.py <slug> <raw-or-keyed.png> [--allow-protected]
Exit 0 compatible, 1 refused, 2 abstain.
"""
import argparse, json, math, os, sys
from PIL import Image
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "references")
CAMERA_DEG = 30
# Documented exceptions (project record, 2026-10-03): not survey renders in the one camera.
EXCEPTIONS = {
    "ferry-building": "lies flat along the Embarcadero at the MAP's angle (approved piece, c3b44f7); verify-pieces expects its plan angle",
    "legion-of-honor": "sheared to the MAP's angle on 2026-10-03; verify-pieces expects its plan angle",
    "golden-gate-bridge": "a span: drawn by its 1280 m main span, not the 1949 m OSM deck way, and true scale at every zoom",
}


def ink_box(path):
    a = np.asarray(Image.open(path).convert("RGBA")).astype(int)
    ink = a[..., 3] > 24 if (a[..., 3] < 250).any() else ~((a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 90))
    ys, xs = np.where(ink)
    if xs.size == 0:
        return None
    return int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def expected(fp):
    """(plan h/w, camera lowest h/w, camera highest h/w) for a surveyed footprint.
    South-up map: the long axis lies |90 - bearing| from horizontal on screen. Depth
    is foreshortened by sin(30), heights drawn at cos(30)."""
    L, S, H = fp["long_m"], fp["short_m"], fp.get("height_m") or 0
    phi = math.radians(abs(90 - fp["axis_bearing_deg"]))
    w = L * abs(math.cos(phi)) + S * abs(math.sin(phi))
    depth = L * abs(math.sin(phi)) + S * abs(math.cos(phi))
    s, c = math.sin(math.radians(CAMERA_DEG)), math.cos(math.radians(CAMERA_DEG))
    return depth / w, depth * s / w, (depth * s + H * c) / w


def judge(slug, box, fp):
    """-> (exit code, verdict line)"""
    if slug in EXCEPTIONS:
        return 2, f"ABSTAIN: documented exception. {slug} {EXCEPTIONS[slug]}. This check does not apply."
    if box is None:
        return 2, "ABSTAIN: the image has no ink (fully transparent or all background)."
    plan, lo, hi = expected(fp)
    obs = box[1] / box[0]
    detail = f"ink box {box[0]} x {box[1]} px, height/width {obs:.3f}; camera allows {lo:.3f} to {hi:.3f}; plan view gives {plan:.3f}"
    if lo * 0.8 <= plan <= hi * 1.12:
        return 2, f"ABSTAIN: for this footprint a plan view ({plan:.3f}) falls inside what the camera allows, so the box cannot tell them apart ({detail}). Judge the camera by eye against the set."
    if abs(obs - plan) <= 0.12 * plan:
        return 1, (f"REFUSED: the box matches a PLAN VIEW, not the set's 30 degree camera ({detail}). A plan view draws the full depth, about "
                   f"{plan / ((lo + hi) / 2):.1f}x the camera's. Render with CAMERA_ELEVATION_DEG = 30. The rule: one camera for the art.")
    if lo * 0.8 <= obs <= hi * 1.12:
        return 0, f"COMPATIBLE with the one camera, which is not proof of it ({detail}). The box says nothing about size, orientation or handedness."
    return 2, f"ABSTAIN: the box fits neither projection ({detail}). The drawing may include more or less than the surveyed footprint; this check cannot say."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("png"); ap.add_argument("--allow-protected", action="store_true")
    a = ap.parse_args()
    protected = json.load(open(os.path.join(REF, "protected.json")))
    if a.slug in protected and not a.allow_protected:
        p = protected[a.slug]
        print(f"REFUSED: {a.slug} is an approved piece ({p['approved']}). {p['note']} "
              f"Do not redraw or re-key it without the owner's word in this session. {p['restore']}")
        sys.exit(1)
    fp = json.load(open(os.path.join(REF, "footprints.json"))).get(a.slug)
    if not fp or a.slug.startswith("_"):
        print(f"ABSTAIN: no surveyed footprint for {a.slug} in references/footprints.json. Fetch it from OSM first; never type a dimension from memory.")
        sys.exit(2)
    try:
        box = ink_box(a.png)
    except (OSError, ValueError) as e:
        print(f"ABSTAIN: cannot read {a.png} ({type(e).__name__})."); sys.exit(2)
    print(f"{a.slug}: survey {fp['long_m']} x {fp['short_m']} m, axis bearing {fp['axis_bearing_deg']} deg, record height {fp.get('height_m')} m (OSM tag {fp.get('height_osm_tag_m')} m)")
    code, line = judge(a.slug, box, fp)
    print(line)
    sys.exit(code)


if __name__ == "__main__":
    main()
