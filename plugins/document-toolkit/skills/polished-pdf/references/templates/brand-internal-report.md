Brand-product aesthetic applied to a concise internal decision report. Read this file when Step 2 locks aesthetic = brand and doc-type = internal-report.

## Content-block schema (refusal gate input)

| Block | Required | Description |
|---|---|---|
| `title` | yes | Full report title. String. |
| `subtitle` | no | One-sentence framing. String. |
| `date` | yes | Publication or audit date. String. |
| `brand.name` | yes | Organization or product name. String. |
| `brand.accent` | no | Primary accent hex. Defaults to `#F2B100`. |
| `brand.secondary` | no | Secondary hex. Defaults to `#3FAB7E`. |
| `executive_verdict` | yes | Short decision-oriented summary. String. |
| `state_shift.current` | yes | Current-state phrase for the cover diagnostic. String. |
| `state_shift.target` | yes | Target-state phrase for the cover diagnostic. String. |
| `body.sections` | yes | 5 to 12 sections with `eyebrow`, `heading`, and `body`. |
| `comparison_rows` | no | Compact comparison rows for surfaces, promises, audiences, or paths. |
| `evidence_cards` | no | Observed evidence with optional severity and source. |
| `recommendations` | yes | Prioritized actions grouped by horizon. |
| `figures` | no | Screenshots or diagrams with captions and credits. |
| `limitations` | yes | Audit boundaries and unavailable evidence. String. |

If `executive_verdict`, `body.sections`, or `recommendations` is empty, Step 3 refuses to proceed.

## HTML scaffold (v0.1, Letter portrait)

White-page internal report with a bold diagnostic cover, warm geometric display type, rounded evidence cards, and an accent band showing current state to target state.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>
  @page { size: 8.5in 11in; margin: 0.75in; }
  :root {
    --ink: #1F2024;
    --ink-muted: #4A4E58;
    --ink-faint: #8B909B;
    --paper: #FFFFFF;
    --paper-alt: #F7F6F2;
    --accent: {{ brand.accent | default('#F2B100') }};
    --secondary: {{ brand.secondary | default('#3FAB7E') }};
    --rule: #E8E5DD;
  }
  html, body { margin: 0; padding: 0; background: var(--paper); color: var(--ink); }
  body { font-family: "Source Sans 3", "GT America", sans-serif; font-size: 11pt; line-height: 1.5; }
  h1, h2, h3 { font-family: "Avenir Next", "Gill Sans", sans-serif; page-break-after: avoid; }
  .cover { min-height: 9.45in; display: flex; flex-direction: column; page-break-after: always; }
  .cover-brand { font-size: 9pt; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
  .cover-title { font-size: 34pt; line-height: 1.03; letter-spacing: -.025em; margin: 1.2in 0 .22in; max-width: 6.5in; }
  .cover-subtitle { font-size: 15pt; line-height: 1.35; color: var(--ink-muted); max-width: 5.8in; }
  .diagnostic-band { margin-top: auto; border-radius: 1.25rem; background: var(--accent); padding: .36in; page-break-inside: avoid; }
  .diagnostic-label { font-size: 8pt; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin-bottom: .12in; }
  .state-shift { display: grid; grid-template-columns: 1fr auto 1fr; gap: .18in; align-items: center; }
  .state-box { font-size: 13pt; font-weight: 700; line-height: 1.25; }
  .state-box.target { text-align: right; }
  .state-arrow { font-size: 20pt; }
  .cover-date { margin-top: .24in; font-size: 9pt; color: var(--ink-muted); }
  .section { padding: .42in 0 .18in; }
  .eyebrow { font-size: 8pt; font-weight: 700; letter-spacing: .11em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: .09in; }
  h2 { font-size: 21pt; line-height: 1.12; margin: 0 0 .2in; }
  h3 { font-size: 14pt; line-height: 1.2; margin: .22in 0 .08in; }
  p { margin: 0 0 .14in; text-align: left; }
  .verdict { border-radius: 1.25rem; background: var(--paper-alt); border: 2px solid var(--accent); padding: .3in; font-size: 14pt; line-height: 1.42; page-break-inside: avoid; }
  .card-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: .18in; margin: .18in 0; }
  .card { border-radius: 1rem; background: var(--paper-alt); padding: .22in; page-break-inside: avoid; }
  .card.severe { border-top: 4px solid var(--accent); }
  .card .label { font-size: 8pt; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-muted); }
  .card .value { font-size: 13pt; font-weight: 700; line-height: 1.25; margin-top: .06in; }
  table { width: 100%; border-collapse: collapse; margin: .18in 0; font-size: 9.5pt; }
  th { text-align: left; font-size: 8pt; letter-spacing: .07em; text-transform: uppercase; padding: .1in; border-bottom: 2px solid var(--ink); }
  td { vertical-align: top; padding: .12in .1in; border-bottom: 1px solid var(--rule); }
  figure { margin: .22in 0; page-break-inside: avoid; }
  figure img { display: block; max-width: 100%; max-height: 5.2in; margin: 0 auto; object-fit: contain; }
  figcaption { font-size: 8.5pt; color: var(--ink-muted); margin-top: .08in; }
  .priority { display: grid; grid-template-columns: .42in 1fr; gap: .14in; margin: .14in 0; page-break-inside: avoid; }
  .priority-badge { width: .36in; height: .36in; border-radius: 999px; display: flex; align-items: center; justify-content: center; background: var(--accent); font-weight: 800; }
  .limitations { border-top: 2px solid var(--rule); padding-top: .18in; font-size: 9pt; color: var(--ink-muted); }
  .page-break { page-break-before: always; }
</style>
</head>
<body>
<section class="cover">
  <div class="cover-brand">{{ brand.name }}</div>
  <h1 class="cover-title">{{ title }}</h1>
  {% if subtitle %}<div class="cover-subtitle">{{ subtitle }}</div>{% endif %}
  <div class="diagnostic-band">
    <div class="diagnostic-label">Current state → target state</div>
    <div class="state-shift">
      <div class="state-box">{{ state_shift.current }}</div>
      <div class="state-arrow">→</div>
      <div class="state-box target">{{ state_shift.target }}</div>
    </div>
  </div>
  <div class="cover-date">{{ date }}</div>
</section>
<section class="section">
  <div class="eyebrow">Executive verdict</div>
  <div class="verdict">{{ executive_verdict }}</div>
</section>
{% for section in body.sections %}
<section class="section{% if section.page_break %} page-break{% endif %}">
  {% if section.eyebrow %}<div class="eyebrow">{{ section.eyebrow }}</div>{% endif %}
  <h2>{{ section.heading }}</h2>
  {{ section.body | safe }}
</section>
{% endfor %}
<section class="section">
  <div class="eyebrow">Prioritized actions</div>
  <h2>What changes first</h2>
  {% for item in recommendations %}
  <div class="priority"><div class="priority-badge">{{ loop.index }}</div><div>{{ item | safe }}</div></div>
  {% endfor %}
</section>
<section class="section limitations">
  <strong>Audit limitations.</strong> {{ limitations }}
</section>
</body>
</html>
```

## Render notes

- Uses Jinja2 substitution.
- Default geometry is US Letter portrait with 0.75-inch margins.
- The cover diagnostic band is the primary variance hook and may use the subject organization's accent rather than the fallback amber.
- Screenshots remain contained, captioned, and never stretched beyond legibility.

## Hard rules

1. White pages in screen and print.
2. No stock photography or decorative AI imagery.
3. No shadows.
4. No dense wall-of-text pages. Break evidence into cards, tables, or short subsections.
5. Every recommendation must trace to observed evidence.
6. Course screenshots retain aspect ratio and readable labels.
7. No em dashes and no contractions in report prose.

## Variance hooks

- Cover diagnostic band: bottom-aligned horizontal band or full-width mid-page card.
- Evidence treatment: two-column cards or a compact comparison table.
- Section opener: large whitespace or rounded diagnostic summary.

## What this template does not handle

- Financial statements or dense KPI spreads.
- Annual reports longer than roughly 20 pages.
- Full-bleed photography.
- Formal correspondence.

## Related

- `design-tokens-base.md`
- `design-tokens-brand.md`
- `soft-ui-patterns.md`
- `interface-design-patterns.md`

