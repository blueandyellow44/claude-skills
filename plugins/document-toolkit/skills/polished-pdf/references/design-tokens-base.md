Shared typographic scale, spacing rhythm, and semantic tokens used by every polished-pdf template. Aesthetic-specific overrides live in `design-tokens-editorial.md`, `design-tokens-corporate.md`, `design-tokens-brand.md`, and `design-tokens-warm.md`. Read this file first, then the chosen aesthetic file.

## Page dimensions

Default to US Letter portrait, 8.5 in × 11 in, with print-safe margins:

- Top: 0.75 in
- Bottom: 0.75 in
- Outside (right on recto, left on verso): 0.75 in
- Inside (binding-side): 1.0 in

For invitations and event recaps, prefer A5 portrait (5.83 in × 8.27 in) by default; the brand aesthetic file overrides accordingly.

## Type scale

Modular scale based on a 1.25 ratio (major third) for body documents. Use the variable names below in every template; aesthetic files override the actual values.

- `--type-display` (largest): roughly 4× body
- `--type-h1`: roughly 2.4× body
- `--type-h2`: roughly 1.8× body
- `--type-h3`: roughly 1.4× body
- `--type-body`: base (typically 11 pt for print, 16 px for screen)
- `--type-caption`: 0.85× body
- `--type-micro`: 0.7× body

## Line-height scale

- `--leading-display`: 1.05
- `--leading-heading`: 1.15
- `--leading-body`: 1.5 for serif body, 1.55 for sans body
- `--leading-tight`: 1.2 (use for callouts, captions)

## Spacing rhythm

Vertical rhythm based on body line-height. All vertical spacing should be a multiple of `--space-1` to keep the baseline grid coherent.

- `--space-0`: 0
- `--space-1`: 0.25× body line-height
- `--space-2`: 0.5× body line-height
- `--space-3`: 1× body line-height
- `--space-4`: 1.5× body line-height
- `--space-5`: 2× body line-height
- `--space-6`: 3× body line-height
- `--space-7`: 5× body line-height (section breaks)
- `--space-8`: 8× body line-height (chapter breaks)

## Semantic color tokens

Defined per aesthetic. Every template references the semantic names, not the raw hex values:

- `--ink`: primary text
- `--ink-muted`: secondary text, captions
- `--ink-faint`: tertiary text, watermarks
- `--paper`: page background (must be white for any document intended for print, except the `warm` aesthetic, which is sanctioned to use a warm cream page; see `design-tokens-warm.md` and its Chrome print-color-adjust requirement; every other aesthetic follows the editorial-tokens rule)
- `--paper-alt`: section dividers, callout backgrounds
- `--accent`: primary accent color, used sparingly
- `--accent-muted`: hover, secondary accent
- `--rule`: hairline rules, borders
- `--shadow`: subtle drop shadows for layered elements (screen only; do not use in print templates)

## Banned tokens

These are the failure modes inherited from `soft-ui-patterns.md`. Do not use them in any template.

- Banned fonts in CSS `font-family` stacks: Inter, Roboto, Arial, Open Sans, Helvetica (any of these without an explicit override from the user or a brand that specifies them means the template is wrong).
- Banned shadows in print templates: any shadow. Shadows print as muddy gray blocks; reserve them for screen-only templates.
- Banned color usage: full-page backgrounds in any non-white color for print templates, except the `warm` aesthetic (design-tokens-warm.md), the one sanctioned exception, and a matched brand's own ground (see `brand-matching.md`). See editorial tokens for why the page is white.
- Banned spacing: less than `--space-1` between vertically adjacent text blocks. Real documents breathe.

## Print vs screen

For print-targeted templates (anything that may be physically printed), the page background is white in every render mode, except the `warm` aesthetic, which uses its cream page in every render mode for the same reason: consistency between screen preview and print output matters more than which color is consistent. Do not use `@media print` vs `@media screen` to give print a different background tone in any aesthetic. If a screen-only PDF wants a tinted paper feel outside the `warm` aesthetic, apply it equally in print and accept the toner cost (rare).

## Related

- `design-tokens-editorial.md`
- `design-tokens-corporate.md`
- `design-tokens-brand.md`
- `design-tokens-warm.md`
- `soft-ui-patterns.md`
- `interface-design-patterns.md`
