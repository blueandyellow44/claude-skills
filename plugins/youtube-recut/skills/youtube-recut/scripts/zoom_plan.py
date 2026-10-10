"""Plan punch-in zooms: for every cut piece, find where the screen changes and frame it.

Usage: python zoom_plan.py <project> <track>   (the youtube-recut env has OpenCV 4.x; 5.x lacks CascadeClassifier)
Output: <project>/work/zoom-plan.json {side: {"src|start": [x, y, w, h] or null}} in 3840x2160 source pixels
(null = stay wide). Rules:
- Activity = pixel change between frames sampled at 2 fps, excluding the webcam region (found as
  the area that changes in most frame pairs across the whole piece set) and tiny changes (cursor).
- Crop is the 16:9 box around the activity with 12% padding, never tighter than 2.2x, and skipped
  when the activity already spans most of the frame (>70% width) or the piece is under 1.5 s.
- Pieces that overlap a privacy window stay wide, so the email masks keep their exact geometry.
"""
import json, pathlib, subprocess, sys
import numpy as np
import cv2

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_track as R  # noqa: E402

W, H = 3840, 2160
SW, SH = 960, 540          # analysis size
FPS = 2.0
MAX_ZOOM = 2.0
FACE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
PAD = 0.12


def frames(path, s, e, width):
    """Grayscale analysis frames of [s, e] at FPS, padded to the 3840 canvas like the render."""
    pad = '' if width == W else f',pad={W}:{H}:{(W - width) // 2}:0:black'
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{s:.3f}', '-t', f'{e - s:.3f}', '-i', path, '-map', '0:v:0',
           '-vf', f'fps={FPS}{pad},scale={SW}:{SH},format=gray', '-f', 'rawvideo', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, SH, SW)


def face_mask(img):
    m = np.zeros(img.shape, np.uint8)
    for (x, y, w, h) in FACE.detectMultiScale(img, 1.15, 5, minSize=(24, 24)):
        cx, cy = x + w // 2, y + h // 2          # the bubble is ~3x the face; mask generously
        m[max(0, cy - 2 * h):min(SH, cy + 2 * h), max(0, cx - 2 * w):min(SW, cx + 2 * w)] = 1
    return m


def change_masks(fr):
    out = []
    for a, b in zip(fr[:-1], fr[1:]):
        d = cv2.absdiff(a, b)
        m = (d > 28).astype(np.uint8) & (1 - (face_mask(a) | face_mask(b)))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        out.append(m)
    return out


def main():
    P = R.init(sys.argv[1]); side = sys.argv[2]
    cfg = dict(R.SIDE[side], side=side)
    mapped = P.read('beats-mapped.json')[side]
    spec = {b['id']: b for b in P.beats()[side] if 'id' in b}
    sources = P.sources
    words = {k: json.load(open(v))['words'] for k, v in cfg['words'].items()}
    pv = R.PRIVACY.get(side)

    pieces = []
    for b in mapped:
        if 'card' in b:
            continue
        if spec.get(b['id'], {}).get('skip'):
            b['skip'] = spec[b['id']]['skip']
        for s, e, ws, m in R.pieces_for(b, words[b['src']], side):
            pieces.append((b['src'], s, e, m))

    # pass 1: activity masks per piece; accumulate how often each pixel changes (webcam finder)
    data, freq, pairs = {}, np.zeros((SH, SW), np.float64), 0
    for src, s, e, m in pieces:
        path = sources[src]
        width = int(R.probe(path, 'width,height')[0])
        fr = frames(path, s, e, width)
        ms = change_masks(fr) if len(fr) > 1 else []
        for x in ms:
            freq += x; pairs += 1
        data[(src, s)] = (ms, e - s, m, fr[::max(1, len(fr) // 6)])
    webcam = (freq / max(1, pairs) > 0.35).astype(np.uint8)
    webcam = cv2.dilate(webcam, np.ones((25, 25), np.uint8))
    print(f'webcam/persistent-motion mask covers {webcam.mean() * 100:.1f}% of frame')

    plan = {}
    for (src, s), (ms, dur, m, samples) in data.items():
        key = f'{src}|{s:.3f}'
        private = pv and any(m < hi and m + dur > lo for (lo, hi), _ in pv['boxes'])
        if dur < 1.5 or not ms or private:
            plan[key] = None; continue
        act = np.zeros((SH, SW), np.uint8)
        for x in ms:
            act |= x
        act &= (1 - webcam)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(act, 8)
        keep = np.zeros_like(act)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= 60:          # drop cursor-sized specks
                keep[lab == i] = 1
        ys, xs = np.nonzero(keep)
        if len(xs) < 200:
            plan[key] = None; continue
        x0, x1 = np.percentile(xs, [2, 98]); y0, y1 = np.percentile(ys, [2, 98])
        bw, bh = (x1 - x0) * (1 + 2 * PAD), (y1 - y0) * (1 + 2 * PAD)
        if bw > 0.70 * SW:
            plan[key] = None; continue
        cw = min(SW, max(bw, bh * 16 / 9, SW / MAX_ZOOM)); ch = cw * 9 / 16
        if cw >= 0.9 * SW:
            plan[key] = None; continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cx = min(max(cx, cw / 2), SW - cw / 2); cy = min(max(cy, ch / 2), SH - ch / 2)
        bx0, by0, bx1, by1 = cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2
        face_in_box = False
        for img in samples:
            for (x, y, w, h) in FACE.detectMultiScale(img, 1.15, 5, minSize=(24, 24)):
                if x + w > bx0 and x < bx1 and y + h > by0 and y < by1:
                    face_in_box = True
        if face_in_box:
            plan[key] = None; continue
        # skip boxes that frame near-empty screen: require real text (edge density) inside the box
        last = samples[-1][int(by0):int(by1), int(bx0):int(bx1)]
        edges = cv2.Canny(last, 60, 160)
        if edges.mean() / 255 < 0.035:
            plan[key] = None; continue
        f = W / SW
        box = [int((cx - cw / 2) * f) // 2 * 2, int((cy - ch / 2) * f) // 2 * 2, int(cw * f) // 2 * 2, int(ch * f) // 2 * 2]
        plan[key] = box
    allp = P.read('zoom-plan.json', {})
    allp[side] = plan
    P.write('zoom-plan.json', allp)
    z = [v for v in plan.values() if v]
    print(f'{side}: {len(plan)} pieces, {len(z)} zoomed, median zoom {np.median([W / b[2] for b in z]) if z else 0:.2f}x')


if __name__ == '__main__':
    main()
