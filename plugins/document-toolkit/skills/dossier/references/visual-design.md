# Dossier: visual design

Brand-color adaptation, the warm-neutral fallback palette, typography, and layout. Load this at the BUILD step, not during research or drafting.

## Brand color adaptation

The dossier borrows the subject's org colors so it feels connected to their world without looking like their marketing.

Map the extracted colors to these CSS variables:

```css
:root {
  --primary: <extracted primary>;   /* headers, title bars, section dividers */
  --dark: <primary darkened ~20%>;  /* cover name, darkest elements */
  --accent: <extracted accent>;     /* left accent bars on cards, highlights */
  --page: #FFFFFF;                  /* page, always white: print margins cannot be painted */
  --card: #F9F8F7;                  /* warm off-white cards, always */
  --text: #2D2A26;                  /* warm near-black body, always */
  --muted: #6B6560;                 /* captions and sources, always */
  --border: #E8E4E0;                /* warm border, always */
}
```

Rules:
- Page, card, text, muted, and border are FIXED. Only primary, dark, and accent adapt. The document stays readable whatever the brand.
- A very light primary (pastel, yellow, white) gets darkened. A near-black one gets lightened enough to separate from body text.
- Garish or high-saturation brands get desaturated 20 to 30 percent. The dossier should feel refined, not like a sports jersey.

## Warm neutral fallback

When colors cannot be extracted: primary `#5C524A`, dark `#3D3935`, accent `#C4956A`, with the fixed neutrals above.

## Typography

- One sans family for everything: `font-family: Inter, "Helvetica Neue", Arial, sans-serif;`
- Cover name: 28pt bold, `--dark`
- Section headers: 16pt bold, `--primary`
- Card titles: 13pt bold, `--primary`
- Body: 12pt, `--text`. Nothing below 10pt.
- Captions and sources: 10pt, `--muted`

## Layout

- US Letter portrait, 0.5in margins (`@page { size: Letter; margin: 0.5in; }`). Keep the page white: Chromium leaves print margins unpainted, so a tinted body background shows a white frame, and zero margins with body padding let text run to the edge of every page after the first.
- Card layout for every content section; a 4px left accent bar in `--accent` on each card
- 0.15in gap between cards; keep a card from splitting across pages (`break-inside: avoid`)
- The cover is its own page with no content sections
