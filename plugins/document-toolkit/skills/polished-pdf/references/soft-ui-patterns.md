Patterns adapted from the `design:soft-ui` plugin SKILL.md. The original is screen-only; this extract keeps only what applies to print PDFs. Read on every polished-pdf run.

## The "Absolute Zero" directive (anti-patterns)

If the generated HTML for a PDF includes any of these, the design fails:

- **Banned fonts**: Inter, Roboto, Arial, Open Sans, Helvetica. Use premium fonts named in the chosen `design-tokens-<aesthetic>.md` instead. If a premium font is not available on the rendering machine, fall back to the next stack item, not to a banned font.
- **Banned shadows in print templates**: any shadow. Shadows print as muddy gray blocks. Reserve them for screen-only template variants.
- **Banned borders**: generic 1 px solid gray. Use the per-aesthetic `--rule` token.
- **Banned color usage**: a colored full-page background that varies across render modes. The page tone is a single value, applied everywhere, or it is white.
- **Banned spacing**: less than `--space-1` between vertically adjacent text blocks. Real documents breathe.

## Variance mandate

Never produce the same layout twice in a row across multiple runs of the same aesthetic. For each run, vary at least one of:

- Hero treatment (left-aligned vs centered vs full-bleed)
- Section opener style (color block vs whitespace vs hairline)
- Pull-quote or blockquote style (offset to gutter vs inline vs full-page)

Defaults are the enemy. Two runs of the same aesthetic should feel like the same publishing house but a different issue.

## Eyebrow tags

Precede major H1 and H2 headings with a microscopic uppercase eyebrow tag using the `--type-micro` token. Use sparingly: one per section opener, not on every heading. Skip eyebrow tags entirely for formal-letter doc-type; they read as design-y on personal correspondence.

## Macro-whitespace

Double the standard padding instinct. Section breaks use `--space-7`. Chapter breaks use `--space-8`. A page that looks underfilled when you scan it is probably correctly designed; a page that feels balanced when you scan it is probably overcrowded. The exception is formal-letter, which uses tighter spacing for a more conversational feel.

## Spatial rhythm

Every vertical gap should be a multiple of `--space-1`. Misaligned spacing breaks the baseline grid and the page reads as amateur even if you cannot identify why.

## What does not apply in print

The original SKILL.md covers motion choreography (button hover physics, scroll interpolation, magnetic hover) and JS-driven scroll reveals. None of that applies to a static PDF. Ignore those sections when rendering for print.

For the HTML preview shown to the user in a browser before the PDF render, light hover and entry animations are allowed. They do not transfer to the rendered PDF, but they help the user evaluate the visual hierarchy during preview.

## Pre-output checklist

Before saving the HTML for PDF rendering:

- [ ] No banned fonts in any font-family stack.
- [ ] Page background is white in every render mode (or a single non-white tone applied uniformly across screen and print).
- [ ] No shadows in print templates.
- [ ] Every section padding is at least `--space-7` (or `--space-3` for formal-letter).
- [ ] Eyebrow tags precede H1 and H2 section openers in research-report and corporate doc-types. Suppressed for formal-letter.
- [ ] Variance check: this layout differs from the previous run of the same aesthetic on at least one of hero / section / blockquote.

## Related

- `design-tokens-base.md`
- `design-tokens-editorial.md`
- `design-tokens-corporate.md`
- `design-tokens-brand.md`
- `interface-design-patterns.md`
- Source plugin: `design:soft-ui`
