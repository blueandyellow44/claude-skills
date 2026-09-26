Warm travel-brief / planning-document aesthetic. Full-bleed location photography, a warm cream page (not white), a rotating rust/gold/brown accent set, colored stat tiles and table headers. Override on top of `design-tokens-base.md`. This is the one aesthetic in this skill that is allowed a non-white page background: see the carve-out in `design-tokens-base.md`.

**Not a default for branded work.** This palette is a generic aesthetic option like editorial, corporate and brand, not any organization's visual identity. When a document belongs to an organization with its own brand, use that brand (the `brand` aesthetic or the Match path), and pick `warm` only if the user explicitly chooses it at Step 1 for that specific document.

## Color

- `--ink`: `#221609` (warm near-black)
- `--ink-muted`: `#5C4A34`
- `--ink-faint`: `#8A7A62`
- `--paper`: `#F2E7D0` (warm cream/parchment. This is the sanctioned exception to the base white-page rule; see below for the Chrome print gotcha this requires handling.)
- `--paper-card`: `#FFFFFF` (cards and tables sit on white against the cream page for contrast; do not make the whole page white)
- `--tile`: `#EADFC3` (stat tiles and callout bands, one step darker than `--paper`)
- `--accent-rust`: `#B5451C`
- `--accent-gold`: `#C08A2E`
- `--accent-brown`: `#6E4A2E`
- `--cover-band`: `#241608` (the dark band behind cover and location-page titles)
- `--rule`: `#D9C9A6` (hairline rules on the cream page)
- `--shadow`: none (shadows do not print reliably; reserve for screen-only variants)

Accent rotation: assign `--accent-rust`, `--accent-gold`, `--accent-brown` in a fixed repeating order to sibling cards in a grid (left border, 3-4pt) and to the short rule under a section headline. Never randomize the order and never use more than these three within one document; a fourth color reads as decoration rather than a system.

**Chrome print-background gotcha, and the actual fix.** `design-tokens-editorial.md` records that a cream background failed to render reliably in Chrome's print engine during the v0.1 test, which is why that aesthetic locked to white. The missing piece was `-webkit-print-color-adjust: exact` and `print-color-adjust: exact` on `html, body` and on every colored block (table headers, tiles, cover band, card borders). Without it, Chrome's headless print path can drop background colors to save toner. Set both properties globally in this aesthetic's base stylesheet and verify on the first real render (rasterize every page, confirm the cream background and accent fills survived print, not just screen preview) before calling it done.

## Typography

- **Display / heading font stack**: `"Charter", "Georgia", serif` (Charter ships with macOS; Georgia is the fallback elsewhere). Bold weight for h1/h2; italic weight for subheads and pull lines, and a mixed bold-and-italic treatment on the cover title.
- **Body font stack**: `"Charter", "Georgia", serif`, regular weight.
- **Label / kicker / running-header stack**: `"Avenir Next", "Futura", sans-serif` (both ship with macOS; confirm on other systems), uppercase, letter-spacing 0.12em, used only for kickers, running headers/footers, page numbers, and table headers. Never for body prose or headlines.

Scale (overrides base):

- `--type-display`: 40 pt bold serif (cover title)
- `--type-h1`: 26 pt bold serif (section headline)
- `--type-h2`: 20 pt bold serif (location/card-group names)
- `--type-h3`: 14 pt bold serif (card subheads)
- `--type-body`: 11 pt at 1.5 line-height
- `--type-caption`: 9.5 pt italic serif (subheads under a headline, "what this section is really about" lines)
- `--type-micro`: 8 pt sans, letter-spacing 0.12em, uppercase (kickers, running header/footer, page numbers, table headers)

## Page rhythm

- Letter portrait default, 0.75 in outer margins, matching `design-tokens-base.md`; the cover and any full-bleed location-photo page are the only pages allowed to break the margin, and only at the top edge for the photo itself.
- Running header on every interior page: left side carries a numbered section kicker ("01 · WHERE THIS STANDS"), right side carries the page number ("2/22"). Running footer, centered, carries the document's short title, a subject tag, and the date, all in `--type-micro`.
- Section openers: kicker label, then h1, then a short accent-colored rule (one of the three rotation colors, ~2pt tall, ~60pt wide) directly under the headline, then an italic one-to-two sentence framing line before the body content starts.
- Cards: white fill, thin `--rule` border, one accent-colored left border (3-4pt) assigned by the rotation. Used for parallel content: timeline phases, weekly-rhythm blocks, city or option profiles, callouts.
- Stat tiles: `--tile` fill, no border, `--type-micro` kicker label over a large bold serif number or short value. Group 2-4 across a row.
- Tables: header row solid `--accent-rust` fill, white `--type-micro` text; body rows alternate `--paper-card` and a faint tint of `--tile` for readability at 20+ rows.
- Full-bleed location/profile pages: a photograph fills roughly the top third to half of the page, edge to edge; a `--cover-band` colored block sits at the bottom-left corner of the photo carrying the location name in white bold serif (`--type-h2` or larger); body content continues below on the cream page.
- Left-aligned body text, ragged right, same as editorial. Do not justify.

## What this aesthetic does well

Planning documents, decision briefs, options memos, travel or relocation research, anything that pairs real photography with a personal or high-stakes decision and benefits from feeling considered rather than institutional. Reader carries it, annotates it, comes back to specific sections.

## What this aesthetic does not do

Formal correspondence, anything requiring strict institutional restraint (a rebuttal, a filing, a complaint letter), third-party brand identity work (use `brand`, with real brand assets, not this aesthetic's palette), long unbroken prose reading (its rhythm is built for scannable sections, not chapters).

## Doc types built so far

None yet. First real use triggers the Step 2 build-template sub-interview in `SKILL.md`, the same path that produced `brand-lookbook.md` and `editorial-field-guide.md`.

## Related

- `design-tokens-base.md` (carries the sanctioned non-white-page exception for this aesthetic)
- `design-tokens-editorial.md` (the restrained sibling this aesthetic deliberately departs from)
- `design-tokens-brand.md` and `brand-matching.md` (use these, not this palette, for an organization's own branded documents)
