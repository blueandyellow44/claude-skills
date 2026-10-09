#!/usr/bin/env python3
"""
Full zoom-out size table: what the map draws for each piece, and how a candidate
version of one piece compares with the version it replaces.

Cause it exists (2026-10-03): a de Young render was checked only at close zoom and
shipped far heavier at full zoom-out than the piece it replaced.

A DETECTOR for a review. It sets no size and proposes none: area and visual-weight
SIZING stay rejected (lib/pieceScale.ts header), and no threshold here is a
sizing rule. A flag means "this changed; look", never "this is bad art".

HOW SIZES ARE COMPUTED (the map's own contract, components/LiveMap.tsx and
lib/pieceScale.ts as read 2026-10-04):
  - the dump gives px per real meter at full zoom-out: the median, over shown
    ground pieces, of (drawn longest side x inkOfBox) / sizeM;
  - a ground piece's whole image is drawn with its longer side =
    (px per meter x sizeM) / inkOfBox;
  - an upright piece (|inkAxisDeg| >= 60) is drawn by height: px per meter x
    heightM, compressed by a square root above HEIGHT_KNEE x the 127 m reference;
  - a span (the bridge) is true scale along its deck: NOT SUPPORTED here.
Each version is sized with ITS OWN metadata (w, h, inkOfBox, inkAxisDeg, sizeM,
heightM), so a change in padding, in the keyer's measurements or in the data
shows up as a displayed-size change instead of being scaled away.
The sizing RULE is today's for every version; old revisions' own rules are not replayed.

THREE separate findings, never merged:
  DISPLAYED SIZE   the longest side of the candidate's INK as drawn vs the baseline's
  DISPLAYED INK    drawn ink area vs the baseline's (size and shape together)
  SHAPE ONLY       ink at equal longest side (shape alone)
plus DUMP CHECK: is the piece drawn in the dump at the size the contract gives?

Usage:
  weight_table.py --dump D --slug S [--candidate WT|git:REV|PATH.png] [--baseline git:REV|WT|PATH.png] [--out T.md]
  weight_table.py --dump D --all --candidate WT --baseline git:HEAD
Exit 0 clear, 1 flagged, 2 bad input, 3 not reviewed (the comparison could not be made).
"""
import argparse, datetime, hashlib, io, json, math, os, re, statistics, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib"))
import cw_common as cw
from PIL import Image
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTPRINTS = os.path.join(HERE, "..", "..", "landmark-piece", "references", "footprints.json")
PROTECTED = os.path.join(HERE, "..", "..", "landmark-piece", "references", "protected.json")
SPRITE_REL = "public/images/sprites/sf/{}.png"
GROUND_REFERENCE_M, HEIGHT_KNEE, UPRIGHT_WITHIN_DEG = 127, 0.344, 30   # lib/pieceScale.ts, data/boardLandmarks.ts
TRIM_ALPHA = 24
FACTOR, SIZE_TOL = 1.4, 0.10   # review tripwires only; not sizing rules


def git_bytes(repo, rev, rel):
    p = subprocess.run(["git", "-C", repo, "show", f"{rev}:{rel}"], capture_output=True)
    return p.stdout if p.returncode == 0 and p.stdout else None


def ink_mask(im):
    a = np.asarray(im.convert("RGBA")).astype(int)
    if (a[..., 3] < 250).any():
        return a[..., 3] > TRIM_ALPHA
    return ~((a[..., 0] > 200) & (a[..., 2] > 200) & (a[..., 1] < 90))   # a raw render on magenta


def measure_png(data):
    """Metadata the keyer would record, measured from the image itself."""
    im = Image.open(io.BytesIO(data)); mask = ink_mask(im)
    yy, xx = np.nonzero(mask)
    if xx.size == 0:
        return None
    raw_bg = not (np.asarray(im.convert("RGBA"))[..., 3] < 250).any()
    # A raw render has no trim yet: its box is the ink box (the keyer trims to ink and pads 4 px).
    w, h = (xx.max() - xx.min() + 1 + 8, yy.max() - yy.min() + 1 + 8) if raw_bg else (im.width, im.height)
    cx, cy = xx.mean(), yy.mean(); dx, dy = xx - cx, yy - cy
    axis = 0.5 * math.atan2(2 * (dx * dy).mean(), (dx * dx).mean() - (dy * dy).mean())
    along = dx * math.cos(axis) + dy * math.sin(axis)
    return {"w": int(w), "h": int(h), "inkOfBox": float((along.max() - along.min()) / max(w, h)),
            "inkAxisDeg": math.degrees(axis), "ink": int(mask.sum()), "measured": True,
            "bw": int(xx.max() - xx.min() + 1), "bh": int(yy.max() - yy.min() + 1)}


def landmark_data(src):
    out = {}
    for chunk in re.split(r'(?=\bslug:\s*")', src or "")[1:]:
        slug = re.match(r'slug:\s*"([a-z0-9-]+)"', chunk).group(1)
        s, h = re.search(r"\bsizeM:\s*([\d.]+)", chunk), re.search(r"\bheightM:\s*([\d.]+)", chunk)
        out[slug] = {"sizeM": float(s.group(1)) if s else None, "heightM": float(h.group(1)) if h else None,
                     "span": bool(re.search(r"\bspan:\s*\{", chunk))}
    return out


class Source:
    """One state of the repo: 'WT' or 'git:<rev>'. Gives a sprite version = bytes + metadata + data."""
    def __init__(self, repo, spec):
        self.repo, self.spec = repo, spec
        if spec == "WT":
            rd = lambda rel: open(os.path.join(repo, rel), "rb").read() if os.path.isfile(os.path.join(repo, rel)) else None
        else:
            rd = lambda rel: git_bytes(repo, spec[4:], rel)
        self.read = rd
        idx = rd("data/board/sf-sprites.json")
        self.index = json.loads(idx) if idx else {}
        lm = rd("data/boardLandmarks.ts")
        self.lm = landmark_data(lm.decode("utf-8", "replace") if lm else "")

    def version(self, slug, png_path=None):
        data = open(png_path, "rb").read() if png_path else self.read(SPRITE_REL.format(slug))
        if not data:
            return None
        m = measure_png(data)
        if m is None:
            return {"empty": True}
        meta = self.index.get(slug) if not png_path else None
        if meta and "inkOfBox" in meta:     # the recorded keyer metadata is what the map uses
            m.update(w=meta["w"], h=meta["h"], inkOfBox=meta["inkOfBox"], inkAxisDeg=meta.get("inkAxisDeg", m["inkAxisDeg"]), measured=False)
        m.update(self.lm.get(slug, {"sizeM": None, "heightM": None, "span": False}))
        m["sha"] = hashlib.sha256(data).hexdigest()
        m["upright"] = abs(m["inkAxisDeg"]) >= 90 - UPRIGHT_WITHIN_DEG
        return m


def drawn(v, ppm):
    """(image w px, image h px, ink px2, ink longest px) under the map's contract, or None if unsupported.
    The ink's own extent is reported apart from the image box: transparent padding enlarges the box, not the piece."""
    if v.get("span") or not v.get("sizeM"):
        return None
    if v["upright"]:
        raw = ppm * (v.get("heightM") or v["sizeM"])
        knee = HEIGHT_KNEE * ppm * GROUND_REFERENCE_M
        h = raw if raw <= knee else knee * math.sqrt(raw / knee)
    else:
        box = ppm * v["sizeM"] / v["inkOfBox"]
        h = box / (v["w"] / v["h"]) if v["w"] >= v["h"] else box
    k = h / v["h"]
    return v["w"] * k, h, v["ink"] * k * k, max(v["bw"], v["bh"]) * k


def px_per_meter(dump, wt, exclude=None):
    vals = []
    for r in dump.get("rows", []):
        v = wt.version(r["slug"])
        if (r["slug"] == exclude or not v or v.get("empty") or v.get("span") or v["upright"] or not v.get("sizeM")
                or not r.get("shown") or not r.get("longest")):
            continue
        vals.append((r["longest"] * v["inkOfBox"]) / v["sizeM"])
    return (statistics.median(vals), len(vals), (min(vals), max(vals))) if len(vals) >= 3 else (None, len(vals), None)


def compare(slug, dump, wt, cand_src, base_src, cand_path=None, base_path=None):
    """-> dict(state=clear|flag|not_reviewed, lines=[...], cand=version)"""
    L, flags = [], []
    rows = {r["slug"]: r for r in dump.get("rows", [])}
    ppm, n, spread = px_per_meter(dump, wt, exclude=slug)
    cand, base = cand_src.version(slug, cand_path), base_src.version(slug, base_path)
    def nr(why):
        return {"state": "not_reviewed", "lines": L + [f"NOT REVIEWED: {why}"], "cand": cand}
    if ppm is None:
        return nr(f"the dump has only {n} other shown ground piece(s); at least 3 are needed to read the map's scale. A dump of one piece, or an empty one, reviews nothing.")
    L.append(f"scale read from the dump: {ppm:.4f} px per real meter (median of {n} other ground pieces; they range {spread[0]:.4f} to {spread[1]:.4f})")
    if cand is None:
        return nr(f"no candidate sprite for {slug} in {cand_src.spec}")
    if cand.get("empty"):
        return nr("the candidate image has no ink")
    if cand.get("span"):
        return nr(f"{slug} is a span, drawn true scale along its deck; this table does not model it")
    dc = drawn(cand, ppm)
    if dc is None:
        return nr(f"{slug} has no sizeM in {cand_src.spec}'s data/boardLandmarks.ts")
    L.append(f"candidate ({cand_path or cand_src.spec}): {dc[0]:.0f} x {dc[1]:.0f} px, ink {dc[2]:.0f} px2"
             f"  [{'upright, by height ' + str(cand.get('heightM')) + ' m' if cand['upright'] else 'ground, sizeM ' + str(cand['sizeM']) + ' m'}; inkOfBox {cand['inkOfBox']:.3f}{', measured from the image' if cand['measured'] else ''}]")
    # DUMP CHECK: only meaningful when the candidate is what the dump rendered (the working tree).
    row = rows.get(slug)
    if cand_src.spec == "WT" and not cand_path:
        if not row:
            L.append("DUMP CHECK: the piece is not in the dump, so nothing was observed at full zoom-out.")
            flags.append("not in dump")
        elif not row.get("shown") or not row.get("longest"):
            L.append("DUMP CHECK: the piece is HIDDEN at full zoom-out in this dump. There is no observed size; a finding for the owner, not a pass.")
            flags.append("hidden")
        else:
            ratio = row["longest"] / max(dc[0], dc[1])
            L.append(f"DUMP CHECK: the dump drew it {row['longest']:.0f} px on its longest side; the contract gives {max(dc[0], dc[1]):.0f} px ({ratio:.2f}x)")
            if abs(ratio - 1) > SIZE_TOL:
                flags.append(f"the map drew this piece {ratio:.2f}x the size the sizing contract gives (ink about {ratio * ratio:.2f}x). Either the dump predates the current sprite or data, or the piece is off the set's scale")
    if base is None:
        L.append(f"NO BASELINE: {base_path or base_src.spec} has no version of this piece. A new piece has nothing to be compared with; judge it by eye beside its neighbours.")
    elif base.get("empty"):
        L.append("NO BASELINE: the baseline image has no ink.")
    else:
        db = drawn(base, ppm)
        if db is None:
            L.append(f"NO BASELINE SIZE: {base_src.spec} gives no sizeM (or a span) for this piece.")
        else:
            size = dc[3] / db[3]; ink = dc[2] / db[2]; shape = ink / (size * size)
            L += [f"baseline  ({base_path or base_src.spec}): {db[0]:.0f} x {db[1]:.0f} px, ink {db[2]:.0f} px2"
                  f"  [{'upright' if base['upright'] else 'ground'}, sizeM {base['sizeM']}, inkOfBox {base['inkOfBox']:.3f}]",
                  f"- DISPLAYED SIZE (longest side of the ink): {size:.2f}x", f"- DISPLAYED INK (what the eye weighs): {ink:.2f}x",
                  f"- SHAPE ONLY (ink at equal longest side): {shape:.2f}x"]
            if base["upright"] != cand["upright"]:
                flags.append("the piece changed class (upright vs ground), so it is sized by a different rule")
            if abs(size - 1) > SIZE_TOL:
                flags.append(f"displayed size changed {size:.2f}x")
            if ink > FACTOR or ink < 1 / FACTOR:
                flags.append(f"displayed ink changed {ink:.2f}x")
    prot = json.load(open(PROTECTED)).get(slug)
    if prot:
        L.append(f"NOTE: {slug} is a piece the owner approved by name ({prot['approved']}). A change measured against any OTHER baseline says nothing against the approved art.")
    L.append("The baseline is a point of comparison. Nothing here knows whether the owner approved it.")
    return {"state": "flag" if flags else "clear", "flags": flags, "lines": L, "cand": cand}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True); ap.add_argument("--slug"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--repo", default=cw.REPO); ap.add_argument("--out")
    ap.add_argument("--candidate", default="WT"); ap.add_argument("--baseline", default="git:HEAD")
    a = ap.parse_args()
    if not a.repo:
        print("set CITY_WALKS_REPO to the map repo, or pass --repo", file=sys.stderr); sys.exit(2)
    try:
        dump = json.load(open(a.dump)); dump["rows"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"bad dump {a.dump}: {type(e).__name__}", file=sys.stderr); sys.exit(2)
    if not (a.slug or a.all):
        print("give --slug or --all", file=sys.stderr); sys.exit(2)
    wt = Source(a.repo, "WT")
    def src(spec):
        return (Source(a.repo, spec), None) if spec == "WT" or spec.startswith("git:") else (wt, spec)
    (cs, cp), (bs, bp) = src(a.candidate), src(a.baseline)

    if a.all:
        slugs = sorted(set(json.load(open(FOOTPRINTS))) - {"_source", "_qualifications"})
        print(f"# {a.baseline} -> {a.candidate}, all {len(slugs)} surveyed pieces (sizes under today's contract, scale from {os.path.basename(a.dump)})\n")
        tally = {"clear": 0, "flag": 0, "not_reviewed": 0}
        for s in slugs:
            r = compare(s, dump, wt, cs, bs)
            tally[r["state"]] += 1
            nums = " ".join(x.split("): ")[1] if "): " in x else "" for x in r["lines"] if x.startswith("- "))
            why = "; ".join(r.get("flags", [])) or next((x for x in r["lines"] if x.startswith(("NOT REVIEWED", "NO BASELINE"))), "")
            print(f"{r['state'].upper():13} {s:24} size/ink/shape {nums or '-':18} {why[:150]}")
        print(f"\nclear {tally['clear']}, flagged {tally['flag']}, not reviewed {tally['not_reviewed']}. A flag is a change to look at, not a verdict on the art.")
        sys.exit(0)

    r = compare(a.slug, dump, wt, cs, bs, cp, bp)
    # the table for the eye: every piece as the dump drew it
    T = [f"# Full zoom-out size table ({os.path.basename(a.dump)}, viewport {dump.get('innerWidth')}x{dump.get('innerHeight')}, visibility {dump.get('visibility')})", "",
         "| piece | shown | drawn longest px (dump) | ink px2 (dump size) | footprint m2 | ink px2 per 1000 m2 |", "|---|---|---|---|---|---|"]
    fp = json.load(open(FOOTPRINTS)); dens = []
    for row in sorted(dump["rows"], key=lambda x: -(x.get("longest") or 0)):
        v = wt.version(row["slug"])
        if not v or v.get("empty"):
            continue
        shown = bool(row.get("shown") and row.get("longest"))
        k = (row.get("longest") or 0) / max(v["w"], v["h"])
        f = fp.get(row["slug"]); m2 = f["long_m"] * f["short_m"] if f else None
        d = 1000 * v["ink"] * k * k / m2 if (m2 and shown) else None
        if d and not v["upright"] and not v.get("span"):
            dens.append(d)
        T.append(f"| {row['slug']}{' **<- under review**' if row['slug'] == a.slug else ''} | {'yes' if shown else 'HIDDEN'} | {row.get('longest') or 0:.0f} | {v['ink'] * k * k:.0f} | {m2 or 'not surveyed'} | {f'{d:.1f}' if d else '-'} |")
    if len(dens) >= 2:
        T += ["", f"Ink per 1000 m2 of real footprint runs {min(dens):.1f} to {max(dens):.1f} across the {len(dens)} shown ground pieces in THIS dump ({max(dens) / min(dens):.1f}x apart), "
                  "so one piece cannot be judged against its neighbours by this number. The neighbours are judged by eye on the capture."]
    T += ["", f"## {a.slug}"] + r["lines"] + [""]
    if r["state"] == "flag":
        T.append("FLAG: " + "; ".join(r["flags"]) + ". A flag is a change to look at, not a verdict on the art: LOOK at full zoom-out beside the neighbours and say what is seen.")
    elif r["state"] == "clear":
        T.append(f"clear on these tripwires (size within {SIZE_TOL:.0%}, ink within {FACTOR}x). A floor, never the verdict: LOOK at the capture beside the neighbours.")
    cand = r.get("cand") or {}
    T += ["", f"candidate-sha256: {cand.get('sha', 'none')}", f"dump-sha256: {hashlib.sha256(open(a.dump, 'rb').read()).hexdigest()}",
          f"generated: {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}", ""]
    text = "\n".join(T)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "w").write(text)
    print(text)
    sys.exit({"clear": 0, "flag": 1, "not_reviewed": 3}[r["state"]])


if __name__ == "__main__":
    main()
