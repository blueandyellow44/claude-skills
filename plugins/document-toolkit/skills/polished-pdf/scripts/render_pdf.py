#!/usr/bin/env python3
"""render_pdf.py: render an HTML document to PDF and QA it in one step.

Waits for web fonts, prints with backgrounds, then checks: page count, fonts
embedded in the PDF, the page ground color at the corners, em dashes in the text,
and writes page thumbnails for a visual pass.

Usage: python3 render_pdf.py draft.html out.pdf [--expect-fonts "Family A,Family B"] [--ground "#ffffff"] [--skip-ground-pages 1]
Needs: playwright with chromium (or system Chrome), pymupdf for QA.
"""
import argparse, asyncio, json, os, re, sys
from pathlib import Path

async def render(html, pdf, wait_ms):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception:
            browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": 1100, "height": 1400})
        await page.goto(Path(html).resolve().as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        await page.wait_for_timeout(wait_ms)
        loaded = await page.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/\"/g, '') + ' ' + f.weight + ' ' + f.style)")
        failed = await page.evaluate("[...document.fonts].filter(f => f.status === 'error').map(f => f.family)")
        await page.emulate_media(media="print")
        await page.pdf(path=pdf, print_background=True, prefer_css_page_size=True)
        await browser.close()
        return sorted(set(loaded)), failed

def qa(pdf, expect_fonts, ground, thumbs):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(pdf)
    fonts = set()
    type3 = 0
    for page in doc:
        for f in page.get_fonts():
            if f[2] == "Type3" or not f[3]:
                type3 += 1
            else:
                fonts.add(re.sub(r"^[A-Z]{6}[+]", "", f[3]))
    text = "".join(p.get_text() for p in doc)
    report = {"pages": len(doc), "embedded_fonts": sorted(fonts), "type3_fonts": type3, "em_dashes": text.count("\u2014")}
    squash = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    if expect_fonts:
        report["missing_fonts"] = [f for f in expect_fonts if not any(squash(f) in squash(x) for x in fonts)]
    corners = []
    thumbs.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=40)
        pix.save(thumbs / f"page-{i + 1:02d}.png")
        c = pix.pixel(2, 2)
        corners.append("#%02x%02x%02x" % tuple(c[:3]))
    report["corner_colors"] = corners
    if ground:
        g = tuple(int(ground.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4))
        report["pages_off_ground"] = [i + 1 for i, h in enumerate(corners)
                                      if sum(abs(a - int(h[1 + 2 * k:3 + 2 * k], 16)) for k, a in enumerate(g)) > 12]
    return report

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="input HTML file"); ap.add_argument("pdf", help="output PDF path")
    ap.add_argument("--expect-fonts", default="")
    ap.add_argument("--ground", default="")
    ap.add_argument("--wait-ms", type=int, default=600)
    ap.add_argument("--skip-ground-pages", default="", help="comma list of pages with an intended different ground, e.g. a dark cover: 1")
    a = ap.parse_args()
    loaded, failed = asyncio.run(render(a.html, a.pdf, a.wait_ms))
    exp = [x.strip() for x in a.expect_fonts.split(",") if x.strip()]
    rep = qa(a.pdf, exp, a.ground, Path(a.pdf).with_suffix("").parent / (Path(a.pdf).stem + "-thumbs"))
    # Chrome prints variable fonts as unnamed Type3 fonts, so a family can be present with no name in the PDF.
    # Count it as present when the browser loaded it and the PDF has Type3 fonts.
    if rep.get("missing_fonts") and rep["type3_fonts"]:
        squash = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        still = [f for f in rep["missing_fonts"] if not any(squash(f) in squash(l) for l in loaded)]
        rep["present_as_type3"] = [f for f in rep["missing_fonts"] if f not in still]
        rep["missing_fonts"] = still
    skip = {int(x) for x in a.skip_ground_pages.split(",") if x.strip()}
    if rep.get("pages_off_ground"):
        rep["pages_off_ground"] = [p for p in rep["pages_off_ground"] if p not in skip]
    rep["fonts_loaded_in_browser"] = loaded
    rep["fonts_failed_in_browser"] = failed
    print(json.dumps(rep, indent=2))
    bad = rep.get("missing_fonts") or failed or rep["em_dashes"] or rep.get("pages_off_ground")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
