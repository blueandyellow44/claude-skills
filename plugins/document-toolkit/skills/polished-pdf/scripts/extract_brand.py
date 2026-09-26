#!/usr/bin/env python3
"""extract_brand.py: pull a brand's visual system out of whatever evidence exists.

Accepts any mix of: a brand folder, a brand guide PDF, a website snapshot PDF,
logo SVG/PNG files, CSS or JSON token files, font files, a local HTML page, or a
live URL. Writes <out>/brand_profile.json, <out>/brand_summary.md, page thumbnails,
and any usable font files it can recover.

It gathers evidence and proposes roles. It does not decide the design. Read the
summary, look at the thumbnails, and confirm roles against the source before use.

Dependencies, all optional and degraded gracefully:
  pymupdf (PDF fonts, colors, thumbnails)   pip install pymupdf
  pillow  (raster color clustering)          pip install pillow
  playwright + chromium (live URL styles)    pip install playwright
Usage:
  python3 extract_brand.py <source> [<source> ...] --out ./brand-profile
"""
import argparse, colorsys, json, os, re, sys, urllib.request, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)")
VAR_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]+);")
FF_RE = re.compile(r"font-family\s*:\s*([^;}{]+)[;}]")
FACE_RE = re.compile(r"@font-face\s*{([^}]*)}", re.S)
GENERIC = {"serif", "sans-serif", "monospace", "system-ui", "cursive", "fantasy", "inherit",
           "initial", "ui-sans-serif", "ui-serif", "ui-monospace", "-apple-system",
           "blinkmacsystemfont", "var"}

def norm_hex(h):
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h

def rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))

def hex_to_rgb(h):
    h = norm_hex(h)
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

def chroma(h):
    r, g, b = [v / 255 for v in hex_to_rgb(h)]
    _, l, s = colorsys.rgb_to_hls(r, g, b)
    return s * (1 - abs(2 * l - 1))

def lightness(h):
    r, g, b = [v / 255 for v in hex_to_rgb(h)]
    return colorsys.rgb_to_hls(r, g, b)[1]

def merge_close(counter, tol=18):
    """Merge near-identical colors so anti-aliasing noise does not split a swatch."""
    out = []
    for h, w in counter.most_common():
        rgb = hex_to_rgb(h)
        for item in out:
            if sum(abs(a - b) for a, b in zip(rgb, hex_to_rgb(item[0]))) <= tol:
                item[1] += w
                break
        else:
            out.append([h, w])
    return out

def clean_font_name(name):
    name = re.sub(r"^[A-Z]{6}\+", "", name.strip().strip("'\""))
    base = re.split(r"[-,]", name)[0]
    base = re.sub(r"(Variable|VF|Regular|Bold|Italic|Medium|Light|SemiBold|Semibold|Black|Book|Roman|Text|Display)$", "", base)
    base = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", base).strip()
    return base or name

def local_font_index():
    names = set()
    for d in ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts"), "/usr/share/fonts", os.path.expanduser("~/.local/share/fonts")]:
        for root, _, files in os.walk(d):
            for fn in files:
                names.add(fn.lower().replace(" ", "").replace("-", ""))
    return names

def google_fonts_has(family):
    url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(family)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False

class Profile:
    def __init__(self):
        self.sources = []
        self.text_colors = Counter()     # weighted by characters
        self.fill_colors = Counter()     # weighted by area
        self.raster_colors = Counter()   # weighted by pixel share
        self.declared = []               # hex values written in a guide, with context
        self.css_vars = {}
        self.fonts = defaultdict(lambda: {"chars": 0, "sizes": Counter(), "seen_in": set(), "embedded": False})
        self.font_faces = []
        self.font_files = []
        self.logos = []
        self.thumbnails = []
        self.notes = []
        self.font_mentions = Counter()

    def font(self, name, chars=0, size=None, where=""):
        n = clean_font_name(name)
        if not n or n.lower() in GENERIC:
            return None
        f = self.fonts[n]
        f["chars"] += chars
        if size:
            f["sizes"][round(size)] += chars or 1
        if where:
            f["seen_in"].add(where)
        return f

def raster_colors(img_path, prof, weight=1.0):
    try:
        from PIL import Image
    except ImportError:
        prof.notes.append("pillow missing: raster color clustering skipped")
        return
    im = Image.open(img_path).convert("RGB")
    im.thumbnail((400, 400))
    q = im.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    total = im.width * im.height
    for count, idx in q.getcolors():
        r, g, b = pal[idx * 3: idx * 3 + 3]
        prof.raster_colors[rgb_to_hex(r, g, b)] += weight * count / total

def do_pdf(path, prof, out, max_pages):
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            prof.notes.append(f"pymupdf missing: skipped {path}")
            return
    doc = fitz.open(path)
    tag = Path(path).name
    prof.sources.append({"type": "pdf", "path": str(path), "pages": len(doc)})
    font_dir = out / "fonts"
    seen_xref = set()
    for pno, page in enumerate(doc):
        if pno >= max_pages:
            break
        area = page.rect.width * page.rect.height
        for xref, ext, ftype, basefont, *_ in page.get_fonts(full=True):
            f = prof.font(basefont, where=tag)
            if f is not None and ext not in ("n/a", "") and xref not in seen_xref:
                seen_xref.add(xref)
                f["embedded"] = True
                try:
                    name, fext, _, buf = doc.extract_font(xref)
                    if buf and fext in ("ttf", "otf", "cff", "pfa", "pfb"):
                        font_dir.mkdir(exist_ok=True)
                        fp = font_dir / f"{re.sub(r'[^A-Za-z0-9+-]', '_', basefont)}.{fext}"
                        fp.write_bytes(buf)
                        prof.font_files.append({"file": str(fp), "font": basefont,
                                                "subset": bool(re.match(r'^[A-Z]{6}\+', basefont))})
                except Exception:
                    pass
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    n = len(txt.strip())
                    if not n:
                        continue
                    c = span.get("color", 0)
                    prof.text_colors[rgb_to_hex((c >> 16) & 255, (c >> 8) & 255, c & 255)] += n
                    prof.font(span.get("font", ""), n, span.get("size"), tag)
        text = page.get_text()
        if re.search(r"typeface|typography|font|type family|display face|body face|typeset", text, re.I):
            for run in re.findall(r"\b([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3})\b", text):
                run = " ".join(x.capitalize() if x.isupper() and len(x) > 3 else x for x in run.split())
                w = run.split()
                for i in range(len(w)):
                    for j in range(i + 1, min(i + 3, len(w)) + 1):
                        prof.font_mentions[" ".join(w[i:j])] += 1
        for m in HEX_RE.finditer(text):
            s = max(0, m.start() - 40)
            ctx = " ".join(text[s:m.end() + 30].split())
            prof.declared.append({"hex": norm_hex(m.group()), "context": ctx, "source": f"{tag} p{pno + 1}"})
        for dr in page.get_drawings():
            fill = dr.get("fill")
            if fill and dr.get("rect") is not None:
                r = dr["rect"]
                a = abs(r.width * r.height) / area
                if a > 0.0005:
                    prof.fill_colors[rgb_to_hex(*(v * 255 for v in fill))] += a
        if pno < 6:
            (out / "thumbs").mkdir(exist_ok=True)
            tp = out / "thumbs" / f"{Path(path).stem}-p{pno + 1}.png"
            page.get_pixmap(dpi=60).save(tp)
            prof.thumbnails.append(str(tp))
            raster_colors(tp, prof)

def do_css(text, prof, where):
    for k, v in VAR_RE.findall(text):
        prof.css_vars[k] = v.strip()
    for m in FF_RE.findall(text):
        if "var(" in m:
            continue
        for fam in m.split(","):
            prof.font(fam, 1, where=where)
    for body in FACE_RE.findall(text):
        fam = re.search(r"font-family\s*:\s*([^;]+);", body)
        src = re.search(r"src\s*:\s*([^;]+);", body)
        wt = re.search(r"font-weight\s*:\s*([^;]+);", body)
        if fam:
            prof.font_faces.append({"family": fam.group(1).strip().strip("'\""),
                                    "src": src.group(1).strip() if src else "",
                                    "weight": wt.group(1).strip() if wt else "", "source": where})
            prof.font(fam.group(1), 0, where=where)
    for h in HEX_RE.findall(text):
        prof.fill_colors[norm_hex(h)] += 0.01
    for r, g, b in RGB_RE.findall(text):
        prof.fill_colors[rgb_to_hex(r, g, b)] += 0.01

def do_svg(path, prof):
    t = Path(path).read_text(errors="ignore")
    colors = Counter(norm_hex(h) for h in HEX_RE.findall(t))
    fams = set(re.findall(r"font-family[=:]\s*['\"]?([^'\";>]+)", t))
    name = Path(path).name.lower()
    tone = "negative" if any(k in name for k in ("negative", "reverse", "white", "knockout", "dark")) else \
           "positive" if any(k in name for k in ("positive", "black", "color", "primary")) else "unknown"
    kind = next((k for k in ("wordmark", "monogram", "lockup", "stacked", "horizontal", "icon", "mark", "badge", "favicon") if k in name), "logo")
    has_text = "<text" in t
    prof.logos.append({"file": str(path), "kind": kind, "tone": tone, "colors": dict(colors),
                       "outlined": not has_text, "fonts": sorted(fams)})
    for h, n in colors.items():
        prof.fill_colors[h] += 0.02 * n

def do_url(url, prof, out):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        prof.notes.append("playwright missing: static fetch only for " + url)
        return do_url_static(url, prof)
    js = """() => {
      const pick = s => [...document.querySelectorAll(s)].slice(0, 6);
      const roles = {body:'body', h1:'h1', h2:'h2', h3:'h3', p:'p', link:'a', button:'button, .btn, [class*=button]', nav:'nav, header', label:'small, .eyebrow, [class*=label], [class*=kicker]'};
      const res = {};
      for (const [k, s] of Object.entries(roles)) res[k] = pick(s).map(el => { const c = getComputedStyle(el);
        return {font: c.fontFamily, size: c.fontSize, weight: c.fontWeight, ls: c.letterSpacing, tt: c.textTransform,
                color: c.color, bg: c.backgroundColor, radius: c.borderRadius, chars: (el.innerText||'').length}; });
      const vars = {}; for (const sh of document.styleSheets) { try { for (const r of sh.cssRules) {
        if (r.selectorText === ':root' && r.style) for (const p of r.style) if (p.startsWith('--')) vars[p] = r.style.getPropertyValue(p).trim(); } } catch(e) {} }
      const logos = [...document.querySelectorAll('img, svg')].filter(el => /logo|brand|wordmark|mark/i.test((el.outerHTML||'').slice(0,300))).slice(0,6)
        .map(el => el.tagName === 'IMG' ? {src: el.currentSrc || el.src, alt: el.alt} : {svg: el.outerHTML.slice(0, 4000)});
      const loaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g,'') + ' ' + f.weight);
      return {res, vars, logos, loaded, title: document.title};
    }"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        pg.goto(url, wait_until="networkidle", timeout=45000)
        pg.evaluate("document.fonts.ready")
        data = pg.evaluate(js)
        (out / "thumbs").mkdir(exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", url.lower())[:60]
        shot = out / "thumbs" / f"{slug}.png"
        pg.screenshot(path=str(shot), full_page=False)
        pg.set_viewport_size({"width": 400, "height": 900})
        mshot = out / "thumbs" / f"{slug}-mobile.png"
        pg.screenshot(path=str(mshot))
        b.close()
    prof.sources.append({"type": "url", "url": url, "title": data.get("title")})
    prof.thumbnails += [str(shot), str(mshot)]
    raster_colors(shot, prof, weight=2.0)
    prof.css_vars.update(data["vars"])
    prof.web_roles = data["res"]
    prof.web_loaded_fonts = data["loaded"]
    for role, items in data["res"].items():
        for it in items:
            m = RGB_RE.search(it["color"])
            if m:
                prof.text_colors[rgb_to_hex(*m.groups())] += max(it["chars"], 1)
            m = RGB_RE.search(it["bg"])
            if m and "rgba(0, 0, 0, 0)" not in it["bg"]:
                prof.fill_colors[rgb_to_hex(*m.groups())] += 0.05
            for fam in it["font"].split(","):
                prof.font(fam, it["chars"], float(it["size"].rstrip("px")) * 0.75, "web:" + role)
    for lg in data["logos"]:
        prof.logos.append({"file": lg.get("src") or "inline-svg", "kind": "web-logo", "tone": "unknown",
                           "colors": dict(Counter(norm_hex(h) for h in HEX_RE.findall(lg.get("svg", "")))), "outlined": True, "fonts": []})

def do_url_static(url, prof):
    def get(u):
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", "ignore")
    html = get(url)
    prof.sources.append({"type": "url-static", "url": url})
    do_css(" ".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)), prof, "inline-style")
    for href in re.findall(r"<link[^>]+rel=[\"']?stylesheet[^>]+href=[\"']([^\"']+)", html)[:12]:
        try:
            do_css(get(urllib.parse.urljoin(url, href)), prof, href)
        except Exception as e:
            prof.notes.append(f"css fetch failed {href}: {e}")

def walk(src, prof, out, max_pages):
    s = str(src)
    if s.startswith("http://") or s.startswith("https://"):
        return do_url(s, prof, out)
    p = Path(src)
    if p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file() and not any(part.startswith(".") for part in f.parts):
                walk(f, prof, out, max_pages)
        return
    ext = p.suffix.lower()
    if ext == ".pdf":
        do_pdf(p, prof, out, max_pages)
    elif ext == ".svg":
        do_svg(p, prof)
    elif ext in (".png", ".jpg", ".jpeg", ".webp"):
        if re.search(r"logo|wordmark|monogram|mark|lockup", p.name, re.I):
            prof.logos.append({"file": str(p), "kind": "raster-logo", "tone": "unknown", "colors": {}, "outlined": False, "fonts": []})
    elif ext in (".css", ".scss"):
        do_css(p.read_text(errors="ignore"), prof, p.name)
    elif ext in (".html", ".htm"):
        do_css(" ".join(re.findall(r"<style[^>]*>(.*?)</style>", p.read_text(errors="ignore"), re.S)), prof, p.name)
    elif ext == ".json":
        t = p.read_text(errors="ignore")
        if HEX_RE.search(t) or "font" in t.lower():
            for m in HEX_RE.finditer(t):
                s0 = max(0, m.start() - 50)
                prof.declared.append({"hex": norm_hex(m.group()), "context": " ".join(t[s0:m.end()].split()), "source": p.name})
    elif ext in (".woff2", ".woff", ".ttf", ".otf"):
        prof.font_files.append({"file": str(p), "font": p.stem, "subset": False})

def propose(prof):
    """Propose roles from evidence. Declared values in a guide outrank measured ones."""
    fills = merge_close(prof.fill_colors + Counter({k: v * 3 for k, v in prof.raster_colors.items()}))
    texts = merge_close(prof.text_colors)
    total_fill = sum(w for _, w in fills) or 1
    light = [(h, w) for h, w in fills if lightness(h) > 0.82]
    dark = [(h, w) for h, w in fills if lightness(h) < 0.22]
    sat = [(h, w) for h, w in fills + [(h, w / 500) for h, w in texts] if chroma(h) > 0.18 and 0.15 < lightness(h) < 0.85]
    sat = merge_close(Counter({h: w for h, w in sat}))
    roles = {
        "ground": light[0][0] if light else None,
        "ground_share": round(light[0][1] / total_fill, 3) if light else None,
        "ink": texts[0][0] if texts else (dark[0][0] if dark else None),
        "dark_field": dark[0][0] if dark else None,
        "accent": sat[0][0] if sat else None,
        "support": sat[1][0] if len(sat) > 1 else None,
        "accent_share": round(sat[0][1] / total_fill, 3) if sat else None,
    }
    fonts = sorted(((n, f) for n, f in prof.fonts.items() if not n.startswith("Type3")), key=lambda kv: -kv[1]["chars"])
    def avg_size(f):
        s = f["sizes"]
        return sum(k * v for k, v in s.items()) / max(sum(s.values()), 1) if s else 0
    body = fonts[0][0] if fonts else None
    display = max(fonts, key=lambda kv: avg_size(kv[1]) if kv[1]["chars"] > 3 else 0)[0] if fonts else None
    mono = next((n for n, _ in fonts if re.search(r"mono|code|courier", n, re.I)), None)
    type_roles = {"body": body, "display": display, "mono_or_label": mono}
    return roles, type_roles, fills[:14], texts[:8]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", help="brand folder, guide PDF, logo files, CSS or JSON tokens, local HTML, or a URL")
    ap.add_argument("--out", default="brand-profile")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--no-network", action="store_true", help="skip Google Fonts availability checks")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prof = Profile()
    for s in a.sources:
        try:
            walk(s, prof, out, a.max_pages)
        except Exception as e:
            prof.notes.append(f"failed on {s}: {e}")
    roles, type_roles, fills, texts = propose(prof)
    fonts = []
    for name, f in sorted(prof.fonts.items(), key=lambda kv: -kv[1]["chars"])[:12]:
        entry = {"family": name, "chars": f["chars"], "common_sizes_pt": [k for k, _ in f["sizes"].most_common(4)],
                 "embedded_in_pdf": f["embedded"], "seen_in": sorted(f["seen_in"])[:6],
                 "self_hosted_face": any(ff["family"].lower() == name.lower() for ff in prof.font_faces)}
        if not a.no_network:
            entry["on_google_fonts"] = google_fonts_has(name)
        fonts.append(entry)
    stated_fonts = []
    if not a.no_network:
        known = {f["family"].lower() for f in fonts}
        stop = {"And", "Caps", "Contents", "Guidelines", "Wordmark", "Monogram", "Not", "Inside", "These", "Headline", "Label", "Lede", "Text", "Interface", "Editorial", "Abcdefghijklmnopqrstuvwxyz", "Aa", "Aag", "The", "This", "Use", "Body", "Display", "Type", "Typeface", "Typography", "Font", "Brand", "Logo", "Color", "Colour", "Primary", "Secondary", "Regular", "Italic", "Bold", "Medium", "Light", "Headline", "Headlines", "Caption", "Captions", "Mono", "Sans", "Serif", "Never", "Always", "Do", "Don"}
        checked = 0
        for cand, n in prof.font_mentions.most_common(60):
            if cand in stop or len(cand) < 4 or cand.isupper() or all(x in stop for x in cand.split()) or cand.split()[0] in stop or any(cand.lower() in k for k in known):
                continue
            if checked >= 45:
                break
            checked += 1
            if google_fonts_has(cand):
                # drop a shorter family already covered by a longer confirmed name, e.g. "Plex Mono" under "IBM Plex Mono"
                if not any(cand in x["family"] for x in stated_fonts):
                    stated_fonts.append({"family": cand, "mentions": n, "on_google_fonts": True})
    local = local_font_index()
    for f in fonts + stated_fonts:
        f["installed_locally"] = any(f["family"].lower().replace(" ", "") in x for x in local)
    for k, v in prof.css_vars.items():
        if re.search(r"brand|primary|accent|ink|ground|paper|surface|bg|background|text|highlight", k, re.I):
            m = HEX_RE.search(v) or RGB_RE.search(v)
            if m:
                hx = norm_hex(m.group()) if m.group().startswith("#") else rgb_to_hex(*m.groups())
                prof.declared.append({"hex": hx, "context": f"CSS variable {k}", "source": "css"})
    declared = {}
    for d in prof.declared:
        declared.setdefault(d["hex"], d)
    data = {
        "sources": prof.sources, "proposed_color_roles": roles, "proposed_type_roles": type_roles,
        "declared_colors": list(declared.values())[:40], "css_variables": dict(list(prof.css_vars.items())[:80]),
        "measured_fill_colors": [{"hex": h, "weight": round(w, 4)} for h, w in fills],
        "measured_text_colors": [{"hex": h, "chars": int(w)} for h, w in texts],
        "fonts": fonts, "fonts_named_in_guide": stated_fonts, "font_faces": prof.font_faces[:30], "recovered_font_files": prof.font_files[:30],
        "logos": prof.logos[:30], "thumbnails": prof.thumbnails[:40],
        "web_roles": getattr(prof, "web_roles", None), "web_loaded_fonts": getattr(prof, "web_loaded_fonts", None),
        "notes": prof.notes,
    }
    (out / "brand_profile.json").write_text(json.dumps(data, indent=2))
    L = ["# Brand evidence summary", "", "Proposed roles are guesses from measurement. Confirm each against the thumbnails and any values the guide states outright.", ""]
    L.append("## Colors stated in the source (strongest evidence)")
    L += [f"- `{d['hex']}` ({d['source']}): {d['context']}" for d in list(declared.values())[:24]] or ["- none found"]
    L += ["", "## Proposed color roles"] + [f"- {k}: `{v}`" for k, v in roles.items()]
    L += ["", "## Measured fills (area-weighted)"] + [f"- `{h}` {w:.3f}" for h, w in fills]
    L += ["", "## Measured text colors (character-weighted)"] + [f"- `{h}` {int(w)} chars" for h, w in texts]
    L += ["", "## Fonts"] + [f"- **{f['family']}**: {f['chars']} chars, sizes {f['common_sizes_pt']}, embedded {f['embedded_in_pdf']}, self-hosted {f['self_hosted_face']}, Google Fonts {f.get('on_google_fonts', 'unchecked')}" for f in fonts]
    L += ["", "## Font families named in the guide text and available on Google Fonts"] + ([f"- **{f['family']}** ({f['mentions']} mentions), installed locally {f['installed_locally']}" for f in stated_fonts] or ["- none confirmed"])
    L += ["", "PDF fonts listed as Type3 are usually web or variable fonts flattened by a browser print. Their real names are lost, so trust the named families above and the guide's own typography page instead.", "", f"Proposed type roles: {type_roles}", "", "## Logos"]
    L += [f"- {l['kind']} / {l['tone']} / outlined {l['outlined']}: `{l['file']}` colors {l['colors']}" for l in prof.logos[:20]] or ["- none found"]
    if prof.css_vars:
        L += ["", "## CSS custom properties"] + [f"- `{k}`: {v}" for k, v in list(prof.css_vars.items())[:60]]
    L += ["", "## Recovered font files"] + [f"- `{x['file']}`{' (SUBSET: missing glyphs likely, do not ship as the text face)' if x['subset'] else ''}" for x in prof.font_files[:20]]
    if prof.notes:
        L += ["", "## Notes"] + [f"- {n}" for n in prof.notes]
    (out / "brand_summary.md").write_text("\n".join(L) + "\n")
    print(f"wrote {out/'brand_profile.json'} and {out/'brand_summary.md'}")
    print(json.dumps({"roles": roles, "type": type_roles}, indent=1))

if __name__ == "__main__":
    main()
