The first fully-built template in polished-pdf. Stripe Press style editorial aesthetic applied to research report doc-type. Read this file when Step 2 of polished-pdf locks aesthetic = editorial and doc-type = research-report.

## Content-block schema (refusal gate input)

| Block | Required | Description |
|---|---|---|
| `title` | yes | Full title of the report. String. |
| `subtitle` | no | Optional subtitle. String. |
| `authors` | yes | One or more authors with name + affiliation. Array. |
| `date` | yes | Publication date. ISO 8601 or written form. |
| `abstract` | yes | 150 to 300 word executive summary. String. |
| `keywords` | no | Comma-separated. String. |
| `toc` | no | Table of contents. Auto-generated from `body.sections` if omitted. |
| `body.sections` | yes | 3 to 12 sections. Each has `heading`, `body` (markdown), and optional `figures`, `pull_quotes`, `footnotes`. |
| `figures` | no | Inline images or charts. Array of `{src, caption, credit}`. |
| `references` | no | Bibliography. Array of citation strings. |
| `colophon` | no | Production notes. String. |

If `body.sections` is empty or has zero recognizable headings, Step 3 refuses to proceed.

## HTML scaffold (v0.1, white-page-locked)

Single column main body with optional sidenotes. White page (per v0.1 print-friendly rule). Gold accent on pull-quote left rules only.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ title }}</title>
<style>
  @page { size: 8.5in 11in; margin: 0.85in; }
  :root {
    --ink: #111111;
    --ink-muted: #4A4A4A;
    --ink-faint: #888888;
    --rule: #C9C9C9;
    --gold: #A87617;
  }
  html, body { background: #FFFFFF; margin: 0; padding: 0; }
  body {
    font-family: "Source Serif 4", "Source Serif 4 Text", Georgia, serif;
    font-size: 11pt;
    line-height: 1.55;
    color: var(--ink);
  }
  .eyebrow {
    font-family: "Source Serif 4 Caption", serif;
    font-size: 9pt;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-muted);
    margin-bottom: 0.2in;
  }
  h1.cover-title {
    font-family: "Source Serif 4 Display", Georgia, serif;
    font-size: 36pt;
    line-height: 1.05;
    font-weight: 400;
    margin: 0 0 0.3in;
    max-width: 6in;
  }
  .subtitle {
    font-family: "Source Serif 4 Display", Georgia, serif;
    font-size: 18pt;
    font-style: italic;
    color: var(--ink-muted);
    margin: 0 0 0.6in;
    max-width: 6in;
  }
  .authors {
    font-size: 10pt;
    color: var(--ink-muted);
    margin-bottom: 0.15in;
  }
  .date {
    font-size: 9pt;
    color: var(--ink-faint);
  }
  .cover { page-break-after: always; padding-top: 3in; }
  h2.section-heading {
    font-family: "Source Serif 4 Display", Georgia, serif;
    font-size: 22pt;
    font-weight: 400;
    line-height: 1.15;
    margin: 0.5in 0 0.18in;
    page-break-after: avoid;
  }
  p.body { margin: 0 0 0.16in; text-align: left; hyphens: none; }
  .pull-quote {
    font-style: italic;
    color: var(--ink-muted);
    border-left: 2px solid var(--gold);
    padding-left: 0.25in;
    margin: 0.25in 0;
    max-width: 5in;
  }
  figure { margin: 0.3in 0; page-break-inside: avoid; }
  figure img { max-width: 100%; height: auto; }
  figcaption { font-size: 9pt; color: var(--ink-muted); margin-top: 0.08in; font-style: italic; }
  .references { font-size: 9pt; color: var(--ink-muted); }
  .references li { margin-bottom: 0.12in; text-indent: -1em; padding-left: 1em; }
</style>
</head>
<body>

<section class="cover">
  {% if keywords %}<div class="eyebrow">{{ keywords }}</div>{% endif %}
  <h1 class="cover-title">{{ title }}</h1>
  {% if subtitle %}<div class="subtitle">{{ subtitle }}</div>{% endif %}
  <div class="authors">
    {% for author in authors %}{{ author.name }}, {{ author.affiliation }}{% if not loop.last %} · {% endif %}{% endfor %}
  </div>
  <div class="date">{{ date }}</div>
</section>

{% if abstract %}
<section>
  <div class="eyebrow">Abstract</div>
  <p class="body">{{ abstract }}</p>
</section>
{% endif %}

{% for section in body.sections %}
<section>
  <h2 class="section-heading">{{ section.heading }}</h2>
  {{ section.body | safe }}
  {% for figure in section.figures or [] %}
  <figure>
    <img src="{{ figure.src }}" alt="{{ figure.caption }}">
    <figcaption>{{ figure.caption }}{% if figure.credit %} <em>Credit: {{ figure.credit }}</em>{% endif %}</figcaption>
  </figure>
  {% endfor %}
  {% for quote in section.pull_quotes or [] %}
  <blockquote class="pull-quote">{{ quote }}</blockquote>
  {% endfor %}
</section>
{% endfor %}

{% if references %}
<section>
  <h2 class="section-heading">References</h2>
  <ol class="references">
    {% for ref in references %}<li>{{ ref }}</li>{% endfor %}
  </ol>
</section>
{% endif %}

</body>
</html>
```

## Render notes

- Uses jinja2 substitution.
- White page everywhere per the v0.1 print-friendly rule. Drop the cream paper from earlier drafts.
- Drop cap on first paragraph removed from v0.1; reintroduce only on explicit user request.
- Pull-quote color and weight: italic muted gray text with a gold left rule. No background fill.

## Hard rules

1. **Page background is white.** No exception.
2. **Left-aligned body, no hyphenation.** Same rule as formal-letter.
3. **Source Serif 4 over Source Serif Pro.** Same rule as formal-letter.

## Variance hooks

- Cover layout: top-aligned title vs bottom-aligned title (using `padding-top` value).
- Pull-quote position: inline (default) vs marginalia (using `float: right` plus negative right margin).

## What this template does not handle

- Multi-column body layout (use `editorial-long-form-essay.md` once built).
- KPI spreads or financial tables (use `corporate-annual-report.md` once built).
- Full-bleed photography (use `corporate-business-review.md` once built).

## Related

- `design-tokens-base.md`
- `design-tokens-editorial.md`
- `soft-ui-patterns.md`
- `interface-design-patterns.md`
- `editorial-formal-letter.md` (sibling template, shares the same hard rules)
