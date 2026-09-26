Stripe Press / editorial-grade aesthetic. Serif body, generous white space, restrained color, book-like. Override on top of `design-tokens-base.md`.

## Color (v0.1 print-friendly)

- `--ink`: `#111111` (near-black, warmer than pure black)
- `--ink-muted`: `#4A4A4A`
- `--ink-faint`: `#888888`
- `--paper`: `#FFFFFF` (pure white, do not change)
- `--accent`: `#A87617` (editorial gold, used only on blockquote left rules)
- `--rule`: `#C9C9C9` (hairline rule, neutral gray)
- `--shadow`: none (shadows do not print well; reserve for screen-only document types)

**Why the page is white:** the page background is always white. Cream paper was tried and rejected for two reasons. First, Chrome's print engine did not apply the body background to the full page consistently, creating a cream rectangle inside a white frame which read as sloppy. Second, putting a cream wash on a letter that will be printed burns through toner across the entire page. Page tone cannot vary by render mode either, so the `@media screen` vs `@media print` split is also banned for backgrounds.

Color on the page is allowed in two ways only: a thin colored rule (the gold left border on blockquotes) and `--ink` text. No background fills.

## Typography

- **Body font stack**: `"Source Serif 4", "Source Serif 4 Text", Georgia, serif` (the open-source successor to Source Serif Pro, available on Google Fonts; install it or link it before rendering).
- **Display font stack**: `"Source Serif 4 Display", Georgia, serif` for headlines. If you want PP Editorial New specifically, license it on the rendering machine before using.
- **Caption stack**: `"Source Serif 4 Caption", serif` for tiny-caps date lines, page numbers, etc.

Scale (overrides base):

- `--type-h1`: 28 pt (display)
- `--type-h2`: 20 pt
- `--type-h3`: 15 pt
- `--type-body`: 11 pt at 1.55 line-height
- `--type-caption`: 9-10 pt at 1.4 line-height
- `--type-micro`: 8 pt, letter-spacing 0.08em (avoid in formal-letter doc-type; reserve for research-report aesthetic)

## Page rhythm

- Body text is left-aligned with a natural ragged right edge. Do not justify; do not auto-hyphenate. Both create rivers or awkward breaks in formal prose.
- Drop caps allowed for chapter openers in research-report only.
- Margins default to 0.85 in (formal-letter) or 0.75 in / 1.0 in inside (research-report).

## What this aesthetic does well

Long-form prose, research reports, formal letters, white papers. Anywhere reading time exceeds 2 minutes and the document has gravitas.

## What this aesthetic does not do

Bold marketing, data-heavy KPI spreads, full-bleed photography. If the doc-type wants those, use `design-tokens-corporate.md` instead.

## Doc types built so far

- `templates/editorial-research-report.md`: research report scaffold with cover, abstract, body sections, references. v0.1.
- `templates/editorial-formal-letter.md`: formal letter scaffold. White page, gold accent on blockquote rules, no other color. Reusable for rebuttals, complaints, escalations.
- `templates/editorial-field-guide.md`: day-by-day field guide for a conference or trip. One day per page, a left time rail, talking-points blocks. The first template written for a document that is carried rather than read at a desk.

## Related

- `design-tokens-base.md`
- `templates/editorial-research-report.md`
- `templates/editorial-formal-letter.md`
- `templates/editorial-long-form-essay.md` (not yet built)
- `templates/editorial-white-paper.md` (not yet built)
- `templates/editorial-book-interior.md` (not yet built)
