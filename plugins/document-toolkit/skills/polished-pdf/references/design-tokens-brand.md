**Whose brand is this document?** Answer that before reading further. "Brand" is the name of an *aesthetic*, not a licence to apply any particular organization's identity. A mark, wordmark, colour system or company name reaches an outward-facing document only after its owner is confirmed and you know the document may wear it. Never put one organization's brand on another organization's document.

Mailchimp / Notion / Linear brand-product aesthetic. Friendly illustration, brand color everywhere, playful but precise type. Override on top of `design-tokens-base.md`.

## Color

- `--ink`: `#1F2024` (warm dark)
- `--ink-muted`: `#4A4E58`
- `--ink-faint`: `#9CA1AC`
- `--paper`: `#FFFFFF` (pure white for printability; the warmth comes from accent color, not the page)
- `--accent`: the accent color of **the brand this document actually belongs to**. Resolve ownership before loading anything. Take the accent from the owning organization's own brand guide, tokens or site (see `brand-matching.md`). This applies equally to the user's own organization, a client, a third party or an invented company. Fall back to `#A87617` (the editorial gold) only when no owning brand is established.
- `--secondary`: the secondary color from the same source as `--accent`, resolved by the same ownership test. Never mix two brands' palettes in one document.
- `--rule`: `#E8E5DD`

Illustration uses duotone treatment by default: every illustration is rendered in `--accent` + white, or `--accent` + `--secondary`. No realistic stock photography. If the doc-type needs imagery, prefer generated duotone illustration (from an image-generation tool, if available) over photos.

## Typography

- **Display font stack**: a friendly geometric sans (Clash Display, GT Walsheim, Söhne Buch) if licensed. Otherwise system sans, never banned fonts.
- **Body font stack**: `"Source Sans 3", "GT America", sans-serif`.
- **Hand stack**: cursive family for personal signature touches (invitation closings only). Default to `"Caveat", cursive` if no other hand-style is installed.

Scale:

- `--type-h1`: 30 pt (display)
- `--type-h2`: 20 pt
- `--type-h3`: 15 pt
- `--type-body`: 12 pt at 1.55 line-height (slightly larger than other aesthetics, friendlier)
- `--type-caption`: 10 pt at 1.4 line-height
- `--type-micro`: 9 pt, letter-spacing 0.06em, uppercase

## Page rhythm

- Rounded corners on every card or callout (`border-radius: 1rem` minimum, often `1.5rem`).
- Negative space is generous; nothing crowds the edges.
- Body sections may include duotone illustrations inline at 60-80% page width.
- CTAs and RSVPs use pill-shaped buttons with `--accent` fill, white text.

## What this aesthetic does well

Invitations, marketing PDFs, internal team docs, event recaps, onboarding handouts.

## What this aesthetic does not do

Multi-page reports, financial data spreads, somber subject matter.

## Doc types built so far

- `brand-internal-report.md`: concise internal decision reports with a diagnostic cover, evidence cards, comparison tables, and prioritized actions.
- `brand-lookbook.md`: phone-first product lookbooks. 9:16 page so one page fills one phone screen, per-section colour grounds, full-bleed plates, a name and one line per piece. Use it instead of `brand-internal-report` whenever the work is full-bleed photography, which that template does not handle.

The remaining brand doc types are deferred until first real use triggers the build-template sub-interview.

## Related

- `design-tokens-base.md`
- `brand-matching.md` (how to take real values from an owning organization's brand evidence)
- `templates/brand-invitation.md` (not yet built)
- `templates/brand-marketing-pdf.md` (not yet built)
- `templates/brand-lookbook.md`
- `templates/brand-internal-team-doc.md` (not yet built)
- `templates/brand-event-recap.md` (not yet built)
- `templates/brand-internal-report.md`
