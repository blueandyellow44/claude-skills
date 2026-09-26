# Brand matching

Read this file when Step 1 takes the **Match a brand** path: the document should look like it came from a specific company, product, publication or website. The job is to reproduce that organization's existing visual system in print, faithfully, and to invent nothing it does not already have.

The ownership test in `design-tokens-brand.md` still comes first: never put one organization's brand on another organization's document. Resolve whose document this is before a mark, color or font goes on the page.

## When matching is allowed

- **The document belongs to the brand.** It is written by, for, or inside the organization: its own board report, client deliverable, internal memo, proposal on its letterhead, or an organization the user has been engaged by. This includes invented companies whose brand materials are supplied in the working folder.
- **The user has the right to use the brand for this document.** A client engagement, the user's own organization, a partner who asked for it.
- **Not allowed, whatever the stated purpose.** A document that would pass as a real organization's official material to someone outside it: a fake statement, notice, invoice, press release, login or support page, or a competitor's document in the rival's clothing. Reference a real site's craft (grid, rhythm, type scale) for an original brand if the user asks, but do not lift its marks, name or signature colors onto it.

If ownership is unclear and the user is reachable, ask. If no human will answer (an unattended or scripted run), match only brands whose materials were supplied in the working folder as that organization's own, and write the assumption into the build notes.

## Evidence, in order of authority

Stronger evidence overrides weaker evidence. Record which source each token came from.

1. **Machine tokens.** `tokens.css`, `tokens.json`, design-system packages, CSS custom properties, Figma exports. Exact values, named roles.
2. **The brand guide's own words.** Hex values, named colors, typeface names, weights, tracking, case rules, logo clear space, minimum sizes, do and do-not pages. A guide that says "emphasis comes from italics, never from bold" is a rule, not a suggestion.
3. **Supplied logo files.** Use the file itself. Positive and negative versions tell you which grounds the brand sits on. Never redraw, retype or recolor a mark. Check each SVG for a baked background plate (a full-size rect in a second color, which the extractor shows as two colors on a negative file). A plated mark only sits cleanly on a field of exactly the plate color, so either set that field to the plate color or use a plate-free version.
4. **The live site or a site snapshot.** Computed styles show what the brand actually does, including how much of the accent it really uses.
5. **Other company documents.** Existing decks, reports and one-pagers show how the brand already translates to paper. When they conflict with the guide, the guide wins for identity and the documents win for document conventions (table style, chart style, footers).
6. **Photography and illustration.** Treatment, crop, color grade. Reuse supplied images only where they carry information, never as filler.

## Run the extractor first

```sh
python3 scripts/extract_brand.py <brand folder, guide PDF, logo files, css, or URL> --out <workdir>/brand-profile
```

It writes `brand_profile.json`, `brand_summary.md`, page thumbnails, and any font files it can recover. It degrades without pymupdf, pillow or playwright; install what is missing (`pip install pymupdf pillow playwright` then `playwright install chromium`) when the environment allows.

What it does and does not know:

- **Declared colors** are hex values found in guide text or role-named CSS variables, with surrounding words. These are the strongest color evidence. Map names ("Primary ground", "Accent") to roles from that context.
- **Measured colors** are area-weighted fills and character-weighted text colors. They show proportion: an accent covering 0.6 percent of the guide is used sparingly, and the document must be just as sparing.
- **Fonts listed as `Type3`** are browser-printed web or variable fonts whose names were flattened. Trust `fonts_named_in_guide` and the guide's typography page instead.
- **Recovered subset fonts** only contain the glyphs that were printed. Never ship them as a text face.
- **Proposed roles are guesses.** Look at the thumbnails. Confirm every role against the source before building.

Then look at the brand directly: rasterize the guide's typography, color, logo and applications pages and read them. The extractor finds values; only looking finds the system.

## Build the brand profile

Write `<workdir>/brand-profile/profile.md` with every field filled or marked unknown. Each value carries its source.

| Field | What to capture |
|---|---|
| Owner | Whose brand, and why this document may wear it |
| Color roles | ground, ink, ink-muted, rule, accent, support, dark field, semantic colors if the brand defines them; plus sub-brand or product tints and exactly where each is allowed |
| Accent proportion | Roughly how much of a page the accent occupies in the source |
| Type roles | display, body, label or data face; weights, italics, case, tracking, numeral style |
| Type rules | What carries emphasis, headline case, what is never done |
| Font sourcing | Self-hosted files supplied, Google Fonts, installed locally, or substitute (named, with reason) |
| Logo | Files for positive and negative, clear space, minimum size, which marks go where |
| Layout grammar | Grid, margins, radius or none, rules or none, density, how sections open, how imagery is framed |
| Data grammar | How the brand's own documents draw tables and charts, if any exist |
| Voice cues | Sentence case vs title case, labels, tone words from the guide |
| Do nots | Every prohibition the guide states |

## Font sourcing, in order

1. Font files supplied with the brand (self-hosted `woff2`, `ttf`, `otf`). Embed with `@font-face` as data URIs so the HTML is self-contained. Check the license file travels with them.
2. Google Fonts, when the family is there. Link it, then confirm with `document.fonts` that it loaded before rendering the PDF.
3. Installed locally.
4. A declared substitute that matches the original's classification, x-height and width. Name the substitute and the reason in the build notes. A silent fallback to a system default is a defect.

The banned-font list in `soft-ui-patterns.md` does not apply to a brand's own specified faces. A brand that uses Inter gets Inter.

## Translating a web or screen brand to print

- **Keep:** color roles and proportions, type pairing and scale ratios, case and tracking rules, radius or its absence, rule weights, the logo system, image treatment, section rhythm.
- **Drop:** navigation, hover and motion, sticky bars, cookie and booking widgets, viewport-height heroes, decorative scroll effects.
- **Convert:** pixel sizes to points (0.75 pt per px), then re-scale so body text lands at 9.5 to 11.5 pt. Large display sizes shrink more than body. Keep the ratio between levels, not the absolute sizes.
- **Page ground:** use the brand's own ground color when it has one, applied identically in screen and print with `print-color-adjust: exact` on every colored block. A brand ground is the sanctioned exception to the white-page rule, the same principle as `warm`. Set the ground on `@page { background: ... }` as well as on `body`: Chrome paints body backgrounds only inside the page margins, so without the `@page` rule every interior page gets a white frame. A dark-mode website becomes a light document with dark cover and section bands unless the brand guide shows dark print pieces.
- **Sub-brand tints:** use them only where the guide says they belong, for example a property page for that property. Never as a rainbow across a group document.

## Fidelity QA before the user sees it

1. **Side by side.** Put page 1 of the render next to a brand guide page or site screenshot at the same scale. Would a person who works there accept it as theirs?
2. **Fonts loaded.** `document.fonts` lists the brand families with status `loaded`, and the PDF's embedded font list matches.
3. **Colors exact.** Every color in the CSS is a profile value or a documented tint of one. No invented hues.
4. **Logo untouched.** The supplied file, correct tone for its ground, clear space respected, above minimum size.
5. **Prohibitions checked.** Walk the guide's do-not list against the render.
6. **Proportion.** The accent is no louder than in the source.
7. **Nothing invented.** No taglines, slogans, icons, illustrations or product names that the brand does not already have.

## Build notes

Every matched render ends with a short note in the working folder: sources used, the confirmed profile, substitutions and why, assumptions made without a human, and QA results.
