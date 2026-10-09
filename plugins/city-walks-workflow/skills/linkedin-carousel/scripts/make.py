"""Carousel slides for the wallywalks.app LinkedIn post, built from the app's own
drawings, fonts and story text (Telegraph Hill Stairway Loop). 1080x1350 each,
plus one PDF for LinkedIn's document upload."""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.environ.get("CAROUSEL_WORK") or os.path.dirname(os.path.abspath(__file__))  # data, fonts, map band
# The app repo (sprites, stop drawings). CAROUSEL_APP, or the current folder when it is the repo root.
APP = os.environ.get("CAROUSEL_APP") or os.getcwd()
if not os.path.isfile(os.path.join(APP, "data", "routes.ts")):
    sys.exit(f"{APP} is not the app repo (no data/routes.ts): set CAROUSEL_APP to the repo root, or run from it")
OUT = os.path.expanduser(os.environ.get("CAROUSEL_OUT", "~/Downloads/wallywalks-carousel"))
os.makedirs(OUT, exist_ok=True)
data = json.load(open(os.path.join(HERE, "stops.json")))

W, H, M = 1080, 1350, 84
PAPER, INK, SLATE, MUTED = "#F3EAD8", "#2B2622", "#5A524A", "#8A8176"
ACCENT = data["color"]


def font(name, size, weight=None):
    f = ImageFont.truetype(os.path.join(HERE, name), size)
    if weight is not None:
        axes = f.get_variation_axes()
        vals = []
        for a in axes:
            n = a.get("name", b"")
            n = n.decode() if isinstance(n, bytes) else n
            if n.lower().startswith("weight"):
                vals.append(weight)
            elif n.lower().startswith("optical"):
                vals.append(max(a["minimum"], min(a["maximum"], size / 2)))
            else:
                vals.append(a["default"])
        f.set_variation_by_axes(vals)
    return f


def serif(size, w=400): return font("Newsreader.ttf", size, w)
def italic(size, w=400): return font("NewsreaderItalic.ttf", size, w)
def sans(size, w=500): return font("Inter.ttf", size, w)


def wrap(d, text, f, width):
    lines, line = [], ""
    for word in text.split():
        t = (line + " " + word).strip()
        if d.textlength(t, font=f) <= width:
            line = t
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def para(d, xy, text, f, width, fill, lead):
    x, y = xy
    for ln in wrap(d, text, f, width):
        d.text((x, y), ln, font=f, fill=fill)
        y += lead
    return y


def eyebrow(d, xy, text, color=MUTED, size=24):
    f = sans(size, 600)
    x, y = xy
    for ch in text.upper():
        d.text((x, y), ch, font=f, fill=color)
        x += d.textlength(ch, font=f) + size * 0.14
    return x


def canvas():
    im = Image.new("RGB", (W, H), PAPER)
    return im, ImageDraw.Draw(im)


def footer(d, n, total):
    d.line([(M, H - 92), (W - M, H - 92)], fill="#DDD2BE", width=2)
    d.text((M, H - 72), "wallywalks.app", font=sans(26, 500), fill=SLATE)
    t = f"{n} / {total}"
    d.text((W - M - d.textlength(t, font=sans(26, 500)), H - 72), t, font=sans(26, 500), fill=MUTED)


def sentences(text, n):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def drawing(im, path, top, height):
    pic = Image.open(path).convert("RGB")
    box_w = W
    scale = max(box_w / pic.width, height / pic.height)
    pic = pic.resize((round(pic.width * scale), round(pic.height * scale)), Image.LANCZOS)
    left = (pic.width - box_w) // 2
    tp = (pic.height - height) // 2
    im.paste(pic.crop((left, tp, left + box_w, tp + height)), (0, top))


def silhouette(im, cx, top, h):
    s = Image.open(os.path.join(APP, "public/images/brand/walker-silhouette.png")).convert("RGBA")
    w = round(s.width * h / s.height)
    s = s.resize((w, h), Image.LANCZOS)
    im.paste(s, (cx - w // 2, top), s)


def main():
    slides = []
    TOTAL = 6

    # 1. Cover
    im, d = canvas()
    silhouette(im, W // 2, 250, 300)
    t = "Wally Walks"
    f = serif(130, 500)
    d.text(((W - d.textlength(t, font=f)) / 2, 600), t, font=f, fill=INK)
    sub = "A hand-drawn walking guide to San Francisco"
    f2 = italic(44)
    d.text(((W - d.textlength(sub, font=f2)) / 2, 770), sub, font=f2, fill=SLATE)
    x0 = W // 2
    d.line([(x0 - 60, 880), (x0 + 60, 880)], fill=ACCENT, width=3)
    footer(d, 1, TOTAL)
    slides.append(im)

    # 2. The walk
    im, d = canvas()
    im.paste(Image.open(os.path.join(HERE, "map-band.png")).convert("RGB"), (0, 0))
    y = 680
    d.ellipse([M, y + 6, M + 18, y + 24], fill=ACCENT)
    eyebrow(d, (M + 34, y), "Telegraph Hill · North Beach")
    d.text((M, y + 50), data["title"], font=serif(68, 500), fill=INK)
    eyebrow(d, (M, y + 150), f"{data['distance']}  ·  {data['duration']}  ·  4 stops", color=SLATE, size=22)
    para(d, (M, y + 205), data["description"], serif(36), W - 2 * M, SLATE, 52)
    footer(d, 2, TOTAL)
    slides.append(im)


    def stop_slide(n, stop, img, story_n):
        im, d = canvas()
        drawing(im, os.path.join(APP, "public/images/stops", img), 0, 620)
        y = 670
        d.ellipse([M, y + 6, M + 18, y + 24], fill=ACCENT)
        eyebrow(d, (M + 34, y), stop["kind"])
        d.text((M, y + 46), stop["name"], font=serif(72, 500), fill=INK)
        x = eyebrow(d, (M, y + 160), "The story of this place", size=22)
        para(d, (M, y + 210), sentences(stop["history"], story_n), serif(35), W - 2 * M, INK, 50)
        footer(d, n, TOTAL)
        return im


    s = {x["id"]: x for x in data["stops"]}
    slides.append(stop_slide(3, s["caffe-trieste"], "caffe-trieste.jpg", 4))

    # 4. The app's own story quote for the stop
    im, d = canvas()
    silhouette(im, M + 40, 300, 150)
    q = sentences(data["quote"], 3)
    y = para(d, (M, 530), "“" + q + "”", italic(58), W - 2 * M, INK, 82)
    eyebrow(d, (M, y + 50), "Wally, on North Beach", color=ACCENT, size=26)
    footer(d, 4, TOTAL)
    slides.append(im)

    slides.append(stop_slide(5, s["filbert-steps"], "filbert-steps.jpg", 4))
    slides.append(stop_slide(6, s["coit-tower"], "coit-tower.jpg", 3))

    for i, im in enumerate(slides, 1):
        im.save(os.path.join(OUT, f"slide-{i}.png"))
    slides[0].save(os.path.join(OUT, "wallywalks-carousel.pdf"), save_all=True,
                   append_images=slides[1:], resolution=150)
    print("wrote", len(slides), "slides to", OUT)


if __name__ == "__main__":
    main()
