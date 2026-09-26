Edelman / McKinsey / Stripe Atlas annual-report aesthetic. Bold cover, full-bleed photography, color blocks, data spreads. Override on top of `design-tokens-base.md`.

## Color

- `--ink`: `#0E1A2B` (deep navy, near-black)
- `--ink-muted`: `#3D506B`
- `--ink-faint`: `#8A9BB0`
- `--paper`: `#FFFFFF` (pure white for printability; corporate aesthetic does not use cream)
- `--accent`: `#2563EB` (saturated default blue; swap for the owning organization's primary when the document has one)
- `--rule`: `#D5DDE7`

Color blocks for section openers may use full-bleed accent backgrounds with white text. These are intentional design elements, not page-wide background fills; print toner cost is acceptable for hero blocks but not for whole-page wash.

## Typography

- **Display font stack**: geometric grotesk family. If Söhne / Clash Display / Founders Grotesk are licensed, use them. Otherwise fall back to a system grotesk; never to Inter, Roboto, or Helvetica.
- **Body font stack**: `"Source Sans 3", "Söhne", "GT America", sans-serif`.
- **Numeric stack**: monospace for KPI numbers, financial tables, dates.

Scale:

- `--type-h1`: 36 pt (display)
- `--type-h2`: 22 pt
- `--type-h3`: 16 pt
- `--type-body`: 11 pt at 1.5 line-height
- `--type-caption`: 9 pt at 1.4 line-height
- `--type-micro`: 8.5 pt, letter-spacing 0.12em, uppercase

## Page rhythm

- Cover: large display title, eyebrow tag (microscopic uppercase) above. Full-bleed accent block behind title is allowed.
- KPI spreads: 4-column or 2x2 grid, each cell shows one big number plus a caption.
- Multi-column body: 2 columns at 9 pt body, gutter 0.3 in.

## What this aesthetic does well

Annual reports, investor decks, business reviews, market analyses. Data-heavy with strong narrative scaffolding.

## What this aesthetic does not do

Long-form reading without breaks. Casual or playful tone. Personal correspondence.

## Doc types built so far

None in v0.1. All corporate doc types are deferred until first real use triggers the build-template sub-interview.

## Related

- `design-tokens-base.md`
- `templates/corporate-annual-report.md` (not yet built)
- `templates/corporate-investor-deck.md` (not yet built)
- `templates/corporate-business-review.md` (not yet built)
- `templates/corporate-market-analysis.md` (not yet built)
