Brand aesthetic applied to a product lookbook read on a phone. Read this file when Step 2 locks aesthetic = brand and doc-type = lookbook.

Why a separate template: `brand-internal-report` does not fit this work because its own "What this template does not handle" list names full-bleed photography, which is the entire substance of a lookbook.

## What makes this template different

Three departures from every other doc type in this skill, each forced by the work rather than chosen for style:

1. **Phone geometry, not Letter.** The reader opens this on a phone while travelling. A Letter page on a phone is a pinch-and-zoom document. The page is 9:16 so one page fills one screen and the whole thing reads as a vertical flip.
2. **The ground changes by section, not by render mode.** Each tier owns a colour field. This is the magazine chaptering device and it is compliant with the banned-token rule, which forbids a ground that varies between screen and print, not one that varies between sections. Every page's tone is identical in both render modes.
3. **No prose blocks at all.** A lookbook carries a name and one line per piece. If a paragraph appears, the template is being misused.

## Content-block schema (refusal gate input)

| Block | Required | Description |
|---|---|---|
| `title` | yes | Cover title. Two or three words. |
| `subtitle` | no | One line under the title. |
| `brand.name` | yes | Organization name for the cover eyebrow. |
| `brand.ground` | yes | Primary dark ground hex. |
| `brand.accent` | yes | Accent hex. |
| `brand.pale` | yes | Pale or bone hex, used as a section ground. |
| `cover.image` | yes | Full-bleed hero image path. |
| `sections` | yes | 2 to 5 sections, each with `label`, `title`, `line`, `ground`, `ink`, and `plates`. |
| `sections[].plates` | yes | 3 to 8 plates per section, each with `image`, `name`, and `line`. |
| `closer.line` | no | Final page line. |

If `sections` is empty, or any section has zero plates, Step 3 refuses to proceed.

## Page geometry

- Page: 5in x 8.89in (9:16). No margin at the page level; every page is full-bleed and manages its own inset.
- Safe inset for type: 0.42in.
- One plate per page. Never two. A phone screen holds one image.

## Page kinds

- **Cover.** Full-bleed hero, ground field over the lower third, brand eyebrow, title in display, hairline rule in accent.
- **Section opener.** Solid colour field, no image. Oversized section number, section title, one line. This is the only page where type fills the frame.
- **Plate.** Full-bleed image across the upper two thirds, colour field below carrying the piece name and one line. The field colour is the section's ground.
- **Closer.** Solid ground, mark centred, one line.

## Render notes

- Images are embedded as base64 data URIs so the HTML previews and prints identically with no file dependencies.
- Every image uses `object-fit: cover` so it fills its band edge to edge. A letterboxed image on a lookbook page reads as a slide deck.
- Chrome headless renders with `--print-to-pdf --no-pdf-header-footer`. The `@page` size must match the CSS page height exactly or Chrome inserts blank pages.

## Hard rules

1. No research citations, no methodology, no caveats, no production notes. Those belong in the review page, not the lookbook.
2. No paragraphs. A name and one line per plate.
3. No shadows.
4. Each section's ground is one value applied in both screen and print.
5. No em dashes and no contractions in any line.
6. One plate per page.
7. No invented contact details, URLs, prices, or dates.

## Variance hooks

- Section ground sequence: dark to pale to accent, or the reverse.
- Cover: hero above field, or field above hero.
- Plate field: name over line, or name beside line.

## What this template does not handle

- Body copy of any length.
- Tables, data, or figures.
- Anything intended to be read on paper first.

## Related

- `design-tokens-base.md`
- `design-tokens-brand.md`
- `soft-ui-patterns.md`
- `interface-design-patterns.md`
